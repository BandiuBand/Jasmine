"""Tests for day_memory_dry_run node."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.nodes.day_memory_dry_run import day_memory_dry_run
from jasmine_v2.core.state import JasmineState


def test_day_memory_group_id_format():
    """Test day_memory_group_id format for chat:telegram_family_main."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        "primary_memory_space": {
            "space_type": "chat",
            "space_id": "telegram_family_main",
            "key": "chat:telegram_family_main",
        },
    }

    result = day_memory_dry_run(state)

    expected_group_id = "jv2:chat:telegram_family_main:day:2026-05-10"
    assert result["day_memory_group_id"] == expected_group_id, (
        f"Expected {expected_group_id}, got {result['day_memory_group_id']}"
    )
    print(f"✓ day_memory_group_id: {result['day_memory_group_id']}")


def test_active_memory_group_ids_order():
    """Test active_memory_group_ids contains day/week/month/longterm in correct order."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        "primary_memory_space": {
            "space_type": "chat",
            "space_id": "telegram_family_main",
            "key": "chat:telegram_family_main",
        },
    }

    result = day_memory_dry_run(state)

    active_groups = result["active_memory_group_ids"]
    assert len(active_groups) == 4, f"Expected 4 groups, got {len(active_groups)}"

    # Check order: day, week, month, longterm
    assert ":day:" in active_groups[0], f"Expected day first, got {active_groups[0]}"
    assert ":week:" in active_groups[1], f"Expected week second, got {active_groups[1]}"
    assert ":month:" in active_groups[2], f"Expected month third, got {active_groups[2]}"
    assert ":longterm:" in active_groups[3], f"Expected longterm fourth, got {active_groups[3]}"

    print(f"✓ active_memory_group_ids order correct: {active_groups}")


def test_day_memory_write_status_dry_run():
    """Test day_memory_write_status is 'dry_run' when primary_memory_space exists."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        "primary_memory_space": {
            "space_type": "chat",
            "space_id": "telegram_family_main",
            "key": "chat:telegram_family_main",
        },
    }

    result = day_memory_dry_run(state)

    assert result["day_memory_write_status"] == "dry_run", (
        f"Expected 'dry_run', got {result['day_memory_write_status']}"
    )
    print("✓ day_memory_write_status == 'dry_run'")


def test_retrieval_plan_groups_count():
    """Test retrieval_plan['groups'] has 4 items."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        "primary_memory_space": {
            "space_type": "chat",
            "space_id": "telegram_family_main",
            "key": "chat:telegram_family_main",
        },
    }

    result = day_memory_dry_run(state)

    groups = result["retrieval_plan"]["groups"]
    assert len(groups) == 4, f"Expected 4 groups in plan, got {len(groups)}"

    # Check each group has required fields
    for group in groups:
        assert "group_id" in group, "Missing group_id"
        assert "role" in group, "Missing role"
        assert "weight" in group, "Missing weight"
        assert "reason" in group, "Missing reason"

    print(f"✓ retrieval_plan['groups'] has 4 items with correct structure")


def test_skipped_no_primary_space():
    """Test status is 'skipped_no_primary_space' when primary_memory_space is missing."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        # No primary_memory_space
    }

    result = day_memory_dry_run(state)

    assert result["day_memory_write_status"] == "skipped_no_primary_space", (
        f"Expected 'skipped_no_primary_space', got {result['day_memory_write_status']}"
    )
    print("✓ skipped_no_primary_space when primary_memory_space missing")


def test_no_exception_on_missing_primary_space():
    """Test no exception is raised when primary_memory_space is missing."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        # No primary_memory_space
    }

    try:
        result = day_memory_dry_run(state)
        # Should reach here without exception
        assert "day_memory_write_status" in result
        print("✓ no exception raised when primary_memory_space missing")
    except Exception as e:
        assert False, f"Should not raise exception, got: {e}"


def test_debug_log_contains_entry():
    """Test debug_log contains day_memory_dry_run entry."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        "primary_memory_space": {
            "space_type": "chat",
            "space_id": "telegram_family_main",
            "key": "chat:telegram_family_main",
        },
    }

    result = day_memory_dry_run(state)

    assert "debug_log" in result, "Missing debug_log"
    assert any(
        "day_memory_dry_run:" in entry for entry in result["debug_log"]
    ), "debug_log should contain day_memory_dry_run entry"

    print("✓ debug_log contains day_memory_dry_run entry")


def test_retrieval_plan_structure():
    """Test retrieval_plan has correct structure with primary_space and groups."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        "primary_memory_space": {
            "space_type": "chat",
            "space_id": "telegram_family_main",
            "key": "chat:telegram_family_main",
        },
    }

    result = day_memory_dry_run(state)

    plan = result["retrieval_plan"]
    assert "primary_space" in plan, "Missing primary_space"
    assert "groups" in plan, "Missing groups"

    primary = plan["primary_space"]
    assert primary["space_type"] == "chat"
    assert primary["space_id"] == "telegram_family_main"
    assert primary["key"] == "chat:telegram_family_main"

    print("✓ retrieval_plan has correct structure")


def test_debug_log_on_skip():
    """Test debug_log contains entry when skipping due to missing primary_space."""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "timestamp": "2026-05-10T14:22:00Z",
            "raw": {"chat_type": "supergroup"},
        },
        # No primary_memory_space
    }

    result = day_memory_dry_run(state)

    assert "debug_log" in result, "Missing debug_log"
    assert any(
        "day_memory_dry_run:" in entry and "skipped" in entry
        for entry in result["debug_log"]
    ), "debug_log should contain day_memory_dry_run: skipped entry"

    print("✓ debug_log contains day_memory_dry_run: skipped entry")


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("Running day_memory_dry_run tests")
    print("=" * 50)

    test_day_memory_group_id_format()
    test_active_memory_group_ids_order()
    test_day_memory_write_status_dry_run()
    test_retrieval_plan_groups_count()
    test_skipped_no_primary_space()
    test_no_exception_on_missing_primary_space()
    test_debug_log_contains_entry()
    test_retrieval_plan_structure()
    test_debug_log_on_skip()

    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
