"""Load active memory context node for Jasmine v2.

Retrieves memory context based on the retrieval plan using GraphitiV2MemoryAdapter.
"""

from jasmine_v2.core.state import JasmineState
from jasmine_v2.memory.graphiti_v2_adapter import GraphitiV2MemoryAdapter
from jasmine_v2.memory.retrieval_plan import MemoryGroupRef, RetrievalPlan
from jasmine_v2.memory.spaces import MemorySpace


def load_active_memory_context(state: JasmineState) -> JasmineState:
    """
    Load active memory context based on the retrieval plan.

    Logic:
    1. Get config from state
    2. Check if memory read is enabled (jasmine_v2.memory.read_enabled)
    3. If disabled: set status to "disabled" and return
    4. Check if retrieval_plan exists and has groups
    5. If no plan: set status to "skipped_no_plan" and return
    6. Rebuild RetrievalPlan from plain dict in state
    7. Get query from state["message_text"]
    8. Call GraphitiV2MemoryAdapter().search_context()
    9. Set status based on results: "ok", "empty", or "failed"
    10. Always add debug_log entry

    Args:
        state: The current JasmineState.

    Returns:
        Updated JasmineState with memory context and status.
    """
    # Initialize lists if not present
    state.setdefault("errors", [])
    state.setdefault("debug_log", [])

    # 1. Get config from state
    config = state.get("config", {})

    # 2. Check if memory read is enabled
    read_enabled = config.get("jasmine_v2", {}).get("memory", {}).get("read_enabled", False)

    # 3. If read_enabled is not True
    if read_enabled is not True:
        state["memory_read_status"] = "disabled"
        state["memory_context"] = []
        state["debug_log"].append("load_active_memory_context: status=disabled (read_enabled not True)")
        return state

    # 4. Check if retrieval_plan exists and has groups
    retrieval_plan_data = state.get("retrieval_plan")
    if not retrieval_plan_data or not retrieval_plan_data.get("groups"):
        state["memory_read_status"] = "skipped_no_plan"
        state["memory_context"] = []
        state["debug_log"].append("load_active_memory_context: status=skipped_no_plan (no retrieval_plan or groups)")
        return state

    # 5. Rebuild RetrievalPlan from plain dict
    try:
        primary_space_data = retrieval_plan_data.get("primary_space", {})
        primary_space = MemorySpace(
            space_type=primary_space_data.get("space_type", "chat"),
            space_id=primary_space_data.get("space_id", "unknown"),
        )

        groups_data = retrieval_plan_data.get("groups", [])
        groups = [
            MemoryGroupRef(
                group_id=group.get("group_id", ""),
                role=group.get("role", "secondary"),
                weight=group.get("weight", 0.5),
                reason=group.get("reason"),
            )
            for group in groups_data
        ]

        plan = RetrievalPlan(primary_space=primary_space, groups=groups)
    except Exception as e:
        state["memory_read_status"] = "failed"
        state["memory_context"] = []
        state["errors"].append(f"load_active_memory_context: failed to rebuild retrieval plan: {e}")
        state["debug_log"].append(f"load_active_memory_context: status=failed (plan rebuild error), groups=0, items=0")
        return state

    # 6. Get query from state
    query = state.get("message_text", "")

    # 7. Call search_context
    try:
        adapter = GraphitiV2MemoryAdapter()
        results = adapter.search_context(
            plan=plan,
            query=query,
            limit=10,
            include_episodes=True,
        )

        # 8 & 9. Set status based on results
        if results:
            state["memory_read_status"] = "ok"
            state["memory_context"] = results
        else:
            state["memory_read_status"] = "empty"
            state["memory_context"] = []

        # 10. Add debug_log
        state["debug_log"].append(
            f"load_active_memory_context: status={state['memory_read_status']}, groups={len(groups)}, items={len(results)}"
        )

    except Exception as e:
        # 10. If exception: status=failed, add error, don't raise
        state["memory_read_status"] = "failed"
        state["memory_context"] = []
        state["errors"].append(f"load_active_memory_context: search_context failed: {e}")
        state["debug_log"].append(
            f"load_active_memory_context: status=failed, groups={len(groups)}, items=0"
        )

    return state
