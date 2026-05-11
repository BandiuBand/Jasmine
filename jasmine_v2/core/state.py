from typing import Any, Literal, TypedDict


Scope = Literal["private", "family", "system", "unknown"]

DayMemoryWriteStatus = Literal["dry_run", "skipped_no_primary_space", "pending", "written", "failed"]
MemoryReadStatus = Literal["disabled", "skipped_no_plan", "ok", "empty", "failed"]
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

    # Config (passed from outside, not read from disk)
    config: dict[str, Any]

    # Context/memory placeholder
    memory_context: list[dict[str, Any]]
    memory_read_status: MemoryReadStatus
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

    # Memory space
    primary_memory_space: dict[str, Any]

    # Day memory dry run
    day_memory_group_id: str
    active_memory_group_ids: list[str]
    retrieval_plan: dict[str, Any]
    day_memory_write_status: DayMemoryWriteStatus
    day_memory_write_result: dict[str, Any] | None