#!/usr/bin/env python3
"""
Knowledge Graph Tool for WasterWhisper bot.

Usage:
  python kg_tool.py --process              # process all unprocessed messages
  python kg_tool.py --watch                # process new messages every 30 s
  python kg_tool.py --schedule 60          # process every N minutes
  python kg_tool.py --show <identifier>    # show graph for a person/chat
  python kg_tool.py --list                 # list all known persons
  python kg_tool.py --stats                # graph statistics
  python kg_tool.py --reset                # reset processed tracking
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

from kg.extractor import extract
from kg.store import KnowledgeGraph

# --------------------------------------------------------------------------
# Configuration (override via env vars)
# --------------------------------------------------------------------------
LLM_URL     = os.getenv("LLM_URL",     "http://127.0.0.1:1234/v1/chat/completions")
LLM_MODEL   = os.getenv("LLM_MODEL",   "openai/gpt-oss-20b")
EMBED_URL   = os.getenv("EMBED_URL",   "http://127.0.0.1:1234/v1/embeddings")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")

LOGS_DIR      = os.path.join(_BASE_DIR, "logs")
GRAPH_PATH    = os.path.join(_BASE_DIR, "kg", "graph.json")
REGISTRY_FILE = os.path.join(LOGS_DIR,  "chat_registry.json")

# Matches: [HH:MM:SS] [type] optional:[sender]  text
_LINE_RE = re.compile(
    r"^\[(\d{2}:\d{2}:\d{2})\]\s+\[(\w+)\](?:\s+\[([^\]]+)\])?\s+(.+)$"
)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def load_registry() -> dict:
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def iter_log_messages():
    """Yield (file_path, line_idx, timestamp, msg_type, sender, text,
              chat_identifier, date_str) for every parsed log line."""
    if not os.path.exists(LOGS_DIR):
        return
    for year in sorted(os.listdir(LOGS_DIR)):
        year_path = os.path.join(LOGS_DIR, year)
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
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            for i, line in enumerate(f):
                                m = _LINE_RE.match(line.strip())
                                if not m:
                                    continue
                                ts, msg_type, sender, text = m.groups()
                                sender = sender or chat_identifier
                                yield (file_path, i, ts, msg_type, sender,
                                       text, chat_identifier, date_str)
                    except Exception as e:
                        print(f"[KG] Cannot read {file_path}: {e}")


def msg_key(file_path: str, line_idx: int, text: str) -> str:
    raw = f"{file_path}:{line_idx}:{text}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def lm_studio_available() -> bool:
    import requests
    try:
        requests.get(LLM_URL.replace("/chat/completions", "/models"), timeout=3)
        return True
    except Exception:
        return False

# --------------------------------------------------------------------------
# Core processing
# --------------------------------------------------------------------------

def process_messages(kg: KnowledgeGraph, registry: dict,
                     verbose: bool = True) -> int:
    total_msgs = 0
    total_new  = 0

    for (file_path, line_idx, ts, msg_type, sender,
         text, chat_id_str, date_str) in iter_log_messages():
        key = msg_key(file_path, line_idx, text)
        if kg.is_processed(key):
            continue

        total_msgs += 1
        real_chat_id = str(registry.get(chat_id_str, chat_id_str))
        source_ref   = f"{chat_id_str}/{date_str}/{ts}"

        if verbose:
            print(f"  [{sender}] {text[:70]}...")

        items = extract(text, sender, chat_id_str, LLM_URL, LLM_MODEL)
        added = 0
        if items:
            added = kg.add_items(
                items, sender, chat_id_str, real_chat_id, source_ref
            )
            if verbose and added:
                for it in items:
                    print(f"    + [{it['type']}] {it['value']}")

        kg.mark_processed(key)
        total_new += added

        if total_msgs % 5 == 0:
            kg.save()

    kg.save()
    return total_msgs, total_new

# --------------------------------------------------------------------------
# Display
# --------------------------------------------------------------------------

def show_graph(identifier: str, kg: KnowledgeGraph):
    result = kg.get_person_graph(identifier)
    if not result:
        # Try partial match
        for p in kg.list_persons():
            if identifier.lower() in p["value"].lower():
                result = kg.get_person_graph(p["value"])
                break
    if not result:
        print(f"No graph data for: {identifier}")
        return

    print(f"\n=== Knowledge Graph: {result['person']} ===")
    order = ("fact", "intent", "emotion", "behavior")
    graph = result.get("graph", {})
    for t in order:
        items = graph.get(t, [])
        if not items:
            continue
        print(f"\n  [{t.upper()}]")
        for item in sorted(items, key=lambda x: -x["mentions"]):
            dots = "●" * min(item["mentions"], 5)
            conf = f"({item['confidence']:.0%})" if item.get("confidence") else ""
            print(f"    {dots} {item['value']} {conf}")

# --------------------------------------------------------------------------
# Interactive menu
# --------------------------------------------------------------------------

_MENU = """
╔══════════════════════════════════════════╗
║       WasterWhisper — Knowledge Graph    ║
╠══════════════════════════════════════════╣
║  1. Обробити нові повідомлення (ручний)  ║
║  2. Watch-режим (кожні 30 с)             ║
║  3. Планувальник (вказати інтервал)       ║
║  4. Показати граф особи/чату             ║
║  5. Список усіх осіб у графі             ║
║  6. Статистика графу                     ║
║  7. Скинути трекінг (переобробити все)   ║
║  0. Вийти                                ║
╚══════════════════════════════════════════╝"""


def ask(prompt: str, default: str = "") -> str:
    try:
        val = input(prompt).strip()
        return val if val else default
    except (KeyboardInterrupt, EOFError):
        print()
        return default


def run_process(kg, registry):
    print(f"\n[KG] LLM:        {LLM_MODEL}")
    print(f"[KG] Embeddings: {EMBED_MODEL}\n")
    msgs, new = process_messages(kg, registry, verbose=True)
    print(f"\n[KG] Готово: оброблено {msgs} повідомлень, додано {new} нових вузлів.")
    print(kg.summary())


def run_watch(kg, registry):
    print("\n[KG] Watch-режим: перевірка кожні 30 с. Ctrl+C для зупинки.\n")
    try:
        while True:
            msgs, new = process_messages(kg, registry, verbose=False)
            registry = load_registry()
            if new:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"[KG] {ts} — +{new} нових вузлів з {msgs} повідомлень")
            time.sleep(30)
    except KeyboardInterrupt:
        print("\n[KG] Watch зупинено.")


def run_schedule(kg, registry):
    raw = ask("Інтервал у хвилинах [30]: ", "30")
    try:
        minutes = int(raw)
    except ValueError:
        print("Невірне значення, використовую 30 хв.")
        minutes = 30
    print(f"\n[KG] Планувальник: кожні {minutes} хв. Ctrl+C для зупинки.\n")
    try:
        while True:
            t0 = time.time()
            msgs, new = process_messages(kg, registry, verbose=False)
            registry = load_registry()
            elapsed = int(time.time() - t0)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[KG] {ts} — {msgs} повідомлень, +{new} вузлів ({elapsed}с). "
                  f"Наступний запуск через {minutes} хв.")
            time.sleep(minutes * 60)
    except KeyboardInterrupt:
        print("\n[KG] Планувальник зупинено.")


def run_show(kg):
    persons = kg.list_persons()
    if persons:
        print("\nДоступні особи:")
        for i, p in enumerate(sorted(persons, key=lambda x: -x.get("mentions", 0)), 1):
            print(f"  {i}. {p['value']}  (chat: {p.get('chat_id','?')})")
    identifier = ask("\nВведіть ім'я або частину імені: ")
    if identifier:
        show_graph(identifier, kg)


def run_list(kg):
    persons = kg.list_persons()
    if not persons:
        print("\nГраф порожній — ще немає оброблених повідомлень.")
        return
    print(f"\nОсоби у графі ({len(persons)}):")
    for p in sorted(persons, key=lambda x: -x.get("mentions", 0)):
        print(f"  {p['value']:<25} згадок: {p.get('mentions', 0):<4} "
              f"chat_id: {p.get('chat_id', '?')}")


def run_reset(kg):
    confirm = ask("Скинути трекінг? Всі повідомлення будуть оброблені знову [y/N]: ", "n")
    if confirm.lower() == "y":
        kg.processed = set()
        kg.save()
        print("[KG] Трекінг скинуто.")
    else:
        print("[KG] Скасовано.")


def run_analyze_frequency(kg):
    """Аналізує частоту появи сутностей у графі."""
    print("\n[KG] Аналіз частоти появи сутностей:\n")
    freq = kg.analyze_frequency()
    
    for node_type in ("fact", "intent", "emotion", "behavior"):
        items = freq.get(node_type, [])
        if not items:
            continue
        print(f"  [{node_type.upper()}] - {len(items)} сутностей:")
        for item in items[:10]:  # Показуємо перші 10
            dots = "●" * min(item["mentions"], 5)
            print(f"    {dots} {item['value']} (згадок: {item['mentions']})")
        if len(items) > 10:
            print(f"    ... та ще {len(items) - 10}")
        print()


def run_remove_noise(kg, min_mentions: int, dry_run: bool):
    """Видаляє рідкісні сутності з графу."""
    print(f"\n[KG] Видалення шуму (сутностей з < {min_mentions} згадок)...")
    
    result = kg.remove_noise(min_mentions=min_mentions, dry_run=dry_run)
    
    if dry_run:
        print(f"[KG] Dry-run: буде видалено {result['would_remove']} сутностей:")
        for item in result["items"][:20]:
            print(f"  - [{item['type']}] {item['value']} (згадок: {item['mentions']})")
        if len(result["items"]) > 20:
            print(f"  ... та ще {len(result['items']) - 20}")
    else:
        print(f"[KG] Видалено {result['removed']} сутностей:")
        for item in result["items"][:20]:
            print(f"  - [{item['type']}] {item['value']} (згадок: {item['mentions']})")
        if len(result["items"]) > 20:
            print(f"  ... та ще {len(result['items']) - 20}")
        kg.save()
        print(f"\n[KG] Граф збережено.")
        print(kg.summary())


def run_consolidate(kg, threshold: float, dry_run: bool):
    """Консолідація схожих сутностей."""
    print(f"\n[KG] Консолідація схожих сутностей (поріг: {threshold})...")
    
    result = kg.consolidate_similar(similarity_threshold=threshold, dry_run=dry_run)
    
    if dry_run:
        print(f"[KG] Dry-run: буде об'єднано {result['would_consolidate']} пар:")
        for item in result["items"][:20]:
            print(f"  - [{item['type']}] '{item['remove_value']}' -> '{item['keep_value']}' "
                  f"(схожість: {item['similarity']:.2f})")
        if len(result["items"]) > 20:
            print(f"  ... та ще {len(result['items']) - 20}")
    else:
        print(f"[KG] Об'єднано {result['consolidated']} пар:")
        for item in result["items"][:20]:
            print(f"  - [{item['type']}] '{item['remove_value']}' -> '{item['keep_value']}' "
                  f"(схожість: {item['similarity']:.2f})")
        if len(result["items"]) > 20:
            print(f"  ... та ще {len(result['items']) - 20}")
        kg.save()
        print(f"\n[KG] Граф збережено.")
        print(kg.summary())


def run_find_connections(kg, threshold: float, dry_run: bool):
    """Пошук нових зв'язків між сутностями."""
    print(f"\n[KG] Пошук нових зв'язків (поріг: {threshold})...")
    
    result = kg.find_connections(min_similarity=threshold, dry_run=dry_run)
    
    if dry_run:
        print(f"[KG] Dry-run: буде створено {result['would_connect']} нових зв'язків:")
        for item in result["items"][:20]:
            print(f"  - [{item['from_type']}] '{item['from_value']}' <-> "
                  f"[{item['to_type']}] '{item['to_value']}' "
                  f"(схожість: {item['similarity']:.2f})")
        if len(result["items"]) > 20:
            print(f"  ... та ще {len(result['items']) - 20}")
    else:
        print(f"[KG] Створено {result['connected']} нових зв'язків:")
        for item in result["items"][:20]:
            print(f"  - [{item['from_type']}] '{item['from_value']}' <-> "
                  f"[{item['to_type']}] '{item['to_value']}' "
                  f"(схожість: {item['similarity']:.2f})")
        if len(result["items"]) > 20:
            print(f"  ... та ще {len(result['items']) - 20}")
        kg.save()
        print(f"\n[KG] Граф збережено.")
        print(kg.summary())


def run_cleanup(kg, dry_run: bool):
    """Повне очищення графу: видалення шуму + консолідація."""
    print("\n[KG] Повне очищення графу...")
    print("=" * 50)
    
    # Крок 1: Видалення шуму
    print("\n[Крок 1] Видалення шуму:")
    noise_result = kg.remove_noise(min_mentions=2, dry_run=dry_run)
    
    if dry_run:
        print(f"  Dry-run: буде видалено {noise_result['would_remove']} сутностей")
    else:
        print(f"  Видалено {noise_result['removed']} сутностей")
    
    # Крок 2: Консолідація
    print("\n[Крок 2] Консолідація схожих сутностей:")
    cons_result = kg.consolidate_similar(similarity_threshold=0.85, dry_run=dry_run)
    
    if dry_run:
        print(f"  Dry-run: буде об'єднано {cons_result['would_consolidate']} пар")
    else:
        print(f"  Об'єднано {cons_result['consolidated']} пар")
    
    # Крок 3: Пошук нових зв'язків
    print("\n[Крок 3] Пошук нових зв'язків:")
    conn_result = kg.find_connections(min_similarity=0.75, dry_run=dry_run)
    
    if dry_run:
        print(f"  Dry-run: буде створено {conn_result['would_connect']} зв'язків")
    else:
        print(f"  Створено {conn_result['connected']} зв'язків")
    
    if not dry_run:
        kg.save()
        print("\n" + "=" * 50)
        print("[KG] Очищення завершено. Граф збережено.")
        print(kg.summary())
    else:
        print("\n" + "=" * 50)
        print("[KG] Dry-run завершено. Для виконання без --dry-run")


# --------------------------------------------------------------------------
# CLI entry point
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WasterWhisper Knowledge Graph Tool",
        add_help=True,
    )
    parser.add_argument("--process",  action="store_true")
    parser.add_argument("--watch",    action="store_true")
    parser.add_argument("--schedule", type=int, metavar="MINUTES")
    parser.add_argument("--show",     metavar="IDENTIFIER")
    parser.add_argument("--list",     action="store_true")
    parser.add_argument("--stats",    action="store_true")
    parser.add_argument("--reset",    action="store_true")
    args = parser.parse_args()

    kg       = KnowledgeGraph(GRAPH_PATH, EMBED_URL, EMBED_MODEL)
    registry = load_registry()

    # ------------------------------------------------------------------
    # If any flag passed — non-interactive mode (для start_all.py тощо)
    # ------------------------------------------------------------------
    if any(vars(args).values()):
        if args.reset:
            kg.processed = set()
            kg.save()
            print("[KG] Трекінг скинуто.")
        if args.stats:
            print(kg.summary())
            return
        if args.list:
            run_list(kg)
            return
        if args.show:
            show_graph(args.show, kg)
            return
        if not lm_studio_available():
            print(f"[KG] ERROR: LM Studio недоступний ({LLM_URL})")
            sys.exit(1)
        if args.process:
            run_process(kg, registry)
        elif args.schedule:
            run_schedule_direct(kg, registry, args.schedule)
        elif args.watch:
            run_watch(kg, registry)
        return

    # ------------------------------------------------------------------
    # Інтерактивне меню
    # ------------------------------------------------------------------
    print(_MENU)

    while True:
        choice = ask("\nОберіть пункт [0-7]: ")

        if choice == "0":
            print("До побачення!")
            break

        elif choice in ("4", "5", "6", "7"):
            # Ці пункти не потребують LM Studio
            if choice == "4":
                run_show(kg)
            elif choice == "5":
                run_list(kg)
            elif choice == "6":
                print()
                print(kg.summary())
            elif choice == "7":
                run_reset(kg)

        elif choice in ("1", "2", "3"):
            print(f"\n[KG] Перевірка з'єднання з LM Studio ({LLM_URL})...")
            if not lm_studio_available():
                print(f"[KG] ❌ LM Studio недоступний. Запустіть LM Studio і завантажте модель.")
                continue
            print(f"[KG] ✅ LM Studio доступний\n")

            if choice == "1":
                run_process(kg, registry)
            elif choice == "2":
                run_watch(kg, registry)
                registry = load_registry()
            elif choice == "3":
                run_schedule(kg, registry)
                registry = load_registry()

        else:
            print("Невірний вибір. Введіть число від 0 до 7.")


def run_schedule_direct(kg, registry, minutes):
    print(f"\n[KG] Планувальник: кожні {minutes} хв. Ctrl+C для зупинки.\n")
    try:
        while True:
            t0 = time.time()
            msgs, new = process_messages(kg, registry, verbose=False)
            registry = load_registry()
            elapsed = int(time.time() - t0)
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[KG] {ts} — {msgs} повідомлень, +{new} вузлів ({elapsed}с). "
                  f"Наступний через {minutes} хв.")
            time.sleep(minutes * 60)
    except KeyboardInterrupt:
        print("\n[KG] Зупинено.")


if __name__ == "__main__":
    main()
