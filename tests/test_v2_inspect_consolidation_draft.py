"""Tests for jasmine_v2.memory.inspect_consolidation_draft module.

Run directly with: python3 tests/test_v2_inspect_consolidation_draft.py
"""

import os
import sys
from unittest.mock import Mock

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from jasmine_v2.memory.inspect_consolidation_draft import (
    format_text,
    inspect_consolidation_draft,
    main,
    resolve_group_id,
)


def _fake_result(overrides: dict | None = None) -> dict:
    """Build a fake consolidation_draft response."""
    result = {
        "group_id": "jv2-chat-test-day-2026-05-11",
        "mode": "raw_to_summary",
        "counts": {
            "episodes": 3,
            "entities": 10,
            "edges": 15,
            "mentions": 8,
        },
        "source": {
            "episodes": 3,
            "entities": 10,
            "edges": 15,
            "mentions": 8,
        },
        "model": "test-model-v1",
        "consolidation_text": "Test consolidation text.",
    }
    if overrides:
        result.update(overrides)
    return result


def test_resolve_group_id_directly():
    """Test resolve_group_id returns group_id directly when provided."""
    group_id = "jv2-chat-telegram_private_627630958-day-2026-05-11"
    result = resolve_group_id(group_id=group_id)
    assert result == group_id
    print("  resolve_group_id directly works")


def test_resolve_group_id_from_space_and_date():
    """Test resolve_group_id builds group_id from space and date."""
    result = resolve_group_id(
        space_str="chat:telegram_private_627630958",
        date_str="2026-05-11",
    )
    assert result == "jv2-chat-telegram_private_627630958-day-2026-05-11"
    print("  resolve_group_id from space/date works")


def test_resolve_group_id_error_if_neither():
    """Test resolve_group_id raises error if neither group_id nor space is provided."""
    try:
        resolve_group_id()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "--group-id" in str(e) or "--space" in str(e)
        print(f"  resolve_group_id error works: {e}")


def test_output_includes_counts():
    """Test inspect_consolidation_draft output includes counts."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result()

    output = inspect_consolidation_draft(
        group_id="jv2-chat-test-day-2026-05-11",
        client=fake_client,
    )

    assert "group_id: jv2-chat-test-day-2026-05-11" in output
    assert "mode: raw_to_summary" in output
    assert "episodes: 3" in output
    assert "entities: 10" in output
    assert "edges: 15" in output
    assert "mentions: 8" in output
    print("  output includes counts")


def test_output_includes_model():
    """Test inspect_consolidation_draft output includes model."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result()

    output = inspect_consolidation_draft(
        group_id="jv2-chat-test-day-2026-05-11",
        client=fake_client,
    )

    assert "model: test-model-v1" in output
    print("  output includes model")


def test_output_includes_consolidation_text():
    """Test inspect_consolidation_draft output includes consolidation_text."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result()

    output = inspect_consolidation_draft(
        group_id="jv2-chat-test-day-2026-05-11",
        client=fake_client,
    )

    assert "consolidation_text:" in output
    assert "Test consolidation text." in output
    print("  output includes consolidation_text")


def test_no_raw_episodes_passes_false():
    """Test include_raw_episodes=False is passed when --no-raw-episodes is set."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({"consolidation_text": ""})

    inspect_consolidation_draft(
        group_id="jv2-chat-test-day-2026-05-11",
        include_raw_episodes=False,
        client=fake_client,
    )

    call_kwargs = fake_client.consolidation_draft.call_args[1]
    assert call_kwargs["include_raw_episodes"] is False
    print("  include_raw_episodes=False passes correctly")


def test_invalid_mode_rejected():
    """Test main rejects invalid mode."""
    rc = main([
        "--group-id", "jv2-chat-test-day-2026-05-11",
        "--mode", "full",
    ])
    assert rc == 2
    print("  invalid mode rejected with rc=2")


def test_include_snapshot_draft_passes_true():
    """Test include_snapshot_draft=True is passed when --include-snapshot-draft is set."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({
        "consolidation_text": "",
        "draft_text": "Snapshot preview text.",
    })

    inspect_consolidation_draft(
        group_id="jv2-chat-test-day-2026-05-11",
        include_snapshot_draft=True,
        client=fake_client,
    )

    call_kwargs = fake_client.consolidation_draft.call_args[1]
    assert call_kwargs["include_snapshot_draft"] is True
    print("  include_snapshot_draft=True passes correctly")


def test_max_chars_truncates_long_consolidation_text():
    """Test --max-chars truncates long consolidation_text."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({
        "consolidation_text": "A" * 8000,
    })

    output = inspect_consolidation_draft(
        group_id="jv2-chat-test-day-2026-05-11",
        max_chars=100,
        client=fake_client,
    )

    assert "A" * 100 in output
    assert "... [truncated, total chars: 8000]" in output
    assert "A" * 101 not in output
    print("  max-chars truncates long consolidation_text")


def test_format_text_none():
    """Test format_text handles None."""
    result = format_text(None, 100)
    assert result == "(no text)"
    print("  format_text handles None")


def test_format_text_short():
    """Test format_text does not truncate short text."""
    result = format_text("short", 100)
    assert result == "short"
    print("  format_text short text unchanged")


def test_main_with_group_id():
    """Test main CLI with --group-id."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({"consolidation_text": ""})

    import jasmine_v2.memory.inspect_consolidation_draft as inspect_module

    original_client_class = inspect_module.GraphitiHttpClient
    inspect_module.GraphitiHttpClient = lambda: fake_client
    try:
        rc = main(["--group-id", "jv2-chat-test-day-2026-05-11"])
        assert rc == 0
        print("  main with --group-id returns 0")
    finally:
        inspect_module.GraphitiHttpClient = original_client_class


def test_main_with_space_and_date():
    """Test main CLI with --space and --date."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({"consolidation_text": ""})

    import jasmine_v2.memory.inspect_consolidation_draft as inspect_module

    original_client_class = inspect_module.GraphitiHttpClient
    inspect_module.GraphitiHttpClient = lambda: fake_client
    try:
        rc = main([
            "--space", "chat:telegram_private_627630958",
            "--date", "2026-05-11",
        ])
        assert rc == 0
        print("  main with --space and --date returns 0")
    finally:
        inspect_module.GraphitiHttpClient = original_client_class


def test_main_error_if_neither_group_id_nor_space():
    """Test main returns error if neither --group-id nor --space is provided."""
    rc = main([])
    assert rc == 2
    print("  main returns error if neither group-id nor space")


def test_main_limits_passed():
    """Test main passes custom limits to consolidation_draft."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({"consolidation_text": ""})

    import jasmine_v2.memory.inspect_consolidation_draft as inspect_module

    original_client_class = inspect_module.GraphitiHttpClient
    inspect_module.GraphitiHttpClient = lambda: fake_client
    try:
        rc = main([
            "--group-id", "jv2-chat-test-day-2026-05-11",
            "--episode-limit", "10",
            "--entity-limit", "25",
            "--edge-limit", "30",
        ])
        assert rc == 0
        call_kwargs = fake_client.consolidation_draft.call_args[1]
        assert call_kwargs["episode_limit"] == 10
        assert call_kwargs["entity_limit"] == 25
        assert call_kwargs["edge_limit"] == 30
        print("  main passes custom limits")
    finally:
        inspect_module.GraphitiHttpClient = original_client_class


def test_main_no_raw_episodes_flag():
    """Test main --no-raw-episodes flag."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({"consolidation_text": ""})

    import jasmine_v2.memory.inspect_consolidation_draft as inspect_module

    original_client_class = inspect_module.GraphitiHttpClient
    inspect_module.GraphitiHttpClient = lambda: fake_client
    try:
        rc = main([
            "--group-id", "jv2-chat-test-day-2026-05-11",
            "--no-raw-episodes",
        ])
        assert rc == 0
        call_kwargs = fake_client.consolidation_draft.call_args[1]
        assert call_kwargs["include_raw_episodes"] is False
        print("  main --no-raw-episodes flag works")
    finally:
        inspect_module.GraphitiHttpClient = original_client_class


def test_main_include_snapshot_draft_flag():
    """Test main --include-snapshot-draft flag."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({
        "consolidation_text": "",
        "draft_text": "Snapshot preview.",
    })

    import jasmine_v2.memory.inspect_consolidation_draft as inspect_module

    original_client_class = inspect_module.GraphitiHttpClient
    inspect_module.GraphitiHttpClient = lambda: fake_client
    try:
        rc = main([
            "--group-id", "jv2-chat-test-day-2026-05-11",
            "--include-snapshot-draft",
        ])
        assert rc == 0
        call_kwargs = fake_client.consolidation_draft.call_args[1]
        assert call_kwargs["include_snapshot_draft"] is True
        print("  main --include-snapshot-draft flag works")
    finally:
        inspect_module.GraphitiHttpClient = original_client_class


def test_main_max_chars_flag():
    """Test main --max-chars flag."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({
        "consolidation_text": "B" * 500,
    })

    import jasmine_v2.memory.inspect_consolidation_draft as inspect_module

    original_client_class = inspect_module.GraphitiHttpClient
    inspect_module.GraphitiHttpClient = lambda: fake_client
    try:
        rc = main([
            "--group-id", "jv2-chat-test-day-2026-05-11",
            "--max-chars", "100",
        ])
        assert rc == 0
        print("  main --max-chars flag works")
    finally:
        inspect_module.GraphitiHttpClient = original_client_class


def test_snapshot_draft_preview_shown_when_present():
    """Test snapshot_draft_text preview is shown when draft_text is present."""
    fake_client = Mock()
    fake_client.consolidation_draft.return_value = _fake_result({
        "consolidation_text": "Consolidated.",
        "draft_text": "Snapshot preview text.",
    })

    output = inspect_consolidation_draft(
        group_id="jv2-chat-test-day-2026-05-11",
        include_snapshot_draft=True,
        client=fake_client,
    )

    assert "snapshot_draft_text preview:" in output
    assert "Snapshot preview text." in output
    print("  snapshot_draft_text preview shown")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_resolve_group_id_directly,
        test_resolve_group_id_from_space_and_date,
        test_resolve_group_id_error_if_neither,
        test_output_includes_counts,
        test_output_includes_model,
        test_output_includes_consolidation_text,
        test_no_raw_episodes_passes_false,
        test_invalid_mode_rejected,
        test_include_snapshot_draft_passes_true,
        test_max_chars_truncates_long_consolidation_text,
        test_format_text_none,
        test_format_text_short,
        test_main_with_group_id,
        test_main_with_space_and_date,
        test_main_error_if_neither_group_id_nor_space,
        test_main_limits_passed,
        test_main_no_raw_episodes_flag,
        test_main_include_snapshot_draft_flag,
        test_main_max_chars_flag,
        test_snapshot_draft_preview_shown_when_present,
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("Running test_v2_inspect_consolidation_draft tests")
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
