"""Tests for GraphitiV2MemoryAdapter.

Run directly: python3 tests/test_v2_graphiti_v2_adapter.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.memory.graphiti_v2_adapter import GraphitiV2MemoryAdapter
from jasmine_v2.memory.spaces import make_chat_space


class FakeGraphitiClient:
    """Fake Graphiti HTTP client for testing."""

    def __init__(self):
        self.add_episode_calls = []
        self.search_calls = []
        self.search_response = {"results": []}

    def add_episode(self, name, body, group_id, source_description, reference_time=None):
        """Record add_episode call and return mock response."""
        call = {
            "name": name,
            "body": body,
            "group_id": group_id,
            "source_description": source_description,
            "reference_time": reference_time,
        }
        self.add_episode_calls.append(call)
        return {"status": "ok", "episode_id": f"ep_{len(self.add_episode_calls)}"}

    def search(self, query, group_ids, limit=10, include_episodes=True):
        """Record search call and return configured response."""
        call = {
            "query": query,
            "group_ids": group_ids,
            "limit": limit,
            "include_episodes": include_episodes,
        }
        self.search_calls.append(call)
        return self.search_response


def test_get_day_group_id():
    """Test 1: get_day_group_id for make_chat_space('Telegram Family Main') on 2026-05-10T14:22:00Z."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    space = make_chat_space("Telegram Family Main")
    dt = "2026-05-10T14:22:00Z"

    group_id = adapter.get_day_group_id(space, dt)

    expected = "jv2:chat:telegram_family_main:day:2026-05-10"
    assert group_id == expected, f"Expected {expected!r}, got {group_id!r}"

    print("✓ test_get_day_group_id passed")


def test_build_retrieval_plan():
    """Test 2: build_retrieval_plan includes day/week/month/longterm groups."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    space = make_chat_space("Test Chat")
    dt = "2026-05-10T14:22:00Z"

    plan = adapter.build_retrieval_plan(space, dt=dt)

    # Check all time levels are present
    group_ids = plan.group_ids
    assert any(":day:" in gid for gid in group_ids), "Missing day group"
    assert any(":week:" in gid for gid in group_ids), "Missing week group"
    assert any(":month:" in gid for gid in group_ids), "Missing month group"
    assert any(":longterm:" in gid for gid in group_ids), "Missing longterm group"

    print("✓ test_build_retrieval_plan passed")


def test_format_message_episode():
    """Test 3: format_message_episode includes required fields."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    space = make_chat_space("Test Chat")
    group_id = "jv2:chat:test_chat:day:2026-05-10"

    body = adapter.format_message_episode(
        text="Hello world",
        space=space,
        group_id=group_id,
        access_scope="family",
        timestamp="2026-05-10T14:22:00Z",
        sender_name="Alice",
    )

    # Check required fields are present
    assert "Telegram message" in body
    assert "access_scope: family" in body
    assert "memory_space: chat:test_chat" in body
    assert f"group_id: {group_id}" in body
    assert "timestamp: 2026-05-10T14:22:00Z" in body
    assert "sender_name: Alice" in body
    assert "Text:\nHello world" in body

    print("✓ test_format_message_episode passed")


def test_add_day_message_episode_calls_client():
    """Test 4: add_day_message_episode calls fake_client.add_episode with day group."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    space = make_chat_space("Test Chat")

    adapter.add_day_message_episode(
        text="Test message",
        space=space,
        access_scope="family",
        timestamp="2026-05-10T14:22:00Z",
        chat_id="12345",
        message_id="67890",
        sender_name="Bob",
    )

    # Check that add_episode was called
    assert len(fake_client.add_episode_calls) == 1, "add_episode was not called"

    call = fake_client.add_episode_calls[0]

    # Check group_id is a day group
    assert ":day:" in call["group_id"], f"Expected day group, got {call['group_id']}"

    print("✓ test_add_day_message_episode_calls_client passed")


def test_add_day_message_episode_reference_time():
    """Test 5: add_day_message_episode passes reference_time."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    space = make_chat_space("Test Chat")
    timestamp = "2026-05-10T14:22:00Z"

    adapter.add_day_message_episode(
        text="Test message",
        space=space,
        access_scope="family",
        timestamp=timestamp,
    )

    call = fake_client.add_episode_calls[0]
    assert call["reference_time"] == timestamp, f"Expected {timestamp!r}, got {call['reference_time']!r}"

    print("✓ test_add_day_message_episode_reference_time passed")


def test_search_context_calls_client():
    """Test 6: search_context calls fake_client.search with plan.group_ids."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    space = make_chat_space("Test Chat")
    plan = adapter.build_retrieval_plan(space, dt="2026-05-10T14:22:00Z")

    adapter.search_context(plan, "test query", limit=5)

    # Check that search was called
    assert len(fake_client.search_calls) == 1, "search was not called"

    call = fake_client.search_calls[0]

    # Check group_ids match the plan
    assert call["group_ids"] == plan.group_ids, f"Expected {plan.group_ids}, got {call['group_ids']}"
    assert call["query"] == "test query"
    assert call["limit"] == 5

    print("✓ test_search_context_calls_client passed")


def test_search_context_normalizes_results():
    """Test 7: search_context normalizes response with results field."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    # Set up response with "results" field
    fake_client.search_response = {
        "results": [
            {"text": "Result 1", "group_id": "jv2:chat:test:day:2026-05-10", "score": 0.9},
            {"text": "Result 2", "group_id": "jv2:chat:test:week:2026-W19", "score": 0.8},
        ]
    }

    space = make_chat_space("Test Chat")
    plan = adapter.build_retrieval_plan(space)

    results = adapter.search_context(plan, "test query")

    # Check normalization
    assert len(results) == 2
    assert results[0]["text"] == "Result 1"
    assert results[0]["source"] == "graphiti"
    assert results[0]["group_id"] == "jv2:chat:test:day:2026-05-10"
    assert results[0]["score"] == 0.9
    assert "metadata" in results[0]

    print("✓ test_search_context_normalizes_results passed")


def test_search_context_unknown_response_shape():
    """Test 8: search_context for unknown response shape returns empty list."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    # Set up unexpected response shape
    fake_client.search_response = {"unexpected_field": "value"}

    space = make_chat_space("Test Chat")
    plan = adapter.build_retrieval_plan(space)

    results = adapter.search_context(plan, "test query")

    assert results == [], f"Expected empty list, got {results}"

    print("✓ test_search_context_unknown_response_shape passed")


def test_search_context_normalizes_facts_field():
    """Test: search_context normalizes response with facts field."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    fake_client.search_response = {
        "facts": [
            {"body": "Fact 1", "group_id": "g1", "relevance": 0.95},
        ]
    }

    space = make_chat_space("Test Chat")
    plan = adapter.build_retrieval_plan(space)

    results = adapter.search_context(plan, "test")

    assert len(results) == 1
    assert results[0]["text"] == "Fact 1"
    assert results[0]["score"] == 0.95

    print("✓ test_search_context_normalizes_facts_field passed")


def test_search_context_normalizes_episodes_field():
    """Test: search_context normalizes response with episodes field."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    fake_client.search_response = {
        "episodes": [
            {"content": "Episode 1", "group_id": "g1", "score": 0.88},
        ]
    }

    space = make_chat_space("Test Chat")
    plan = adapter.build_retrieval_plan(space)

    results = adapter.search_context(plan, "test")

    assert len(results) == 1
    assert results[0]["text"] == "Episode 1"
    assert results[0]["score"] == 0.88

    print("✓ test_search_context_normalizes_episodes_field passed")


def test_search_context_handles_list_response():
    """Test: search_context handles response as direct list."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    fake_client.search_response = [
        {"text": "Direct item", "group_id": "g1", "score": 0.77},
    ]

    space = make_chat_space("Test Chat")
    plan = adapter.build_retrieval_plan(space)

    results = adapter.search_context(plan, "test")

    assert len(results) == 1
    assert results[0]["text"] == "Direct item"

    print("✓ test_search_context_handles_list_response passed")


def test_add_day_message_episode_name_with_chat_and_message_id():
    """Test: add_day_message_episode builds name with chat_id and message_id."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    space = make_chat_space("Test Chat")

    adapter.add_day_message_episode(
        text="Test",
        space=space,
        access_scope="family",
        timestamp="2026-05-10T14:22:00Z",
        chat_id="12345",
        message_id="67890",
    )

    call = fake_client.add_episode_calls[0]
    assert call["name"] == "telegram:12345:67890", f"Expected 'telegram:12345:67890', got {call['name']!r}"

    print("✓ test_add_day_message_episode_name_with_chat_and_message_id passed")


def test_add_day_message_episode_name_without_chat_and_message_id():
    """Test: add_day_message_episode builds name with space and timestamp."""
    fake_client = FakeGraphitiClient()
    adapter = GraphitiV2MemoryAdapter(client=fake_client)

    space = make_chat_space("Test Chat")

    adapter.add_day_message_episode(
        text="Test",
        space=space,
        access_scope="family",
        timestamp="2026-05-10T14:22:00Z",
    )

    call = fake_client.add_episode_calls[0]
    expected_name = "telegram:chat:test_chat:2026-05-10T14:22:00Z"
    assert call["name"] == expected_name, f"Expected {expected_name!r}, got {call['name']!r}"

    print("✓ test_add_day_message_episode_name_without_chat_and_message_id passed")


def run_all_tests():
    """Run all tests."""
    print("Running GraphitiV2MemoryAdapter tests...\n")

    test_get_day_group_id()
    test_build_retrieval_plan()
    test_format_message_episode()
    test_add_day_message_episode_calls_client()
    test_add_day_message_episode_reference_time()
    test_search_context_calls_client()
    test_search_context_normalizes_results()
    test_search_context_unknown_response_shape()
    test_search_context_normalizes_facts_field()
    test_search_context_normalizes_episodes_field()
    test_search_context_handles_list_response()
    test_add_day_message_episode_name_with_chat_and_message_id()
    test_add_day_message_episode_name_without_chat_and_message_id()

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    run_all_tests()
