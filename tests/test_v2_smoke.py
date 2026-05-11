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
    assert result["day_memory_write_status"] == "dry_run"


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
    assert result["day_memory_write_status"] == "dry_run"