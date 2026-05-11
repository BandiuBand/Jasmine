"""Day memory dry run node for Jasmine v2.

Builds a retrieval plan for day memory without writing to Graphiti.
This is a pure logic node that prepares memory context parameters.
"""

from jasmine_v2.core.state import JasmineState
from jasmine_v2.memory.graph_scope import get_active_group_ids, make_day_scope
from jasmine_v2.memory.retrieval_plan import build_default_retrieval_plan
from jasmine_v2.memory.spaces import MemorySpace


def day_memory_dry_run(state: JasmineState) -> JasmineState:
    """
    Build a day memory dry run plan without writing to Graphiti.

    Logic:
    1. Read state["primary_memory_space"]
    2. If missing: set status to "skipped_no_primary_space" and return
    3. Build MemorySpace from primary_memory_space
    4. Get timestamp from state["event"]["timestamp"] if available
    5. Build day_scope and retrieval plan
    6. Write results to state

    Args:
        state: The current JasmineState.

    Returns:
        Updated JasmineState with day memory dry run results.
    """
    # Check for primary_memory_space
    primary_space_data = state.get("primary_memory_space")
    if not primary_space_data:
        state["day_memory_write_status"] = "skipped_no_primary_space"
        state.setdefault("debug_log", []).append(
            "day_memory_dry_run: skipped_no_primary_space"
        )
        return state

    # Build MemorySpace from primary_memory_space data
    space = MemorySpace(
        space_type=primary_space_data["space_type"],
        space_id=primary_space_data["space_id"],
    )

    # Get timestamp from event if available
    timestamp = None
    event = state.get("event", {})
    if isinstance(event, dict):
        timestamp = event.get("timestamp")

    # Build day scope
    day_scope = make_day_scope(space, timestamp)
    day_memory_group_id = day_scope.graph_id

    # Get active group IDs (day, week, month, longterm)
    active_memory_group_ids = get_active_group_ids(space, timestamp)

    # Build retrieval plan
    plan = build_default_retrieval_plan(space, dt=timestamp)

    # Convert plan to plain dict
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

    # Write to state
    state["day_memory_group_id"] = day_memory_group_id
    state["active_memory_group_ids"] = active_memory_group_ids
    state["retrieval_plan"] = retrieval_plan
    state["day_memory_write_status"] = "dry_run"

    # Add debug log
    state.setdefault("debug_log", []).append(
        f"day_memory_dry_run: day_group={day_memory_group_id}, active_groups={len(active_memory_group_ids)}"
    )

    return state
