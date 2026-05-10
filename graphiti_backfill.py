#!/usr/bin/env python3
"""
Backfill Telegram chat logs into the local Graphiti memory service.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, Iterator, List

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

from jasmine_filter import load_config, load_processed_messages, save_processed_messages
from kg.graphiti_client import GraphitiMemoryClient, append_episode_queue, graphiti_group_id

_LOGS_DIR = os.path.join(_BASE_DIR, "logs")
_STATE_FILE = os.path.join(_BASE_DIR, "logs", "graphiti_backfill_state.json")
_LINE_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2})\]\s+\[(\w+)\](?:\s+\[([^\]]+)\])?(?:\s+\[([^\]]+)\])?\s+(.+)$"
)


def iter_log_messages() -> Iterator[Dict]:
    if not os.path.exists(_LOGS_DIR):
        return
    for year in sorted(os.listdir(_LOGS_DIR)):
        year_path = os.path.join(_LOGS_DIR, year)
        if not os.path.isdir(year_path) or not year.isdigit():
            continue
        for month in sorted(os.listdir(year_path)):
            month_path = os.path.join(year_path, month)
            if not os.path.isdir(month_path):
                continue
            for day in sorted(os.listdir(month_path)):
                day_path = os.path.join(month_path, day)
                if not os.path.isdir(day_path):
                    continue
                date_str = f"{year}-{month}-{day}"
                for log_file in sorted(os.listdir(day_path)):
                    if not log_file.endswith(".txt"):
                        continue
                    chat_identifier = log_file[:-4]
                    file_path = os.path.join(day_path, log_file)
                    with open(file_path, encoding="utf-8", errors="replace") as f:
                        for line_idx, line in enumerate(f):
                            match = _LINE_RE.match(line.strip())
                            if not match:
                                continue
                            ts, msg_type, third, fourth, text = match.groups()
                            if third in {"private", "group", "supergroup", "channel"}:
                                chat_type = third
                                sender = fourth or chat_identifier
                            else:
                                chat_type = ""
                                sender = third or chat_identifier
                            sender = sender or chat_identifier
                            yield {
                                "file_path": file_path,
                                "line_idx": line_idx,
                                "timestamp": ts,
                                "msg_type": msg_type,
                                "chat_type": chat_type,
                                "sender": sender,
                                "text": text.strip(),
                                "chat_id": chat_identifier,
                                "date_str": date_str,
                                "reference_time": datetime.strptime(
                                    f"{date_str} {ts}", "%Y-%m-%d %H:%M:%S"
                                ).isoformat(),
                            }


def message_key(msg: Dict) -> str:
    raw = f"{msg['file_path']}:{msg['line_idx']}:{msg['timestamp']}:{msg['sender']}:{msg['text']}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def episode_payload(msg: Dict, key: str) -> Dict:
    group_id = graphiti_group_id(msg["chat_id"])
    body = (
        f"Chat: {msg['chat_id']}\n"
        f"Sender: {msg['sender']}\n"
        f"Chat type: {msg.get('chat_type') or 'unknown'}\n"
        f"Message type: {msg['msg_type']}\n"
        f"Timestamp: {msg['date_str']} {msg['timestamp']}\n"
        f"Text: {msg['text']}"
    )
    return {
        "name": f"{group_id}_{key}",
        "body": body,
        "group_id": group_id,
        "sender": msg["sender"],
        "reference_time": msg["reference_time"],
    }


def load_state(path: str = _STATE_FILE) -> set:
    if not os.path.exists(path):
        return set()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("processed", []))
    except Exception:
        return set()


def save_state(processed: set, path: str = _STATE_FILE) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"processed": sorted(processed)}, f, ensure_ascii=False, indent=2)


def queue_path(config: Dict) -> str:
    graphiti_config = config.get("jasmine_filter", {}).get("graphiti_memory", {})
    path = graphiti_config.get("queue_path", "logs/graphiti_ingest_queue.jsonl")
    return path if os.path.isabs(path) else os.path.join(_BASE_DIR, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill chat logs into Graphiti")
    parser.add_argument("--dry-run", action="store_true", help="Only print planned work")
    parser.add_argument("--mode", choices=("queue", "api"), default="queue")
    parser.add_argument("--limit", type=int, default=0, help="Max messages to enqueue/send")
    parser.add_argument("--chat", default="", help="Only process a chat filename without .txt")
    parser.add_argument("--reset-state", action="store_true", help="Ignore previous backfill state")
    parser.add_argument(
        "--mark-jasmine-processed",
        action="store_true",
        help="Also mark messages as processed for jasmine_filter.py",
    )
    args = parser.parse_args()

    config = load_config()
    graphiti_config = config.get("jasmine_filter", {}).get("graphiti_memory", {})
    graphiti = GraphitiMemoryClient(graphiti_config)
    processed = set() if args.reset_state else load_state()
    jasmine_processed = load_processed_messages() if args.mark_jasmine_processed else set()
    qpath = queue_path(config)

    planned = []
    for msg in iter_log_messages():
        if args.chat and msg["chat_id"] != args.chat:
            continue
        key = message_key(msg)
        if key in processed:
            continue
        planned.append((msg, key, episode_payload(msg, key)))
        if args.limit and len(planned) >= args.limit:
            break

    print(f"[GraphitiBackfill] pending={len(planned)}, mode={args.mode}, dry_run={args.dry_run}")
    for msg, key, payload in planned[:10]:
        print(
            f"  {payload['group_id']} {msg['date_str']} {msg['timestamp']} "
            f"[{msg['sender']}] {msg['text'][:80]}"
        )
    if len(planned) > 10:
        print(f"  ... {len(planned) - 10} more")

    if args.dry_run:
        return

    ok_count = 0
    fail_count = 0
    for msg, key, payload in planned:
        if args.mode == "queue":
            append_episode_queue(qpath, payload)
            ok = True
        else:
            ok = graphiti.add_episode(
                name=payload["name"],
                body=payload["body"],
                group_id=payload["group_id"],
                sender=payload["sender"],
                reference_time=payload["reference_time"],
            )
        if ok:
            ok_count += 1
            processed.add(key)
            if args.mark_jasmine_processed:
                jasmine_processed.add(key)
        else:
            fail_count += 1
        if args.mode == "api":
            time.sleep(0.1)
        if ok_count % 20 == 0:
            save_state(processed)

    save_state(processed)
    if args.mark_jasmine_processed:
        save_processed_messages(jasmine_processed)
    print(
        f"[GraphitiBackfill] done ok={ok_count}, failed={fail_count}, "
        f"state={_STATE_FILE}, queue={qpath}"
    )


if __name__ == "__main__":
    main()
