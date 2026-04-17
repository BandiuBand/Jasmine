#!/usr/bin/env python3
"""
Автоматичне очищення графу знань по таймеру.

Запускається з start_all.py якщо увімкнено в config.json
"""

import json
import os
import sys
import time
from datetime import datetime

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _BASE_DIR)

from kg.store import KnowledgeGraph

_CONFIG_FILE = os.path.join(_BASE_DIR, "config.json")
_GRAPH_PATH = os.path.join(_BASE_DIR, "kg", "graph.json")
_EMBED_URL = os.getenv("EMBED_URL", "http://127.0.0.1:1234/v1/embeddings")
_EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-nomic-embed-text-v1.5")


def load_config() -> dict:
    """Завантажує конфігурацію з config.json"""
    if os.path.exists(_CONFIG_FILE):
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def run_cleanup(kg: KnowledgeGraph, config: dict, dry_run: bool = False):
    """Виконує повне очищення графу"""
    min_mentions = config.get("min_mentions", 2)
    consolidate_threshold = config.get("consolidate_threshold", 0.85)
    connections_threshold = config.get("connections_threshold", 0.75)
    
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{ts}] Початок очищення графу...")
    
    # Крок 1: Видалення шуму
    noise_result = kg.remove_noise(
        min_mentions=min_mentions,
        dry_run=dry_run
    )
    print(f"  Видалення шуму: {noise_result['would_remove' if dry_run else 'removed']} сутностей")
    
    # Крок 2: Консолідація
    cons_result = kg.consolidate_similar(
        similarity_threshold=consolidate_threshold,
        dry_run=dry_run
    )
    print(f"  Консолідація: {cons_result['would_consolidate' if dry_run else 'consolidated']} пар")
    
    # Крок 3: Пошук нових зв'язків
    conn_result = kg.find_connections(
        min_similarity=connections_threshold,
        dry_run=dry_run
    )
    print(f"  Нові зв'язки: {conn_result['would_connect' if dry_run else 'connected']}")
    
    if not dry_run:
        kg.save()
        print(f"[{ts}] Очищення завершено. Граф збережено.")
    else:
        print(f"[{ts}] Dry-run завершено.")
    
    return {
        "noise": noise_result,
        "consolidate": cons_result,
        "connections": conn_result
    }


def main():
    config = load_config()
    cleanup_config = config.get("kg_cleanup", {})
    
    if not cleanup_config.get("enabled", False):
        print("[KG Cleanup] Вимкнено в config.json")
        return
    
    interval_minutes = cleanup_config.get("interval_minutes", 60)
    dry_run = cleanup_config.get("dry_run", False)
    
    kg = KnowledgeGraph(_GRAPH_PATH, _EMBED_URL, _EMBED_MODEL)
    
    print(f"[KG Cleanup] Запущено з інтервалом {interval_minutes} хв")
    print(f"[KG Cleanup] Dry-run режим: {dry_run}")
    
    try:
        while True:
            run_cleanup(kg, cleanup_config, dry_run=dry_run)
            
            print(f"[KG Cleanup] Наступний запуск через {interval_minutes} хв...")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("\n[KG Cleanup] Зупинено")


if __name__ == "__main__":
    main()
