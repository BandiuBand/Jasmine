"""Regression tests for the cross-process LLM lock and the v2 shadow queue.

These guard the contract that:
* ``llm_lock`` serializes concurrent acquisitions (within and across
  processes) — verified here using two threads, since flock is shared
  inside a single Python process via the same lock file.
* ``shadow_queue.enqueue`` / ``drain`` are FIFO, atomic (drain removes
  what it returns) and tolerant to concurrent producers.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.transport import shadow_queue
from llm_lock import llm_lock


# --------------------------------------------------------------------------- #
# llm_lock
# --------------------------------------------------------------------------- #


def test_llm_lock_serializes_overlapping_acquisitions():
    """Two threads contending for the lock must run their critical sections
    strictly one after the other."""
    timeline: list[tuple[str, float]] = []
    lock_obs = threading.Lock()

    def worker(tag: str, hold: float) -> None:
        with llm_lock(label=f"test:{tag}"):
            with lock_obs:
                timeline.append((f"{tag}:enter", time.monotonic()))
            time.sleep(hold)
            with lock_obs:
                timeline.append((f"{tag}:exit", time.monotonic()))

    t1 = threading.Thread(target=worker, args=("a", 0.15))
    t2 = threading.Thread(target=worker, args=("b", 0.05))
    t1.start()
    # ensure t1 acquires first
    time.sleep(0.02)
    t2.start()
    t1.join()
    t2.join()

    events = [name for name, _ in timeline]
    # Expect: a:enter -> a:exit -> b:enter -> b:exit (no interleaving)
    assert events == ["a:enter", "a:exit", "b:enter", "b:exit"], events


# --------------------------------------------------------------------------- #
# shadow_queue
# --------------------------------------------------------------------------- #


def _reset_queue() -> None:
    path = shadow_queue.queue_path()
    if os.path.exists(path):
        os.remove(path)


def test_shadow_queue_enqueue_drain_fifo():
    _reset_queue()
    try:
        for i in range(3):
            shadow_queue.enqueue({"chat_id": "c", "user_id": "u", "text": f"msg-{i}"})

        items = shadow_queue.drain()
        assert [it["text"] for it in items] == ["msg-0", "msg-1", "msg-2"]

        # Subsequent drain returns nothing — file removed.
        assert shadow_queue.drain() == []
        assert not os.path.exists(shadow_queue.queue_path())
    finally:
        _reset_queue()


def test_shadow_queue_concurrent_enqueue():
    """Multiple producer threads must not lose or corrupt entries."""
    _reset_queue()
    try:
        n_producers = 6
        per_producer = 20

        def producer(pid: int) -> None:
            for i in range(per_producer):
                shadow_queue.enqueue(
                    {"chat_id": "c", "user_id": "u", "text": f"p{pid}-{i}"}
                )

        threads = [
            threading.Thread(target=producer, args=(p,)) for p in range(n_producers)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        items = shadow_queue.drain()
        assert len(items) == n_producers * per_producer
        # Every produced text appears exactly once.
        seen = {it["text"] for it in items}
        expected = {f"p{p}-{i}" for p in range(n_producers) for i in range(per_producer)}
        assert seen == expected
    finally:
        _reset_queue()


def test_shadow_queue_drain_empty_is_safe():
    _reset_queue()
    assert shadow_queue.drain() == []


if __name__ == "__main__":
    test_llm_lock_serializes_overlapping_acquisitions()
    test_shadow_queue_enqueue_drain_fifo()
    test_shadow_queue_concurrent_enqueue()
    test_shadow_queue_drain_empty_is_safe()
    print("OK")
