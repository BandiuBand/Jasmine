import json
import os
import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


class GraphitiMemoryClient:
    """Small HTTP client for the local Graphiti memory service."""

    def __init__(self, config: Dict[str, Any]):
        self.enabled = bool(config.get("enabled", False))
        self.base_url = str(config.get("url", "http://127.0.0.1:8088")).rstrip("/")
        self.timeout = float(config.get("timeout_seconds", 450))
        self.max_results = int(config.get("max_results", 5))
        self.source_description = str(
            config.get("source_description", "telegram family chat")
        )
        self.fallback_to_legacy_kg = bool(config.get("fallback_to_legacy_kg", True))
        self.include_episode_fallback = bool(config.get("include_episode_fallback", False))

    def health(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "status": "disabled"}
        try:
            response = requests.get(f"{self.base_url}/health", timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return {"ok": data.get("status") == "ok", "data": data}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def add_episode(
        self,
        *,
        name: str,
        body: str,
        group_id: str,
        sender: str,
        reference_time: Optional[str] = None,
    ) -> bool:
        if not self.enabled or not body.strip():
            return False

        payload = {
            "name": name,
            "body": f"[{sender}] {body}",
            "source_description": self.source_description,
            "group_id": group_id,
        }
        if reference_time:
            payload["reference_time"] = reference_time

        try:
            response = requests.post(
                f"{self.base_url}/episodes",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return True
        except Exception as exc:
            print(f"[Graphiti] add_episode failed: {exc}")
            return False

    def search(self, query: str, group_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.enabled or not query.strip():
            return []
        payload = {
            "query": query,
            "group_id": canonical_graphiti_group_id(group_id),
            "limit": limit or self.max_results,
            "include_episodes": self.include_episode_fallback,
        }
        try:
            response = requests.post(
                f"{self.base_url}/search",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            return results if isinstance(results, list) else []
        except Exception as exc:
            print(f"[Graphiti] search failed: {exc}")
            return []


def graphiti_group_id(chat_id: str) -> str:
    raw = str(chat_id)
    canonical = canonical_graphiti_group_id(raw)
    if canonical.startswith("telegram_"):
        return canonical

    ascii_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_")
    if ascii_slug:
        return f"telegram_{ascii_slug}"
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"telegram_chat_{digest}"


def canonical_graphiti_group_id(group_id: str) -> str:
    raw = str(group_id).strip()
    while raw.startswith("telegram_telegram_"):
        raw = raw[len("telegram_") :]
    return raw


def message_reference_time(msg: Dict[str, Any]) -> Optional[str]:
    try:
        return datetime.strptime(
            f"{msg['date_str']} {msg['timestamp']}",
            "%Y-%m-%d %H:%M:%S",
        ).isoformat()
    except Exception:
        return None


def append_episode_queue(queue_path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(queue_path), exist_ok=True)
    with open(queue_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def format_graphiti_context(results: List[Dict[str, Any]]) -> str:
    lines = []
    seen = set()
    for result in results:
        if result.get("type") == "episode":
            fact = result.get("content") or result.get("name")
            relation = "EPISODE"
        else:
            fact = result.get("fact") or result.get("name") or json.dumps(
            result, ensure_ascii=False
            )
            relation = result.get("name")
        fact = str(fact).strip()
        if not fact or fact in seen:
            continue
        seen.add(fact)
        if relation and relation != fact:
            lines.append(f"- [{relation}] {fact}")
        else:
            lines.append(f"- {fact}")
    if not lines:
        return ""
    return "Контекст з Graphiti memory:\n" + "\n".join(lines)
