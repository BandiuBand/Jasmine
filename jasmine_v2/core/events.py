from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class IncomingEvent:
    """
    Уніфікована вхідна подія.

    Transport layer — Telegram, CLI, Web, Discord — має перетворити
    свої сирі події саме в цей формат.
    """

    transport: str
    chat_id: str
    user_id: str
    user_name: str | None
    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attachments: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutgoingMessage:
    """
    Уніфіковане вихідне повідомлення.

    LangGraph-core не має знати, Telegram це чи CLI.
    """

    chat_id: str
    text: str
    reply_to_message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)