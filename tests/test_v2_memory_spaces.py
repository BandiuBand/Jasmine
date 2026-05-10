"""Tests for Jasmine v2 memory spaces."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.memory.spaces import (
    MemorySpace,
    make_chat_space,
    make_custom_space,
    make_family_space,
    make_project_space,
    make_system_space,
    make_user_space,
    sanitize_space_id,
)


def test_sanitize_space_id():
    """Test sanitize_space_id function with various inputs."""
    # Test cases from requirements
    assert sanitize_space_id("Telegram Family Main") == "telegram_family_main"
    assert sanitize_space_id("Jasmine v2") == "jasmine_v2"
    assert sanitize_space_id("chat:family/main") == "chat_family_main"
    assert sanitize_space_id(" ") == "unknown"
    assert sanitize_space_id("-1001234567890") == "-1001234567890"

    # Additional edge cases
    assert sanitize_space_id("") == "unknown"
    assert sanitize_space_id("___test___") == "test"
    assert sanitize_space_id("UPPERCASE") == "uppercase"
    assert sanitize_space_id("  spaces  ") == "spaces"
    print("✓ test_sanitize_space_id passed")


def test_make_chat_space():
    """Test make_chat_space helper."""
    space = make_chat_space("Telegram Family Main")
    assert space.key == "chat:telegram_family_main"
    assert space.space_type == "chat"
    assert space.space_id == "telegram_family_main"
    print("✓ test_make_chat_space passed")


def test_make_user_space():
    """Test make_user_space helper."""
    space = make_user_space("Bandiu")
    assert space.key == "user:bandiu"
    assert space.space_type == "user"
    assert space.space_id == "bandiu"
    print("✓ test_make_user_space passed")


def test_make_family_space():
    """Test make_family_space helper."""
    # Test with default
    space = make_family_space()
    assert space.key == "family:main"
    assert space.space_type == "family"
    assert space.space_id == "main"

    # Test with custom key
    space_custom = make_family_space("MyFamily")
    assert space_custom.key == "family:myfamily"
    print("✓ test_make_family_space passed")


def test_make_project_space():
    """Test make_project_space helper."""
    space = make_project_space("Jasmine v2")
    assert space.key == "project:jasmine_v2"
    assert space.space_type == "project"
    assert space.space_id == "jasmine_v2"
    print("✓ test_make_project_space passed")


def test_make_custom_space():
    """Test make_custom_space helper."""
    space = make_custom_space("Workspace Default")
    assert space.key == "custom:workspace_default"
    assert space.space_type == "custom"
    assert space.space_id == "workspace_default"
    print("✓ test_make_custom_space passed")


def test_make_system_space():
    """Test make_system_space helper."""
    # Test with default
    space = make_system_space()
    assert space.key == "system:jasmine"
    assert space.space_type == "system"
    assert space.space_id == "jasmine"

    # Test with custom key
    space_custom = make_system_space("config")
    assert space_custom.key == "system:config"
    print("✓ test_make_system_space passed")


def test_memory_space_immutable():
    """Test that MemorySpace is frozen (immutable)."""
    space = MemorySpace(space_type="chat", space_id="test")
    assert space.key == "chat:test"

    # Should raise error when trying to modify
    try:
        space.space_id = "modified"
        assert False, "Should have raised an error"
    except AttributeError:
        pass  # Expected
    print("✓ test_memory_space_immutable passed")


def run_all_tests():
    """Run all tests."""
    print("\n=== Running Memory Spaces Tests ===\n")
    test_sanitize_space_id()
    test_make_chat_space()
    test_make_user_space()
    test_make_family_space()
    test_make_project_space()
    test_make_custom_space()
    test_make_system_space()
    test_memory_space_immutable()
    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    run_all_tests()
