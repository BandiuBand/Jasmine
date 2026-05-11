from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from jasmine_v2.core.events import IncomingEvent
from jasmine_v2.core.runner import run_event

logger = logging.getLogger("jasmine_v2.shadow")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SHADOW_LOG_FILE = os.path.join(_BASE_DIR, "logs", "jasmine_v2_shadow.log")
_SNAPSHOT_DIR = os.path.join(_BASE_DIR, "data", "v2_shadow_events")


def _write_shadow_log(
    timestamp: str,
    chat_id: str,
    user_id: str,
    intent: str,
    confidence: float,
    message: str,
    response: str,
    primary_memory_space: dict[str, Any] | None = None,
    day_memory_group_id: str = "",
    active_groups_count: int = 0,
    day_memory_write_status: str = "",
) -> None:
    """Append structured line to shadow log file."""
    try:
        os.makedirs(os.path.dirname(_SHADOW_LOG_FILE), exist_ok=True)
        primary_key = primary_memory_space.get("key", "N/A") if primary_memory_space else "N/A"
        with open(_SHADOW_LOG_FILE, "a", encoding="utf-8") as f:
            line = (
                f"{timestamp}\t{chat_id}\t{user_id}\t{intent}\t{confidence}\t"
                f"{message[:200]!r}\t{response[:200]!r}\t"
                f"{primary_key}\t{day_memory_group_id}\t{active_groups_count}\t{day_memory_write_status}\n"
            )
            f.write(line)
    except Exception as e:
        print(f"[Jasmine v2 shadow] log write failed: {e}", flush=True)


def _write_snapshot(
    timestamp: str,
    chat_id: str,
    user_id: str,
    message_text: str,
    intent: str,
    scope: str,
    debug_log: list[str],
    raw: dict[str, Any] | None,
    primary_memory_space: dict[str, Any] | None = None,
    day_memory_group_id: str = "",
    active_memory_group_ids: list[str] | None = None,
    day_memory_write_status: str = "",
) -> None:
    """Write JSON snapshot of the shadow event."""
    try:
        os.makedirs(_SNAPSHOT_DIR, exist_ok=True)
        safe_ts = timestamp.replace(":", "-").replace(" ", "_")
        filename = f"{safe_ts}_{chat_id}_{user_id}.json"
        filepath = os.path.join(_SNAPSHOT_DIR, filename)

        data = {
            "timestamp": timestamp,
            "chat_id": chat_id,
            "user_id": user_id,
            "message_text": message_text,
            "intent": intent,
            "scope": scope,
            "debug_log": debug_log,
            "raw": raw or {},
            "primary_memory_space": primary_memory_space,
            "day_memory_group_id": day_memory_group_id,
            "active_memory_group_ids": active_memory_group_ids or [],
            "day_memory_write_status": day_memory_write_status,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Jasmine v2 shadow] snapshot write failed: {e}", flush=True)


def run_telegram_shadow_event(
    *,
    chat_id: str | int,
    user_id: str | int,
    user_name: str | None,
    text: str,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Проганяє Telegram-повідомлення через Jasmine v2-core у shadow mode.

    ВАЖЛИВО:
    - нічого не відправляє в Telegram;
    - не впливає на стару логіку;
    - не кидає exception назовні;
    - тільки повертає result і пише лог.
    """

    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        print(
            f"[Jasmine v2 shadow] received: chat_id={chat_id} "
            f"user_id={user_id} text={text[:120]!r}",
            flush=True,
        )

        event = IncomingEvent(
            transport="telegram_shadow",
            chat_id=str(chat_id),
            user_id=str(user_id),
            user_name=user_name,
            text=text,
            raw=raw or {},
        )

        result = run_event(event)
        intent = result.get("intent", "unknown")
        scope = result.get("scope", "unknown")
        confidence = result.get("intent_confidence", 0.0)
        final_response = result.get("final_response", "")
        debug_log = result.get("debug_log") or []
        primary_memory_space = result.get("primary_memory_space")
        day_memory_group_id = result.get("day_memory_group_id", "")
        active_memory_group_ids = result.get("active_memory_group_ids") or []
        day_memory_write_status = result.get("day_memory_write_status", "")

        print(
            f"[Jasmine v2 shadow] result: intent={intent} "
            f"scope={scope} response={final_response!r}",
            flush=True,
        )

        # Write to shadow log file
        _write_shadow_log(
            timestamp=timestamp,
            chat_id=str(chat_id),
            user_id=str(user_id),
            intent=str(intent),
            confidence=float(confidence),
            message=text,
            response=final_response,
            primary_memory_space=primary_memory_space,
            day_memory_group_id=day_memory_group_id,
            active_groups_count=len(active_memory_group_ids),
            day_memory_write_status=day_memory_write_status,
        )

        # Write JSON snapshot
        _write_snapshot(
            timestamp=timestamp,
            chat_id=str(chat_id),
            user_id=str(user_id),
            message_text=text,
            intent=str(intent),
            scope=str(scope),
            debug_log=debug_log,
            raw=raw,
            primary_memory_space=primary_memory_space,
            day_memory_group_id=day_memory_group_id,
            active_memory_group_ids=active_memory_group_ids,
            day_memory_write_status=day_memory_write_status,
        )

        logger.info(
            "[Jasmine v2 shadow] chat_id=%s user_id=%s intent=%s scope=%s response=%r",
            chat_id,
            user_id,
            intent,
            scope,
            final_response,
        )

        for line in debug_log:
            print(f"[Jasmine v2 shadow debug] {line}", flush=True)
            logger.debug("[Jasmine v2 shadow] %s", line)

        return result

    except Exception as exc:
        print(f"[Jasmine v2 shadow] failed: {type(exc).__name__}: {exc}", flush=True)
        logger.exception("[Jasmine v2 shadow] failed")
        return None
