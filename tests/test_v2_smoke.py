import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.core.events import IncomingEvent
from jasmine_v2.core.runner import run_event


def test_v2_simple_chat_smoke():
    event = IncomingEvent(
        transport="test",
        chat_id="test_chat",
        user_id="user_1",
        user_name="Tester",
        text="Привіт",
    )

    result = run_event(event)

    assert result["intent"] == "simple_chat"
    assert result["final_response"]
    assert result["outgoing_messages"][0]["chat_id"] == "test_chat"

    # Memory dry-run assertions
    assert "primary_memory_space" in result
    assert "day_memory_group_id" in result
    assert "active_memory_group_ids" in result
    assert result["day_memory_write_status"] in (
        "dry_run", "written", "failed", "skipped_no_primary_space"
    )
    assert "retrieval_plan" in result

    # Active memory context assertions (not dependent on real Graphiti)
    assert "memory_read_status" in result
    assert "memory_context" in result
    assert isinstance(result["memory_context"], list)


def test_v2_web_search_routing_smoke():
    event = IncomingEvent(
        transport="test",
        chat_id="test_chat",
        user_id="user_1",
        user_name="Tester",
        text="Пошукай новини про LangGraph",
    )

    result = run_event(event)

    assert result["intent"] == "web_search"
    assert "пошук" in result["final_response"].lower()

    # Memory dry-run assertions
    assert "primary_memory_space" in result
    assert "day_memory_group_id" in result
    assert "active_memory_group_ids" in result
    assert result["day_memory_write_status"] in (
        "dry_run", "written", "failed", "skipped_no_primary_space"
    )
    assert "retrieval_plan" in result

    # Active memory context assertions (not dependent on real Graphiti)
    assert "memory_read_status" in result
    assert "memory_context" in result
    assert isinstance(result["memory_context"], list)


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("Running smoke tests")
    print("=" * 50)

    test_v2_simple_chat_smoke()
    test_v2_web_search_routing_smoke()

    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()