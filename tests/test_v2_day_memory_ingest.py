"""Tests for day_memory_ingest node.

Run directly with: python3 tests/test_v2_day_memory_ingest.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.core.state import JasmineState
from jasmine_v2.nodes.day_memory_ingest import day_memory_ingest


def _make_base_state(**overrides) -> JasmineState:
    """Build a base JasmineState for tests."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "user_name": "Test User",
        "message_text": "Hello world",
        "scope": "family",
        "intent": "simple_chat",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"message_id": "msg_789"},
        },
        "primary_memory_space": {
            "space_type": "chat",
            "space_id": "telegram_family_main",
        },
        "config": {
            "jasmine_v2": {
                "memory": {
                    "day_write_enabled": False,
                }
            }
        },
    }
    state.update(overrides)
    return state


def test_config_missing_day_write_enabled():
    """When config is missing day_write_enabled, adapter is NOT called and status is dry_run."""
    state = _make_base_state(config={})

    with patch("jasmine_v2.nodes.day_memory_ingest.GraphitiV2MemoryAdapter") as mock_cls:
        result = day_memory_ingest(state)

    mock_cls.assert_not_called()
    assert result["day_memory_write_status"] == "dry_run"
    print("✓ config missing -> dry_run, adapter not called")


def test_day_write_enabled_false():
    """When day_write_enabled=False, adapter is NOT called and status is dry_run."""
    state = _make_base_state()

    with patch("jasmine_v2.nodes.day_memory_ingest.GraphitiV2MemoryAdapter") as mock_cls:
        result = day_memory_ingest(state)

    mock_cls.assert_not_called()
    assert result["day_memory_write_status"] == "dry_run"
    print("✓ day_write_enabled=false -> dry_run, adapter not called")


def test_day_write_enabled_true_writes():
    """When day_write_enabled=True, adapter IS called and status is written."""
    state = _make_base_state(
        config={
            "jasmine_v2": {
                "memory": {
                    "day_write_enabled": True,
                }
            }
        }
    )

    mock_adapter = MagicMock()
    mock_adapter.add_day_message_episode.return_value = {"uuid": "test-uuid-123"}

    with patch(
        "jasmine_v2.nodes.day_memory_ingest.GraphitiV2MemoryAdapter",
        return_value=mock_adapter,
    ):
        result = day_memory_ingest(state)

    mock_adapter.add_day_message_episode.assert_called_once()
    assert result["day_memory_write_status"] == "written"
    assert result.get("day_memory_write_result") == {"uuid": "test-uuid-123"}
    print("✓ day_write_enabled=true -> adapter called, status written")


def test_adapter_receives_correct_arguments():
    """Adapter receives correct text, access_scope, message_id, and other args."""
    state = _make_base_state(
        config={
            "jasmine_v2": {
                "memory": {
                    "day_write_enabled": True,
                }
            }
        }
    )

    mock_adapter = MagicMock()
    mock_adapter.add_day_message_episode.return_value = {"uuid": "abc"}

    with patch(
        "jasmine_v2.nodes.day_memory_ingest.GraphitiV2MemoryAdapter",
        return_value=mock_adapter,
    ):
        day_memory_ingest(state)

    call_kwargs = mock_adapter.add_day_message_episode.call_args[1]
    assert call_kwargs["text"] == "Hello world"
    assert call_kwargs["access_scope"] == "family"
    assert call_kwargs["message_id"] == "msg_789"
    assert call_kwargs["chat_id"] == "family_chat_123"
    assert call_kwargs["sender_id"] == "user_456"
    assert call_kwargs["sender_name"] == "Test User"
    assert call_kwargs["timestamp"] == "2026-05-10T14:22:00Z"
    assert call_kwargs["source"] == "telegram"
    assert call_kwargs["metadata"] == {
        "transport": "telegram",
        "intent": "simple_chat",
    }
    print("✓ adapter receives correct arguments")


def test_adapter_raises_status_failed_and_errors():
    """When adapter raises, status is failed and error is added to state["errors"]."""
    state = _make_base_state(
        config={
            "jasmine_v2": {
                "memory": {
                    "day_write_enabled": True,
                }
            }
        }
    )

    mock_adapter = MagicMock()
    mock_adapter.add_day_message_episode.side_effect = RuntimeError("Graphiti down")

    with patch(
        "jasmine_v2.nodes.day_memory_ingest.GraphitiV2MemoryAdapter",
        return_value=mock_adapter,
    ):
        result = day_memory_ingest(state)

    assert result["day_memory_write_status"] == "failed"
    assert "errors" in result
    assert any("Graphiti down" in err for err in result["errors"])
    print("✓ adapter raises -> status failed + errors logged")


def test_no_primary_memory_space():
    """When primary_memory_space is missing, status is skipped_no_primary_space."""
    state = _make_base_state(primary_memory_space=None)

    with patch("jasmine_v2.nodes.day_memory_ingest.GraphitiV2MemoryAdapter") as mock_cls:
        result = day_memory_ingest(state)

    mock_cls.assert_not_called()
    assert result["day_memory_write_status"] == "skipped_no_primary_space"
    assert result["day_memory_group_id"] == ""
    assert result["active_memory_group_ids"] == []
    assert result["retrieval_plan"] == {}
    print("✓ no primary_memory_space -> skipped_no_primary_space")


def test_active_memory_group_ids_has_day_week_month_longterm():
    """active_memory_group_ids contains day, week, month, longterm in order."""
    state = _make_base_state()

    with patch("jasmine_v2.nodes.day_memory_ingest.GraphitiV2MemoryAdapter"):
        result = day_memory_ingest(state)

    active_groups = result["active_memory_group_ids"]
    assert len(active_groups) == 4, f"Expected 4 groups, got {len(active_groups)}"
    assert ":day:" in active_groups[0]
    assert ":week:" in active_groups[1]
    assert ":month:" in active_groups[2]
    assert ":longterm:" in active_groups[3]
    print(f"✓ active_memory_group_ids correct: {active_groups}")


def test_debug_log_contains_day_memory_ingest():
    """debug_log contains day_memory_ingest entry."""
    state = _make_base_state()

    with patch("jasmine_v2.nodes.day_memory_ingest.GraphitiV2MemoryAdapter"):
        result = day_memory_ingest(state)

    assert "debug_log" in result
    assert any(
        "day_memory_ingest:" in entry for entry in result["debug_log"]
    ), "debug_log should contain day_memory_ingest entry"
    print("✓ debug_log contains day_memory_ingest")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_config_missing_day_write_enabled,
        test_day_write_enabled_false,
        test_day_write_enabled_true_writes,
        test_adapter_receives_correct_arguments,
        test_adapter_raises_status_failed_and_errors,
        test_no_primary_memory_space,
        test_active_memory_group_ids_has_day_week_month_longterm,
        test_debug_log_contains_day_memory_ingest,
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("Running test_v2_day_memory_ingest tests")
    print("=" * 60)

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
