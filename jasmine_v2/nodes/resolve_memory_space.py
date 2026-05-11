"""Resolve primary memory space for the current event."""

from jasmine_v2.core.state import JasmineState
from jasmine_v2.memory.spaces import make_chat_space, make_user_space


def resolve_memory_space(state: JasmineState) -> JasmineState:
    """
    Resolve the primary memory space based on transport and chat type.

    Logic:
    1. If telegram/supergroup: chat:telegram_family_main
    2. If telegram/private: chat:telegram_private_{user_id}
    3. If cli: user:{user_id} or user:local_user
    4. Otherwise: chat:{transport}_{chat_id}
    """
    transport = state.get("transport", "")
    chat_id = state.get("chat_id", "")
    user_id = state.get("user_id", "")

    # Get raw event data if available
    event = state.get("event", {})
    raw = event.get("raw", {}) if isinstance(event, dict) else {}

    # Determine chat_type from raw data
    chat_type = ""
    if isinstance(raw, dict):
        chat_type = raw.get("chat_type", "")

    # Apply logic based on transport and chat_type
    if transport in ("telegram", "telegram_shadow"):
        if chat_type in ("group", "supergroup"):
            primary = make_chat_space("telegram_family_main")
        elif chat_type == "private":
            primary = make_chat_space(f"telegram_private_{user_id}")
        else:
            # Fallback for telegram without recognized chat_type
            primary = make_chat_space(f"{transport}_{chat_id}")
    elif transport == "cli":
        primary = make_user_space(user_id or "local_user")
    else:
        # Fallback for unknown transport
        primary = make_chat_space(f"{transport}_{chat_id}")

    # Write to state
    state["primary_memory_space"] = {
        "space_type": primary.space_type,
        "space_id": primary.space_id,
        "key": primary.key,
    }

    # Add debug log
    state.setdefault("debug_log", []).append(
        f"resolve_memory_space: primary={primary.key}"
    )

    return state
