"""Tests for Jasmine v2 retrieval plan."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.memory.retrieval_plan import (
    MemoryGroupRef,
    MemoryGroupRole,
    RetrievalPlan,
    build_default_retrieval_plan,
)
from jasmine_v2.memory.spaces import make_chat_space, make_project_space, make_user_space


def test_default_plan_group_count():
    """Test that default plan for chat space has 4 groups."""
    primary = make_chat_space("Telegram Family Main")
    plan = build_default_retrieval_plan(primary, dt="2026-05-10T14:22:00Z")

    assert len(plan.groups) == 4, f"Expected 4 groups, got {len(plan.groups)}"
    print("✓ test_default_plan_group_count passed")


def test_default_plan_group_ids():
    """Test that group_ids match expected format for chat space."""
    primary = make_chat_space("Telegram Family Main")
    plan = build_default_retrieval_plan(primary, dt="2026-05-10T14:22:00Z")

    expected_ids = [
        "jv2:chat:telegram_family_main:day:2026-05-10",
        "jv2:chat:telegram_family_main:week:2026-W19",
        "jv2:chat:telegram_family_main:month:2026-05",
        "jv2:chat:telegram_family_main:longterm:all",
    ]

    assert plan.group_ids == expected_ids, f"Expected {expected_ids}, got {plan.group_ids}"
    print("✓ test_default_plan_group_ids passed")


def test_default_plan_roles():
    """Test that roles are primary, primary, primary, longterm."""
    primary = make_chat_space("Telegram Family Main")
    plan = build_default_retrieval_plan(primary, dt="2026-05-10T14:22:00Z")

    roles = [g.role for g in plan.groups]
    expected_roles = ["primary", "primary", "primary", "longterm"]

    assert roles == expected_roles, f"Expected roles {expected_roles}, got {roles}"
    print("✓ test_default_plan_roles passed")


def test_default_plan_weights():
    """Test that weights are 1.0, 0.9, 0.75, 0.65."""
    primary = make_chat_space("Telegram Family Main")
    plan = build_default_retrieval_plan(primary, dt="2026-05-10T14:22:00Z")

    weights = [g.weight for g in plan.groups]
    expected_weights = [1.0, 0.9, 0.75, 0.65]

    assert weights == expected_weights, f"Expected weights {expected_weights}, got {weights}"
    print("✓ test_default_plan_weights passed")


def test_extra_space_adds_longterm_only():
    """Test that extra user space adds only longterm group with correct role/weight."""
    primary = make_chat_space("Telegram Family Main")
    extra = make_user_space("Bandiu")

    plan = build_default_retrieval_plan(primary, extra_spaces=[extra], dt="2026-05-10T14:22:00Z")

    # Should have 5 groups now (4 primary + 1 extra)
    assert len(plan.groups) == 5, f"Expected 5 groups, got {len(plan.groups)}"

    # Check the extra group
    extra_group = plan.groups[4]
    expected_group_id = "jv2:user:bandiu:longterm:all"

    assert extra_group.group_id == expected_group_id, f"Expected {expected_group_id}, got {extra_group.group_id}"
    assert extra_group.role == "secondary", f"Expected role 'secondary', got {extra_group.role}"
    assert extra_group.weight == 0.4, f"Expected weight 0.4, got {extra_group.weight}"
    print("✓ test_extra_space_adds_longterm_only passed")


def test_project_space_as_primary():
    """Test that project space works correctly as primary space."""
    primary = make_project_space("Jasmine v2")
    plan = build_default_retrieval_plan(primary, dt="2026-05-10T14:22:00Z")

    expected_ids = [
        "jv2:project:jasmine_v2:day:2026-05-10",
        "jv2:project:jasmine_v2:week:2026-W19",
        "jv2:project:jasmine_v2:month:2026-05",
        "jv2:project:jasmine_v2:longterm:all",
    ]

    assert plan.group_ids == expected_ids, f"Expected {expected_ids}, got {plan.group_ids}"
    assert plan.primary_space.key == "project:jasmine_v2"
    print("✓ test_project_space_as_primary passed")


def test_memory_group_ref_frozen():
    """Test that MemoryGroupRef is frozen and cannot be modified."""
    ref = MemoryGroupRef(
        group_id="jv2:chat:test:day:2026-05-10",
        role="primary",
        weight=1.0,
    )

    # Should raise error when trying to modify weight
    try:
        ref.weight = 0.5
        assert False, "Should have raised an error when modifying frozen dataclass"
    except AttributeError:
        pass  # Expected

    # Also verify other fields are frozen
    try:
        ref.group_id = "new_id"
        assert False, "Should have raised an error when modifying frozen dataclass"
    except AttributeError:
        pass  # Expected

    try:
        ref.role = "secondary"
        assert False, "Should have raised an error when modifying frozen dataclass"
    except AttributeError:
        pass  # Expected

    print("✓ test_memory_group_ref_frozen passed")


def test_retrieval_plan_frozen():
    """Test that RetrievalPlan is frozen and cannot be modified."""
    primary = make_chat_space("Test")
    plan = build_default_retrieval_plan(primary, dt="2026-05-10T14:22:00Z")

    try:
        plan.primary_space = make_user_space("Other")
        assert False, "Should have raised an error when modifying frozen dataclass"
    except AttributeError:
        pass  # Expected

    print("✓ test_retrieval_plan_frozen passed")


def test_retrieval_plan_group_ids_property():
    """Test that group_ids property returns correct list."""
    primary = make_chat_space("Test Chat")
    plan = build_default_retrieval_plan(primary, dt="2026-05-10T14:22:00Z")

    group_ids = plan.group_ids
    assert isinstance(group_ids, list), "group_ids should return a list"
    assert len(group_ids) == 4, f"Expected 4 group_ids, got {len(group_ids)}"

    # Verify each group_id matches the group
    for i, group_id in enumerate(group_ids):
        assert group_id == plan.groups[i].group_id, f"Mismatch at index {i}"

    print("✓ test_retrieval_plan_group_ids_property passed")


def test_multiple_extra_spaces():
    """Test that multiple extra spaces are all included with correct settings."""
    primary = make_chat_space("Main")
    extra1 = make_user_space("User1")
    extra2 = make_user_space("User2")

    plan = build_default_retrieval_plan(
        primary,
        extra_spaces=[extra1, extra2],
        dt="2026-05-10T14:22:00Z"
    )

    # Should have 6 groups (4 primary + 2 extra)
    assert len(plan.groups) == 6, f"Expected 6 groups, got {len(plan.groups)}"

    # Check extra groups
    assert plan.groups[4].group_id == "jv2:user:user1:longterm:all"
    assert plan.groups[4].role == "secondary"
    assert plan.groups[4].weight == 0.4

    assert plan.groups[5].group_id == "jv2:user:user2:longterm:all"
    assert plan.groups[5].role == "secondary"
    assert plan.groups[5].weight == 0.4

    print("✓ test_multiple_extra_spaces passed")


def run_all_tests():
    """Run all retrieval plan tests."""
    print("\n=== Running Retrieval Plan Tests ===\n")
    test_default_plan_group_count()
    test_default_plan_group_ids()
    test_default_plan_roles()
    test_default_plan_weights()
    test_extra_space_adds_longterm_only()
    test_project_space_as_primary()
    test_memory_group_ref_frozen()
    test_retrieval_plan_frozen()
    test_retrieval_plan_group_ids_property()
    test_multiple_extra_spaces()
    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    run_all_tests()
