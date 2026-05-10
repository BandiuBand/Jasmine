from jasmine_v2.core.state import JasmineState


def finalize_response(state: JasmineState) -> JasmineState:
    response = state.get("draft_response", "").strip()

    if not response:
        response = "Jasmine v2-core: порожня відповідь."

    state["final_response"] = response
    state["outgoing_messages"] = [
        {
            "chat_id": state.get("chat_id", "unknown"),
            "text": response,
            "metadata": {
                "intent": state.get("intent"),
                "scope": state.get("scope"),
            },
        }
    ]

    state.setdefault("debug_log", []).append("finalize_response: ok")

    return state