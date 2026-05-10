#!/usr/bin/env python3
"""
Process queued WasterWhisper messages into the local Graphiti memory service.
"""

import argparse
import json
import os
import sys
import time
from typing import Dict, List

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

from jasmine_filter import load_config
from kg.graphiti_client import (
    GraphitiMemoryClient,
    canonical_graphiti_group_id,
    graphiti_group_id,
)


def _queue_path(config: Dict) -> str:
    graphiti_config = config.get("jasmine_filter", {}).get("graphiti_memory", {})
    path = graphiti_config.get("queue_path", "logs/graphiti_ingest_queue.jsonl")
    return path if os.path.isabs(path) else os.path.join(_BASE_DIR, path)


def _dead_letter_path(config: Dict) -> str:
    graphiti_config = config.get("jasmine_filter", {}).get("graphiti_memory", {})
    path = graphiti_config.get("dead_letter_path", "logs/graphiti_ingest_dead_letter.jsonl")
    return path if os.path.isabs(path) else os.path.join(_BASE_DIR, path)


def _load_queue(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(_normalize_item(json.loads(line)))
            except json.JSONDecodeError as exc:
                print(f"[GraphitiWorker] Bad queue line ignored: {exc}")
    return items


def _normalize_item(item: Dict) -> Dict:
    chat = ""
    for line in str(item.get("body", "")).splitlines():
        if line.startswith("Chat: "):
            chat = line[len("Chat: ") :]
            break
    if not chat:
        chat = item.get("group_id", "unknown")

    old_group_id = canonical_graphiti_group_id(str(item.get("group_id", "")))
    new_group_id = graphiti_group_id(chat)
    item["group_id"] = new_group_id

    name = str(item.get("name", ""))
    while name.startswith("telegram_telegram_"):
        name = name[len("telegram_") :]
    if old_group_id and name.startswith(old_group_id + "_"):
        item["name"] = new_group_id + name[len(old_group_id) :]
    elif name:
        item["name"] = f"{new_group_id}_{name}"
    return item


def _write_queue(path: str, items: List[Dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _append_dead_letter(path: str, item: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def process_once(config: Dict, limit: int = 20) -> Dict[str, int]:
    graphiti_config = config.get("jasmine_filter", {}).get("graphiti_memory", {})
    graphiti = GraphitiMemoryClient(graphiti_config)
    queue_path = _queue_path(config)
    dead_letter_path = _dead_letter_path(config)
    max_failures = int(graphiti_config.get("max_ingest_failures", 3))
    items = _load_queue(queue_path)

    processed = 0
    failed = 0
    dead_lettered = 0
    remaining = items[limit:]

    for item in items[:limit]:
        ok = graphiti.add_episode(
            name=item["name"],
            body=item["body"],
            group_id=item["group_id"],
            sender=item.get("sender", "unknown"),
            reference_time=item.get("reference_time"),
        )
        if ok:
            processed += 1
        else:
            failed += 1
            item["graphiti_failures"] = int(item.get("graphiti_failures", 0)) + 1
            if item["graphiti_failures"] >= max_failures:
                dead_lettered += 1
                _append_dead_letter(dead_letter_path, item)
                print(
                    "[GraphitiWorker] Dead-lettered item after "
                    f"{item['graphiti_failures']} failures: {item.get('name', '<unnamed>')}"
                )
            else:
                remaining.append(item)

    _write_queue(queue_path, remaining)
    return {
        "queued": len(items),
        "processed": processed,
        "failed": failed,
        "dead_lettered": dead_lettered,
        "remaining": len(remaining),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Graphiti ingest queue worker")
    parser.add_argument("--once", action="store_true", help="Process queue once and exit")
    parser.add_argument("--watch", action="store_true", help="Continuously process the queue")
    parser.add_argument("--interval", type=int, default=30, help="Watch interval in seconds")
    parser.add_argument("--limit", type=int, default=20, help="Max queue items per batch")
    args = parser.parse_args()

    config = load_config()
    while True:
        stats = process_once(config, limit=args.limit)
        print(
            "[GraphitiWorker] queued={queued}, processed={processed}, "
            "failed={failed}, dead_lettered={dead_lettered}, "
            "remaining={remaining}".format(**stats)
        )
        if args.once or not args.watch:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
