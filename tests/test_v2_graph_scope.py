"""Tests for jasmine_v2.memory.graph_scope module.

Run directly with: python3 tests/test_v2_graph_scope.py
"""

import os
import sys

# Ensure the project root is on sys.path when running this file directly
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from datetime import datetime, timezone

from jasmine_v2.memory.graph_scope import (
    MemoryGraphScope,
    get_active_group_ids,
    get_active_scopes,
    make_day_scope,
    make_longterm_scope,
    make_month_scope,
    make_week_scope,
)
from jasmine_v2.memory.spaces import MemorySpace, make_chat_space, make_project_space


def test_day_graph_id():
    """Test day graph_id for chat Telegram Family Main on 2026-05-10T14:22:00Z."""
    space = make_chat_space("Telegram Family Main")
    dt = "2026-05-10T14:22:00Z"
    scope = make_day_scope(space, dt)

    assert scope.time_level == "day"
    assert scope.time_id == "2026-05-10"
    assert scope.graph_id == "jv2:chat:telegram_family_main:day:2026-05-10"
    print(f"  day graph_id: {scope.graph_id}")


def test_week_graph_id():
    """Test week graph_id should be 2026-W19 for 2026-05-10."""
    space = make_chat_space("Telegram Family Main")
    dt = "2026-05-10T14:22:00Z"
    scope = make_week_scope(space, dt)

    assert scope.time_level == "week"
    assert scope.time_id == "2026-W19"
    assert scope.graph_id == "jv2:chat:telegram_family_main:week:2026-W19"
    print(f"  week graph_id: {scope.graph_id}")


def test_month_graph_id():
    """Test month graph_id should be 2026-05."""
    space = make_chat_space("Telegram Family Main")
    dt = "2026-05-10T14:22:00Z"
    scope = make_month_scope(space, dt)

    assert scope.time_level == "month"
    assert scope.time_id == "2026-05"
    assert scope.graph_id == "jv2:chat:telegram_family_main:month:2026-05"
    print(f"  month graph_id: {scope.graph_id}")


def test_longterm_graph_id():
    """Test longterm graph_id should have time_id 'all'."""
    space = make_chat_space("Telegram Family Main")
    scope = make_longterm_scope(space)

    assert scope.time_level == "longterm"
    assert scope.time_id == "all"
    assert scope.graph_id == "jv2:chat:telegram_family_main:longterm:all"
    print(f"  longterm graph_id: {scope.graph_id}")


def test_get_active_group_ids_order():
    """Test get_active_group_ids returns day/week/month/longterm in correct order."""
    space = make_chat_space("Telegram Family Main")
    dt = "2026-05-10T14:22:00Z"
    group_ids = get_active_group_ids(space, dt)

    expected = [
        "jv2:chat:telegram_family_main:day:2026-05-10",
        "jv2:chat:telegram_family_main:week:2026-W19",
        "jv2:chat:telegram_family_main:month:2026-05",
        "jv2:chat:telegram_family_main:longterm:all",
    ]

    assert group_ids == expected
    assert len(group_ids) == 4
    print(f"  active_group_ids: {group_ids}")


def test_project_graph_id():
    """Test graph_id for project space."""
    space = make_project_space("My Awesome Project")
    dt = "2026-05-10T14:22:00Z"
    scope = make_day_scope(space, dt)

    assert scope.graph_id == "jv2:project:my_awesome_project:day:2026-05-10"
    print(f"  project day graph_id: {scope.graph_id}")


def test_custom_longterm_graph_id():
    """Test longterm graph_id for custom space."""
    from jasmine_v2.memory.spaces import make_custom_space

    space = make_custom_space("Special Custom Space")
    scope = make_longterm_scope(space)

    assert scope.graph_id == "jv2:custom:special_custom_space:longterm:all"
    print(f"  custom longterm graph_id: {scope.graph_id}")


def test_memory_graph_scope_frozen():
    """Test that MemoryGraphScope is frozen and immutable."""
    space = make_chat_space("test")
    scope = MemoryGraphScope(space=space, time_level="day", time_id="2026-05-10")

    # Should be able to access attributes
    assert scope.space == space
    assert scope.time_level == "day"
    assert scope.time_id == "2026-05-10"

    # Should not be able to modify (frozen dataclass)
    try:
        scope.time_id = "2026-05-11"  # noqa: B010
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        pass  # Expected

    print("  MemoryGraphScope correctly frozen")


def test_get_active_scopes_returns_correct_types():
    """Test get_active_scopes returns list of MemoryGraphScope."""
    space = make_chat_space("test")
    dt = "2026-05-10T14:22:00Z"
    scopes = get_active_scopes(space, dt)

    assert len(scopes) == 4
    assert all(isinstance(s, MemoryGraphScope) for s in scopes)

    # Check order: day, week, month, longterm
    assert scopes[0].time_level == "day"
    assert scopes[1].time_level == "week"
    assert scopes[2].time_level == "month"
    assert scopes[3].time_level == "longterm"

    print("  get_active_scopes returns correct types and order")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_day_graph_id,
        test_week_graph_id,
        test_month_graph_id,
        test_longterm_graph_id,
        test_get_active_group_ids_order,
        test_project_graph_id,
        test_custom_longterm_graph_id,
        test_memory_graph_scope_frozen,
        test_get_active_scopes_returns_correct_types,
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("Running test_v2_graph_scope tests")
    print("=" * 60)

    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
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
