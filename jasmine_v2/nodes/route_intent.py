from jasmine_v2.core.state import JasmineState


def route_intent(state: JasmineState) -> JasmineState:
    text = state.get("message_text", "").lower()

    if not text:
        state["intent"] = "unknown"
        state["intent_confidence"] = 0.0

    elif any(word in text for word in ["пошукай", "знайди в інтернеті", "новини", "погода"]):
        state["intent"] = "web_search"
        state["intent_confidence"] = 0.7

    elif any(word in text for word in ["запамʼятай", "запам'ятай", "remember"]):
        state["intent"] = "memory_write"
        state["intent_confidence"] = 0.7

    elif any(word in text for word in ["що ти памʼятаєш", "що ти пам'ятаєш", "memory"]):
        state["intent"] = "memory_query"
        state["intent_confidence"] = 0.7

    else:
        state["intent"] = "simple_chat"
        state["intent_confidence"] = 0.6

    state.setdefault("debug_log", []).append(
        f"route_intent: intent={state['intent']}, confidence={state['intent_confidence']}"
    )

    return state