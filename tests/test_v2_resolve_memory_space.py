"""Tests for resolve_memory_space node."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from jasmine_v2.nodes.resolve_memory_space import resolve_memory_space
from jasmine_v2.core.state import JasmineState


def test_telegram_group():
    """Test telegram group -> chat:telegram_family_main"""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "family_chat_123",
        "user_id": "user_456",
        "event": {
            "raw": {
                "chat_type": "group"
            }
        }
    }

    result = resolve_memory_space(state)

    assert result["primary_memory_space"]["space_type"] == "chat"
    assert result["primary_memory_space"]["space_id"] == "telegram_family_main"
    assert result["primary_memory_space"]["key"] == "chat:telegram_family_main"
    print("✓ telegram group: chat:telegram_family_main")


def test_telegram_supergroup():
    """Test telegram supergroup -> chat:telegram_family_main"""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "supergroup_123",
        "user_id": "user_789",
        "event": {
            "raw": {
                "chat_type": "supergroup"
            }
        }
    }

    result = resolve_memory_space(state)

    assert result["primary_memory_space"]["space_type"] == "chat"
    assert result["primary_memory_space"]["space_id"] == "telegram_family_main"
    assert result["primary_memory_space"]["key"] == "chat:telegram_family_main"
    print("✓ telegram supergroup: chat:telegram_family_main")


def test_telegram_private():
    """Test telegram private user_id=12345 -> chat:telegram_private_12345"""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "private_12345",
        "user_id": "12345",
        "event": {
            "raw": {
                "chat_type": "private"
            }
        }
    }

    result = resolve_memory_space(state)

    assert result["primary_memory_space"]["space_type"] == "chat"
    assert result["primary_memory_space"]["space_id"] == "telegram_private_12345"
    assert result["primary_memory_space"]["key"] == "chat:telegram_private_12345"
    print("✓ telegram private: chat:telegram_private_12345")


def test_telegram_shadow_group():
    """Test telegram_shadow group -> chat:telegram_family_main"""
    state: JasmineState = {
        "transport": "telegram_shadow",
        "chat_id": "shadow_chat_123",
        "user_id": "user_456",
        "event": {
            "raw": {
                "chat_type": "group"
            }
        }
    }

    result = resolve_memory_space(state)

    assert result["primary_memory_space"]["space_type"] == "chat"
    assert result["primary_memory_space"]["space_id"] == "telegram_family_main"
    assert result["primary_memory_space"]["key"] == "chat:telegram_family_main"
    print("✓ telegram_shadow group: chat:telegram_family_main")


def test_cli_with_user_id():
    """Test cli user_id=bandiu -> user:bandiu"""
    state: JasmineState = {
        "transport": "cli",
        "chat_id": "local",
        "user_id": "bandiu",
        "event": {}
    }

    result = resolve_memory_space(state)

    assert result["primary_memory_space"]["space_type"] == "user"
    assert result["primary_memory_space"]["space_id"] == "bandiu"
    assert result["primary_memory_space"]["key"] == "user:bandiu"
    print("✓ cli with user_id: user:bandiu")


def test_cli_without_user_id():
    """Test cli without user_id -> user:local_user"""
    state: JasmineState = {
        "transport": "cli",
        "chat_id": "local",
        "user_id": "",
        "event": {}
    }

    result = resolve_memory_space(state)

    assert result["primary_memory_space"]["space_type"] == "user"
    assert result["primary_memory_space"]["space_id"] == "local_user"
    assert result["primary_memory_space"]["key"] == "user:local_user"
    print("✓ cli without user_id: user:local_user")


def test_fallback_unknown_transport():
    """Test fallback unknown/chat42 -> chat:unknown_chat42"""
    state: JasmineState = {
        "transport": "unknown",
        "chat_id": "chat42",
        "user_id": "user_123",
        "event": {}
    }

    result = resolve_memory_space(state)

    assert result["primary_memory_space"]["space_type"] == "chat"
    assert result["primary_memory_space"]["space_id"] == "unknown_chat42"
    assert result["primary_memory_space"]["key"] == "chat:unknown_chat42"
    print("✓ fallback unknown: chat:unknown_chat42")


def test_debug_log_present():
    """Test that debug_log contains resolve_memory_space entry"""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "test_chat",
        "user_id": "test_user",
        "event": {
            "raw": {
                "chat_type": "group"
            }
        }
    }

    result = resolve_memory_space(state)

    assert "debug_log" in result
    assert any("resolve_memory_space: primary=" in entry for entry in result["debug_log"])
    print("✓ debug_log contains resolve_memory_space entry")


def test_no_raw_event():
    """Test handling when event.raw is missing"""
    state: JasmineState = {
        "transport": "telegram",
        "chat_id": "some_chat",
        "user_id": "user_123",
        "event": {}
    }

    result = resolve_memory_space(state)

    # Should fallback to transport_chat_id pattern since chat_type is unknown
    assert result["primary_memory_space"]["space_type"] == "chat"
    assert "telegram_some_chat" in result["primary_memory_space"]["space_id"]
    print("✓ handles missing raw event (fallback to transport_chat_id)")


def test_event_not_dict():
    """Test handling when event is not a dict"""
    state: JasmineState = {
        "transport": "cli",
        "chat_id": "local",
        "user_id": "test_user",
        "event": "not_a_dict"
    }

    result = resolve_memory_space(state)

    assert result["primary_memory_space"]["space_type"] == "user"
    assert result["primary_memory_space"]["space_id"] == "test_user"
    print("✓ handles non-dict event")


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("Running resolve_memory_space tests")
    print("=" * 50)

    test_telegram_group()
    test_telegram_supergroup()
    test_telegram_private()
    test_telegram_shadow_group()
    test_cli_with_user_id()
    test_cli_without_user_id()
    test_fallback_unknown_transport()
    test_debug_log_present()
    test_no_raw_event()
    test_event_not_dict()

    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()
