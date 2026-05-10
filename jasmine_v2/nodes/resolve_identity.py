from jasmine_v2.core.state import JasmineState


def resolve_identity(state: JasmineState) -> JasmineState:
    chat_id = state.get("chat_id", "")

    # Тимчасова логіка.
    # Потім тут буде users/scopes/permissions.
    if chat_id.startswith("family") or chat_id == "family":
        state["scope"] = "family"
    else:
        state["scope"] = "private"

    state["permissions"] = ["chat"]

    if state.get("user_id") not in ("unknown", ""):
        state["permissions"].append("user_known")

    state.setdefault("debug_log", []).append(
        f"resolve_identity: scope={state['scope']}, permissions={state['permissions']}"
    )

    return state