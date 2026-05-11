"""Day memory ingest node for Jasmine v2.

Builds a retrieval plan and optionally writes the message to Graphiti day memory.
This node reads config from state["config"] only — no env vars, no disk reads.
"""

from jasmine_v2.core.state import JasmineState
from jasmine_v2.memory.graph_scope import get_active_group_ids, make_day_scope
from jasmine_v2.memory.graphiti_v2_adapter import GraphitiV2MemoryAdapter
from jasmine_v2.memory.retrieval_plan import build_default_retrieval_plan
from jasmine_v2.memory.spaces import MemorySpace


def day_memory_ingest(state: JasmineState) -> JasmineState:
    """
    Build day memory plan and optionally write to Graphiti.

    Logic:
    1. Read primary_memory_space from state.
    2. If missing: set status to "skipped_no_primary_space" and return.
    3. Build MemorySpace from primary_memory_space.
    4. Get timestamp from state["event"]["timestamp"] if available.
    5. Build day_scope, active group IDs, and retrieval plan.
    6. Write plan fields to state.
    7. Read write_enabled from state["config"]["jasmine_v2"]["memory"]["day_write_enabled"].
    8. If not True: status = "dry_run", debug_log, return.
    9. If True: call GraphitiV2MemoryAdapter().add_day_message_episode(...).
    10. On success: status = "written", store result, debug_log.
    11. On exception: status = "failed", add error to state["errors"], debug_log,
        do not raise.

    Args:
        state: The current JasmineState.

    Returns:
        Updated JasmineState with day memory ingest results.
    """
    # 1. Read primary_memory_space
    primary_space_data = state.get("primary_memory_space")

    # 2. If missing
    if not primary_space_data:
        state["day_memory_write_status"] = "skipped_no_primary_space"
        state["day_memory_group_id"] = ""
        state["active_memory_group_ids"] = []
        state["retrieval_plan"] = {}
        state.setdefault("debug_log", []).append(
            "day_memory_ingest: skipped_no_primary_space"
        )
        return state

    # 3. Build MemorySpace
    space = MemorySpace(
        space_type=primary_space_data["space_type"],
        space_id=primary_space_data["space_id"],
    )

    # 4. Get timestamp from event
    timestamp = None
    event = state.get("event", {})
    if isinstance(event, dict):
        timestamp = event.get("timestamp")

    # 5. Build day scope, active groups, retrieval plan
    day_scope = make_day_scope(space, timestamp)
    day_memory_group_id = day_scope.graph_id
    active_memory_group_ids = get_active_group_ids(space, timestamp)
    plan = build_default_retrieval_plan(space, dt=timestamp)

    # 6. Convert plan to plain dict and write to state
    retrieval_plan = {
        "primary_space": {
            "space_type": plan.primary_space.space_type,
            "space_id": plan.primary_space.space_id,
            "key": plan.primary_space.key,
        },
        "groups": [
            {
                "group_id": group.group_id,
                "role": group.role,
                "weight": group.weight,
                "reason": group.reason,
            }
            for group in plan.groups
        ],
    }

    state["day_memory_group_id"] = day_memory_group_id
    state["active_memory_group_ids"] = active_memory_group_ids
    state["retrieval_plan"] = retrieval_plan

    # 7. Read write_enabled from config
    write_enabled = (
        state.get("config", {})
        .get("jasmine_v2", {})
        .get("memory", {})
        .get("day_write_enabled", False)
    )

    # 8. If not True
    if write_enabled is not True:
        state["day_memory_write_status"] = "dry_run"
        state.setdefault("debug_log", []).append(
            f"day_memory_ingest: dry_run group={day_memory_group_id}"
        )
        return state

    # 9. If True, call adapter
    try:
        adapter = GraphitiV2MemoryAdapter()
        result = adapter.add_day_message_episode(
            space=space,
            text=state.get("message_text", ""),
            access_scope=state.get("scope", "unknown"),
            timestamp=timestamp,
            source=state.get("transport", "unknown"),
            chat_id=state.get("chat_id"),
            message_id=state.get("event", {}).get("raw", {}).get("message_id"),
            sender_id=state.get("user_id"),
            sender_name=state.get("user_name"),
            metadata={
                "transport": state.get("transport"),
                "intent": state.get("intent"),
            },
        )

        # 10. Success
        state["day_memory_write_status"] = "written"
        state["day_memory_write_result"] = result
        state.setdefault("debug_log", []).append(
            f"day_memory_ingest: written group={day_memory_group_id}"
        )
    except Exception as e:
        # 11. Exception — catch, log, do not raise
        state["day_memory_write_status"] = "failed"
        state.setdefault("errors", []).append(str(e))
        state.setdefault("debug_log", []).append(
            f"day_memory_ingest: failed group={day_memory_group_id}, error={e}"
        )

    return state
