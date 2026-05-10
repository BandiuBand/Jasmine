from jasmine_v2.core.state import JasmineState


def normalize_event(state: JasmineState) -> JasmineState:
    event = state.get("event", {})

    state["transport"] = event.get("transport", "unknown")
    state["chat_id"] = str(event.get("chat_id", "unknown"))
    state["user_id"] = str(event.get("user_id", "unknown"))
    state["user_name"] = event.get("user_name")
    state["message_text"] = (event.get("text") or "").strip()

    state.setdefault("errors", [])
    state.setdefault("debug_log", [])
    state["debug_log"].append("normalize_event: ok")

    return state