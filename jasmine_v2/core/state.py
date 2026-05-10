from typing import Any, Literal, TypedDict


Scope = Literal["private", "family", "system", "unknown"]
Intent = Literal[
    "simple_chat",
    "memory_query",
    "memory_write",
    "web_search",
    "tool_request",
    "admin_command",
    "unknown",
]


class JasmineState(TypedDict, total=False):
    # Input/event
    event: dict[str, Any]
    transport: str
    chat_id: str
    user_id: str
    user_name: str | None
    message_text: str

    # Identity/scope
    scope: Scope
    permissions: list[str]

    # Routing
    intent: Intent
    intent_confidence: float

    # Context/memory placeholder
    memory_context: list[dict[str, Any]]
    conversation_context: list[dict[str, Any]]

    # Execution
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]

    # Output
    draft_response: str
    final_response: str
    outgoing_messages: list[dict[str, Any]]

    # Debug
    errors: list[str]
    debug_log: list[str]