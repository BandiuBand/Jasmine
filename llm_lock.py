"""Cross-process exclusive lock for serializing LLM HTTP calls.

The bot, jasmine_filter watcher and kg_tool watcher all run as separate
processes that share a single LM Studio model (and Ollama as a fallback).
Concurrent requests overload the local model and previously caused crashes
that triggered Ollama fallbacks. Wrapping every outbound LLM HTTP call in
``with llm_lock(): ...`` ensures only one inference is in flight at any time
across all processes.

The lock is implemented with ``fcntl.flock`` over a single lock file in the
project ``logs/`` directory, which works across processes on Linux/macOS.
"""

from __future__ import annotations

import fcntl
import os
import time
from contextlib import contextmanager
from typing import Iterator, Optional

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCK_DIR = os.path.join(_BASE_DIR, "logs")
_LOCK_PATH = os.path.join(_LOCK_DIR, "llm.lock")

_DEBUG = os.environ.get("LLM_LOCK_DEBUG") == "1"


@contextmanager
def llm_lock(label: str = "") -> Iterator[None]:
    """Acquire an exclusive cross-process lock around an LLM HTTP call.

    Args:
        label: Optional human-readable tag printed in debug logs (set
            ``LLM_LOCK_DEBUG=1`` in the environment to enable).
    """
    os.makedirs(_LOCK_DIR, exist_ok=True)
    fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
    waited_at: Optional[float] = None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            waited_at = time.monotonic()
            if _DEBUG:
                print(
                    f"[llm_lock] waiting pid={os.getpid()} label={label!r}",
                    flush=True,
                )
            fcntl.flock(fd, fcntl.LOCK_EX)
        if _DEBUG:
            waited = (time.monotonic() - waited_at) if waited_at is not None else 0.0
            print(
                f"[llm_lock] acquired pid={os.getpid()} label={label!r} "
                f"waited={waited:.2f}s",
                flush=True,
            )
        try:
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                if _DEBUG:
                    print(
                        f"[llm_lock] released pid={os.getpid()} label={label!r}",
                        flush=True,
                    )
    finally:
        os.close(fd)
