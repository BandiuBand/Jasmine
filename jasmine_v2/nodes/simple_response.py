from jasmine_v2.core.state import JasmineState


def simple_response(state: JasmineState) -> JasmineState:
    intent = state.get("intent", "unknown")
    text = state.get("message_text", "")

    if intent == "web_search":
        response = (
            "Я бачу, що тут потрібен пошук в інтернеті. "
            "У v2-core цей tool ще не підключений, але маршрутизація уже працює."
        )

    elif intent == "memory_write":
        response = (
            "Я бачу запит на запис у памʼять. "
            "У v2-core памʼять ще не підключена, але intent визначено правильно."
        )

    elif intent == "memory_query":
        response = (
            "Я бачу запит до памʼяті. "
            "Graphiti буде підключено наступними кроками."
        )

    elif intent == "simple_chat":
        response = f"Jasmine v2-core отримала повідомлення: {text}"

    else:
        response = "Jasmine v2-core отримала подію, але не зрозуміла тип задачі."

    state["draft_response"] = response
    state.setdefault("debug_log", []).append("simple_response: ok")

    return state