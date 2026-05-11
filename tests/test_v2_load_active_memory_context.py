"""Tests for load_active_memory_context node."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.nodes.load_active_memory_context import load_active_memory_context
from jasmine_v2.core.state import JasmineState


class FakeGraphitiV2MemoryAdapter:
    """Fake adapter for testing without real Graphiti."""

    def __init__(self, return_results=None, raise_exception=None):
        self.return_results = return_results or []
        self.raise_exception = raise_exception

    def search_context(self, plan, query, limit=10, include_episodes=True):
        if self.raise_exception:
            raise self.raise_exception
        return self.return_results


def test_config_missing():
    """Test status is 'disabled' when config is missing."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "message_text": "Hello",
        # No config
    }

    result = load_active_memory_context(state)

    assert result["memory_read_status"] == "disabled", (
        f"Expected 'disabled', got {result.get('memory_read_status')}"
    )
    assert result["memory_context"] == [], "memory_context should be empty"
    print("✓ config missing -> disabled")


def test_config_read_enabled_false():
    """Test status is 'disabled' when read_enabled=false."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "message_text": "Hello",
        "config": {
            "jasmine_v2": {
                "memory": {
                    "read_enabled": False
                }
            }
        },
    }

    result = load_active_memory_context(state)

    assert result["memory_read_status"] == "disabled", (
        f"Expected 'disabled', got {result.get('memory_read_status')}"
    )
    assert result["memory_context"] == [], "memory_context should be empty"
    print("✓ read_enabled=false -> disabled")


def test_config_read_enabled_true_no_plan():
    """Test status is 'skipped_no_plan' when read_enabled=true but no retrieval_plan."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "message_text": "Hello",
        "config": {
            "jasmine_v2": {
                "memory": {
                    "read_enabled": True
                }
            }
        },
        # No retrieval_plan
    }

    result = load_active_memory_context(state)

    assert result["memory_read_status"] == "skipped_no_plan", (
        f"Expected 'skipped_no_plan', got {result.get('memory_read_status')}"
    )
    assert result["memory_context"] == [], "memory_context should be empty"
    print("✓ read_enabled=true, no plan -> skipped_no_plan")


def test_config_read_enabled_true_empty_plan():
    """Test status is 'skipped_no_plan' when retrieval_plan has no groups."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "message_text": "Hello",
        "config": {
            "jasmine_v2": {
                "memory": {
                    "read_enabled": True
                }
            }
        },
        "retrieval_plan": {
            "primary_space": {
                "space_type": "chat",
                "space_id": "test_chat",
            },
            "groups": []  # Empty groups
        },
    }

    result = load_active_memory_context(state)

    assert result["memory_read_status"] == "skipped_no_plan", (
        f"Expected 'skipped_no_plan', got {result.get('memory_read_status')}"
    )
    assert result["memory_context"] == [], "memory_context should be empty"
    print("✓ read_enabled=true, empty groups -> skipped_no_plan")


def test_read_enabled_true_with_results(monkeypatch):
    """Test status is 'ok' when adapter returns results."""
    fake_results = [
        {"text": "Memory 1", "source": "graphiti", "group_id": "g1", "score": 0.9},
        {"text": "Memory 2", "source": "graphiti", "group_id": "g2", "score": 0.8},
    ]

    # Monkeypatch the adapter
    from jasmine_v2.nodes import load_active_memory_context as lamc
    original_adapter = lamc.GraphitiV2MemoryAdapter
    lamc.GraphitiV2MemoryAdapter = lambda: FakeGraphitiV2MemoryAdapter(return_results=fake_results)

    try:
        state: JasmineState = {
            "transport": "telegram",
            "chat_id": "family_chat_123",
            "user_id": "user_456",
            "message_text": "Hello",
            "config": {
                "jasmine_v2": {
                    "memory": {
                        "read_enabled": True
                    }
                }
            },
            "retrieval_plan": {
                "primary_space": {
                    "space_type": "chat",
                    "space_id": "test_chat",
                },
                "groups": [
                    {"group_id": "g1", "role": "primary", "weight": 1.0},
                    {"group_id": "g2", "role": "secondary", "weight": 0.5},
                ]
            },
        }

        result = load_active_memory_context(state)

        assert result["memory_read_status"] == "ok", (
            f"Expected 'ok', got {result.get('memory_read_status')}"
        )
        assert result["memory_context"] == fake_results, "memory_context should contain results"
        assert len(result["memory_context"]) == 2, "Should have 2 results"
        print("✓ read_enabled=true, results -> ok")
    finally:
        lamc.GraphitiV2MemoryAdapter = original_adapter


def test_read_enabled_true_empty_results(monkeypatch):
    """Test status is 'empty' when adapter returns empty list."""
    # Monkeypatch the adapter
    from jasmine_v2.nodes import load_active_memory_context as lamc
    original_adapter = lamc.GraphitiV2MemoryAdapter
    lamc.GraphitiV2MemoryAdapter = lambda: FakeGraphitiV2MemoryAdapter(return_results=[])

    try:
        state: JasmineState = {
            "transport": "telegram",
            "chat_id": "family_chat_123",
            "user_id": "user_456",
            "message_text": "Hello",
            "config": {
                "jasmine_v2": {
                    "memory": {
                        "read_enabled": True
                    }
                }
            },
            "retrieval_plan": {
                "primary_space": {
                    "space_type": "chat",
                    "space_id": "test_chat",
                },
                "groups": [
                    {"group_id": "g1", "role": "primary", "weight": 1.0},
                ]
            },
        }

        result = load_active_memory_context(state)

        assert result["memory_read_status"] == "empty", (
            f"Expected 'empty', got {result.get('memory_read_status')}"
        )
        assert result["memory_context"] == [], "memory_context should be empty"
        print("✓ read_enabled=true, empty results -> empty")
    finally:
        lamc.GraphitiV2MemoryAdapter = original_adapter


def test_read_enabled_true_adapter_raises(monkeypatch):
    """Test status is 'failed' and error added when adapter raises exception."""
    # Monkeypatch the adapter
    from jasmine_v2.nodes import load_active_memory_context as lamc
    original_adapter = lamc.GraphitiV2MemoryAdapter
    lamc.GraphitiV2MemoryAdapter = lambda: FakeGraphitiV2MemoryAdapter(
        raise_exception=Exception("Graphiti connection failed")
    )

    try:
        state: JasmineState = {
            "transport": "telegram",
            "chat_id": "family_chat_123",
            "user_id": "user_456",
            "message_text": "Hello",
            "config": {
                "jasmine_v2": {
                    "memory": {
                        "read_enabled": True
                    }
                }
            },
            "retrieval_plan": {
                "primary_space": {
                    "space_type": "chat",
                    "space_id": "test_chat",
                },
                "groups": [
                    {"group_id": "g1", "role": "primary", "weight": 1.0},
                ]
            },
        }

        result = load_active_memory_context(state)

        assert result["memory_read_status"] == "failed", (
            f"Expected 'failed', got {result.get('memory_read_status')}"
        )
        assert result["memory_context"] == [], "memory_context should be empty"
        assert "errors" in result, "errors should be in state"
        assert any("Graphiti connection failed" in e for e in result["errors"]), (
            "Error should contain exception message"
        )
        print("✓ read_enabled=true, adapter raises -> failed + errors")
    finally:
        lamc.GraphitiV2MemoryAdapter = original_adapter


def test_debug_log_contains_load_active_memory_context():
    """Test debug_log contains load_active_memory_context entry."""
    from jasmine_v2.nodes import load_active_memory_context as lamc
    original_adapter = lamc.GraphitiV2MemoryAdapter
    lamc.GraphitiV2MemoryAdapter = lambda: FakeGraphitiV2MemoryAdapter(return_results=[])

    try:
        state: JasmineState = {
            "transport": "telegram",
            "chat_id": "family_chat_123",
            "user_id": "user_456",
            "message_text": "Hello",
            "config": {
                "jasmine_v2": {
                    "memory": {
                        "read_enabled": True
                    }
                }
            },
            "retrieval_plan": {
                "primary_space": {
                    "space_type": "chat",
                    "space_id": "test_chat",
                },
                "groups": [
                    {"group_id": "g1", "role": "primary", "weight": 1.0},
                ]
            },
        }

        result = load_active_memory_context(state)

        assert "debug_log" in result, "Missing debug_log"
        assert any(
            "load_active_memory_context:" in entry for entry in result["debug_log"]
        ), "debug_log should contain load_active_memory_context entry"
        print("✓ debug_log contains load_active_memory_context entry")
    finally:
        lamc.GraphitiV2MemoryAdapter = original_adapter


def test_debug_log_disabled():
    """Test debug_log contains entry when disabled."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "message_text": "Hello",
        "config": {
            "jasmine_v2": {
                "memory": {
                    "read_enabled": False
                }
            }
        },
    }

    result = load_active_memory_context(state)

    assert "debug_log" in result, "Missing debug_log"
    assert any(
        "load_active_memory_context:" in entry and "disabled" in entry
        for entry in result["debug_log"]
    ), "debug_log should contain disabled entry"
    print("✓ debug_log contains disabled entry")


def test_debug_log_skipped():
    """Test debug_log contains entry when skipped_no_plan."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "message_text": "Hello",
        "config": {
            "jasmine_v2": {
                "memory": {
                    "read_enabled": True
                }
            }
        },
        # No retrieval_plan
    }

    result = load_active_memory_context(state)

    assert "debug_log" in result, "Missing debug_log"
    assert any(
        "load_active_memory_context:" in entry and "skipped_no_plan" in entry
        for entry in result["debug_log"]
    ), "debug_log should contain skipped_no_plan entry"
    print("✓ debug_log contains skipped_no_plan entry")


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("Running load_active_memory_context tests")
    print("=" * 50)

    test_config_missing()
    test_config_read_enabled_false()
    test_config_read_enabled_true_no_plan()
    test_config_read_enabled_true_empty_plan()
    test_read_enabled_true_with_results(None)
    test_read_enabled_true_empty_results(None)
    test_read_enabled_true_adapter_raises(None)
    test_debug_log_contains_load_active_memory_context()
    test_debug_log_disabled()
    test_debug_log_skipped()

    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
