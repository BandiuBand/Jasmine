"""File-backed pending queue for Jasmine v2 shadow events.

The Telegram bot ``bot.py`` enqueues one JSON line per incoming text
message instead of running the v2 shadow graph inline. The Jasmine v1
watcher (``jasmine_filter.py``) drains this queue at the end of every
processing cycle and runs ``run_telegram_shadow_event`` for each pending
item. This guarantees two invariants:

1. v1 fully finishes processing a given message *before* v2 shadow runs
   for the same message (no cross-version race for shared resources such
   as LM Studio and the Graphiti service).
2. v2 shadow events are processed strictly sequentially in a single
   process, so the v2 graph never runs concurrently with itself.

The queue is a single JSONL file under ``logs/``. Concurrent producers
(``bot.py``) and the consumer (``jasmine_filter.py``) coordinate via an
``fcntl.flock`` on a sibling ``.lock`` file.
"""

from __future__ import annotations

import fcntl
import json
import os
from typing import Any, Iterator, List

_BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_QUEUE_DIR = os.path.join(_BASE_DIR, "logs")
_QUEUE_PATH = os.path.join(_QUEUE_DIR, "v2_shadow_pending.jsonl")
_LOCK_PATH = _QUEUE_PATH + ".lock"


def queue_path() -> str:
    """Return the absolute path of the queue file (mainly for tests)."""
    return _QUEUE_PATH


def _open_lock_fd() -> int:
    os.makedirs(_QUEUE_DIR, exist_ok=True)
    return os.open(_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)


class _Locked:
    def __init__(self) -> None:
        self._fd = _open_lock_fd()

    def __enter__(self) -> "_Locked":
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)


def enqueue(payload: dict) -> None:
    """Append a single shadow-event payload to the pending queue."""
    with _Locked():
        with open(_QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def drain() -> List[dict]:
    """Atomically read and remove all pending payloads from the queue.

    Returns the list of decoded payloads in FIFO order. Malformed lines
    are skipped silently. New writes from producers that arrive after
    ``drain`` releases the lock are picked up on the next call.
    """
    with _Locked():
        if not os.path.exists(_QUEUE_PATH):
            return []
        with open(_QUEUE_PATH, encoding="utf-8") as f:
            content = f.read()
        try:
            os.remove(_QUEUE_PATH)
        except FileNotFoundError:
            pass

    items: List[dict] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def iter_drain() -> Iterator[dict]:
    """Convenience iterator over the result of :func:`drain`."""
    yield from drain()
