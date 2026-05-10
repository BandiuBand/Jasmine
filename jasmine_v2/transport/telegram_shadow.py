from __future__ import annotations

import logging
from typing import Any

from jasmine_v2.core.events import IncomingEvent
from jasmine_v2.core.runner import run_event

logger = logging.getLogger("jasmine_v2.shadow")


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

        print(
            f"[Jasmine v2 shadow] result: intent={result.get('intent')} "
            f"scope={result.get('scope')} response={result.get('final_response')!r}",
            flush=True,
        )

        logger.info(
            "[Jasmine v2 shadow] chat_id=%s user_id=%s intent=%s scope=%s response=%r",
            chat_id,
            user_id,
            result.get("intent"),
            result.get("scope"),
            result.get("final_response"),
        )

        debug_log = result.get("debug_log") or []
        for line in debug_log:
            print(f"[Jasmine v2 shadow debug] {line}", flush=True)
            logger.debug("[Jasmine v2 shadow] %s", line)

        return result

    except Exception as exc:
        print(f"[Jasmine v2 shadow] failed: {type(exc).__name__}: {exc}", flush=True)
        logger.exception("[Jasmine v2 shadow] failed")
        return None
