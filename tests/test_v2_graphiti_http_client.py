"""Tests for jasmine_v2.memory.graphiti_http_client module.

Run directly with: python3 tests/test_v2_graphiti_http_client.py
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import Mock, patch

# Ensure the project root is on sys.path when running this file directly
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from jasmine_v2.memory.graphiti_http_client import GraphitiHttpClient


def test_default_base_url():
    """Test default base_url is http://127.0.0.1:8088."""
    client = GraphitiHttpClient()
    assert client.base_url == "http://127.0.0.1:8088"
    print(f"  default base_url: {client.base_url}")


def test_env_base_url():
    """Test base_url from GRAPHITI_LOCAL_MEMORY_URL env var."""
    original_env = os.environ.get("GRAPHITI_LOCAL_MEMORY_URL")
    try:
        os.environ["GRAPHITI_LOCAL_MEMORY_URL"] = "http://custom:9999"
        client = GraphitiHttpClient()
        assert client.base_url == "http://custom:9999"
        print(f"  env base_url: {client.base_url}")
    finally:
        if original_env is not None:
            os.environ["GRAPHITI_LOCAL_MEMORY_URL"] = original_env
        else:
            del os.environ["GRAPHITI_LOCAL_MEMORY_URL"]


def test_trailing_slash_removed():
    """Test trailing slash is removed from base_url."""
    client = GraphitiHttpClient(base_url="http://localhost:8088/")
    assert client.base_url == "http://localhost:8088"
    print(f"  base_url without trailing slash: {client.base_url}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_health(mock_get):
    """Test health() GET /health."""
    mock_response = Mock()
    mock_response.json.return_value = {"status": "healthy"}
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.health()

    mock_get.assert_called_once_with(
        "http://127.0.0.1:8088/health",
        timeout=30.0
    )
    mock_response.raise_for_status.assert_called_once()
    assert result == {"status": "healthy"}
    print("  health() works correctly")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_config(mock_get):
    """Test config() GET /config."""
    mock_response = Mock()
    mock_response.json.return_value = {"version": "1.0.0"}
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.config()

    mock_get.assert_called_once_with(
        "http://127.0.0.1:8088/config",
        timeout=30.0
    )
    assert result == {"version": "1.0.0"}
    print("  config() works correctly")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_add_episode(mock_post):
    """Test add_episode() POST /episodes with correct payload."""
    mock_response = Mock()
    mock_response.json.return_value = {"uuid": "test-uuid-123"}
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.add_episode(
        name="Test Episode",
        body="Test body content",
        group_id="jv2-chat-test-day-2026-05-10",
    )

    mock_post.assert_called_once_with(
        "http://127.0.0.1:8088/episodes",
        json={
            "name": "Test Episode",
            "body": "Test body content",
            "group_id": "jv2-chat-test-day-2026-05-10",
            "source_description": "Jasmine v2 memory",
        },
        timeout=30.0
    )
    assert result == {"uuid": "test-uuid-123"}
    print("  add_episode() POST /episodes payload correct")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_add_episode_with_reference_time(mock_post):
    """Test add_episode() with reference_time."""
    mock_response = Mock()
    mock_response.json.return_value = {"uuid": "test-uuid-456"}
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()
    ref_time = datetime(2026, 5, 10, 14, 22, 0, tzinfo=timezone.utc)
    result = client.add_episode(
        name="Test Episode",
        body="Test body",
        group_id="jv2-chat-test-day-2026-05-10",
        reference_time=ref_time,
    )

    call_args = mock_post.call_args
    assert call_args[1]["json"]["reference_time"] == "2026-05-10T14:22:00+00:00"
    assert result == {"uuid": "test-uuid-456"}
    print("  add_episode() with reference_time works")


def test_add_episode_blocks_legacy_group_id():
    """Test add_episode() blocks legacy group_id 'family'."""
    client = GraphitiHttpClient()

    try:
        client.add_episode(
            name="Test",
            body="Test body",
            group_id="family",  # legacy group_id without jv2- prefix
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "jv2-" in str(e)
        print(f"  add_episode() blocks legacy group_id: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_search(mock_post):
    """Test search() POST /search with group_ids."""
    mock_response = Mock()
    mock_response.json.return_value = {"results": [{"uuid": "result-1"}]}
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.search(
        query="test query",
        group_ids=["jv2-chat-test-day-2026-05-10"],
    )

    mock_post.assert_called_once_with(
        "http://127.0.0.1:8088/search",
        json={
            "query": "test query",
            "group_ids": ["jv2-chat-test-day-2026-05-10"],
            "limit": 10,
            "include_episodes": True,
        },
        timeout=30.0
    )
    assert result == {"results": [{"uuid": "result-1"}]}
    print("  search() POST /search payload correct")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_search_with_multiple_group_ids(mock_post):
    """Test search() with multiple group_ids."""
    mock_response = Mock()
    mock_response.json.return_value = {"results": []}
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()
    client.search(
        query="test",
        group_ids=[
            "jv2-chat-test-day-2026-05-10",
            "jv2-chat-test-week-2026-W19",
        ],
        limit=5,
        include_episodes=False,
    )

    call_args = mock_post.call_args
    assert call_args[1]["json"]["group_ids"] == [
        "jv2-chat-test-day-2026-05-10",
        "jv2-chat-test-week-2026-W19",
    ]
    assert call_args[1]["json"]["limit"] == 5
    assert call_args[1]["json"]["include_episodes"] is False
    print("  search() with multiple group_ids works")


def test_search_blocks_empty_group_ids():
    """Test search() blocks empty group_ids."""
    client = GraphitiHttpClient()

    try:
        client.search(query="test", group_ids=[])
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower()
        print(f"  search() blocks empty group_ids: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_list_episodes(mock_get):
    """Test list_episodes() GET /episodes with params."""
    mock_response = Mock()
    mock_response.json.return_value = {"episodes": []}
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.list_episodes(
        group_id="jv2-chat-test-day-2026-05-10",
        limit=50,
        offset=10,
        order="desc",
    )

    mock_get.assert_called_once_with(
        "http://127.0.0.1:8088/episodes",
        params={
            "group_id": "jv2-chat-test-day-2026-05-10",
            "limit": 50,
            "offset": 10,
            "order": "desc",
        },
        timeout=30.0
    )
    assert result == {"episodes": []}
    print("  list_episodes() GET /episodes params correct")


def test_list_episodes_blocks_empty_group_id():
    """Test list_episodes() blocks empty group_id."""
    client = GraphitiHttpClient()

    try:
        client.list_episodes(group_id="")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower()
        print(f"  list_episodes() blocks empty group_id: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_group_stats(mock_get):
    """Test group_stats() GET /groups/{group_id}/stats with URL encoding."""
    mock_response = Mock()
    mock_response.json.return_value = {"count": 42}
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.group_stats("jv2-chat-test-day-2026-05-10")

    # Check the URL contains encoded group_id
    call_args = mock_get.call_args
    url = call_args[0][0]
    assert "/groups/" in url
    assert "/stats" in url
    # With dash format, no special chars need encoding in this example
    assert "jv2-chat-test-day-2026-05-10" in url
    assert result == {"count": 42}
    print(f"  group_stats() URL encodes group_id: {url}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_group_stats_with_special_chars(mock_get):
    """Test group_stats() properly encodes special characters."""
    mock_response = Mock()
    mock_response.json.return_value = {"count": 5}
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.group_stats("jv2-chat-hello world-day-2026-05-10")

    call_args = mock_get.call_args
    url = call_args[0][0]
    # Space should be encoded as %20
    assert "hello%20world" in url
    print(f"  group_stats() encodes spaces: {url}")


def test_group_stats_blocks_empty_group_id():
    """Test group_stats() blocks empty group_id."""
    client = GraphitiHttpClient()

    try:
        client.group_stats("")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower()
        print(f"  group_stats() blocks empty group_id: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_group_graph_calls_correct_url_and_params(mock_get):
    """Test group_graph() GET /groups/{group_id}/graph with correct params."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "group_id": "jv2-chat-test-day-2026-05-10",
        "episodes": [],
        "entities": [],
        "edges": [],
        "mentions": [],
        "counts": {},
        "limits": {},
    }
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.group_graph(
        group_id="jv2-chat-test-day-2026-05-10",
        episode_limit=100,
        entity_limit=200,
        edge_limit=300,
        include_content=False,
        include_embeddings=True,
    )

    mock_get.assert_called_once_with(
        "http://127.0.0.1:8088/groups/jv2-chat-test-day-2026-05-10/graph",
        params={
            "episode_limit": 100,
            "entity_limit": 200,
            "edge_limit": 300,
            "include_content": False,
            "include_embeddings": True,
        },
        timeout=30.0,
    )
    mock_response.raise_for_status.assert_called_once()
    assert result["group_id"] == "jv2-chat-test-day-2026-05-10"
    print("  group_graph() GET /groups/{group_id}/graph params correct")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_group_graph_url_encodes_group_id(mock_get):
    """Test group_graph() properly URL-encodes the group_id."""
    mock_response = Mock()
    mock_response.json.return_value = {"group_id": "jv2-chat-hello world"}
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()
    client.group_graph("jv2-chat-hello world-day-2026-05-10")

    call_args = mock_get.call_args
    url = call_args[0][0]
    assert "hello%20world" in url
    assert "/graph" in url
    print(f"  group_graph() encodes spaces: {url}")


def test_group_graph_blocks_empty_group_id():
    """Test group_graph() blocks empty group_id."""
    client = GraphitiHttpClient()

    try:
        client.group_graph("")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower()
        print(f"  group_graph() blocks empty group_id: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_group_graph_http_error_raises(mock_get):
    """Test group_graph HTTP error raises."""
    from requests import HTTPError

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()

    try:
        client.group_graph("jv2-chat-test-day-2026-05-10")
        assert False, "Should have raised HTTPError"
    except HTTPError as e:
        print(f"  group_graph HTTP error properly raised: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_group_graph_returns_json(mock_get):
    """Test group_graph() returns parsed JSON response."""
    expected = {
        "group_id": "jv2-chat-test-day-2026-05-10",
        "episodes": [{"uuid": "ep-1"}],
        "entities": [{"name": "Alice"}],
        "edges": [{"uuid": "edge-1"}],
        "mentions": [{"entity_uuid": "ent-1", "episode_uuid": "ep-1"}],
        "counts": {"episodes": 1, "entities": 1, "edges": 1},
        "limits": {"episode_limit": 500, "entity_limit": 500, "edge_limit": 500},
    }
    mock_response = Mock()
    mock_response.json.return_value = expected
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.group_graph("jv2-chat-test-day-2026-05-10")

    assert result == expected
    print("  group_graph() returns correct JSON")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_http_error_raises(mock_get):
    """Test HTTP error raises requests.HTTPError."""
    from requests import HTTPError

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()

    try:
        client.health()
        assert False, "Should have raised HTTPError"
    except HTTPError as e:
        print(f"  HTTP error properly raised: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_add_episode_http_error_raises(mock_post):
    """Test add_episode HTTP error raises."""
    from requests import HTTPError

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("400 Bad Request")
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()

    try:
        client.add_episode(
            name="Test",
            body="Body",
            group_id="jv2-chat-test-day-2026-05-10",
        )
        assert False, "Should have raised HTTPError"
    except HTTPError as e:
        print(f"  add_episode HTTP error properly raised: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_search_http_error_raises(mock_post):
    """Test search HTTP error raises."""
    from requests import HTTPError

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("400 Bad Request")
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()

    try:
        client.search(query="test", group_ids=["jv2-chat-test"])
        assert False, "Should have raised HTTPError"
    except HTTPError as e:
        print(f"  search HTTP error properly raised: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_list_episodes_http_error_raises(mock_get):
    """Test list_episodes HTTP error raises."""
    from requests import HTTPError

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()

    try:
        client.list_episodes(group_id="jv2-chat-test-day-2026-05-10")
        assert False, "Should have raised HTTPError"
    except HTTPError as e:
        print(f"  list_episodes HTTP error properly raised: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_group_stats_http_error_raises(mock_get):
    """Test group_stats HTTP error raises."""
    from requests import HTTPError

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
    mock_get.return_value = mock_response

    client = GraphitiHttpClient()

    try:
        client.group_stats("jv2-chat-test-day-2026-05-10")
        assert False, "Should have raised HTTPError"
    except HTTPError as e:
        print(f"  group_stats HTTP error properly raised: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_snapshot_draft_calls_correct_url_and_payload(mock_post):
    """Test snapshot_draft() POST /groups/{group_id}/snapshot/draft with correct payload."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "group_id": "jv2-chat-test-day-2026-05-10",
        "mode": "raw",
        "counts": {"episodes": 2, "entities": 3, "edges": 1, "mentions": 4},
        "draft_text": "draft content",
        "source": {"episodes": 2, "entities": 3, "edges": 1, "mentions": 4},
    }
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.snapshot_draft(
        group_id="jv2-chat-test-day-2026-05-10",
        episode_limit=100,
        entity_limit=200,
        edge_limit=300,
        include_raw_episodes=False,
    )

    mock_post.assert_called_once_with(
        "http://127.0.0.1:8088/groups/jv2-chat-test-day-2026-05-10/snapshot/draft",
        json={
            "episode_limit": 100,
            "entity_limit": 200,
            "edge_limit": 300,
            "include_raw_episodes": False,
            "mode": "raw",
        },
        timeout=30.0,
    )
    mock_response.raise_for_status.assert_called_once()
    assert result["mode"] == "raw"
    assert result["draft_text"] == "draft content"
    print("  snapshot_draft() POST URL and payload correct")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_snapshot_draft_url_encodes_group_id(mock_post):
    """Test snapshot_draft() properly URL-encodes the group_id."""
    mock_response = Mock()
    mock_response.json.return_value = {"group_id": "jv2-chat-hello world"}
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()
    client.snapshot_draft("jv2-chat-hello world-day-2026-05-10")

    call_args = mock_post.call_args
    url = call_args[0][0]
    assert "hello%20world" in url
    assert "/snapshot/draft" in url
    print(f"  snapshot_draft() encodes spaces: {url}")


def test_snapshot_draft_blocks_empty_group_id():
    """Test snapshot_draft() blocks empty group_id."""
    client = GraphitiHttpClient()

    try:
        client.snapshot_draft("")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower()
        print(f"  snapshot_draft() blocks empty group_id: {e}")


def test_snapshot_draft_blocks_invalid_mode():
    """Test snapshot_draft() blocks invalid mode."""
    client = GraphitiHttpClient()

    try:
        client.snapshot_draft("jv2-chat-test", mode="full")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "raw" in str(e)
        print(f"  snapshot_draft() blocks invalid mode: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_snapshot_draft_http_error_raises(mock_post):
    """Test snapshot_draft HTTP error raises."""
    from requests import HTTPError

    mock_response = Mock()
    mock_response.raise_for_status.side_effect = HTTPError("500 Server Error")
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()

    try:
        client.snapshot_draft("jv2-chat-test-day-2026-05-10")
        assert False, "Should have raised HTTPError"
    except HTTPError as e:
        print(f"  snapshot_draft HTTP error properly raised: {e}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.post")
def test_snapshot_draft_returns_json(mock_post):
    """Test snapshot_draft() returns parsed JSON response."""
    expected = {
        "group_id": "jv2-chat-test-day-2026-05-10",
        "mode": "raw",
        "counts": {"episodes": 5, "entities": 4, "edges": 3, "mentions": 6},
        "draft_text": "Snapshot draft text",
        "source": {"episodes": 5, "entities": 4, "edges": 3, "mentions": 6},
    }
    mock_response = Mock()
    mock_response.json.return_value = expected
    mock_post.return_value = mock_response

    client = GraphitiHttpClient()
    result = client.snapshot_draft("jv2-chat-test-day-2026-05-10")

    assert result == expected
    print("  snapshot_draft() returns correct JSON")


def test_custom_timeout():
    """Test custom timeout is applied."""
    client = GraphitiHttpClient(timeout=60.0)
    assert client.timeout == 60.0
    print(f"  custom timeout: {client.timeout}")


@patch("jasmine_v2.memory.graphiti_http_client.requests.get")
def test_timeout_applied_to_request(mock_get):
    """Test timeout is passed to each request."""
    mock_response = Mock()
    mock_response.json.return_value = {"status": "ok"}
    mock_get.return_value = mock_response

    client = GraphitiHttpClient(timeout=45.0)
    client.health()

    call_args = mock_get.call_args
    assert call_args[1]["timeout"] == 45.0
    print("  timeout correctly applied to request")


def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_default_base_url,
        test_env_base_url,
        test_trailing_slash_removed,
        test_health,
        test_config,
        test_add_episode,
        test_add_episode_with_reference_time,
        test_add_episode_blocks_legacy_group_id,
        test_search,
        test_search_with_multiple_group_ids,
        test_search_blocks_empty_group_ids,
        test_list_episodes,
        test_list_episodes_blocks_empty_group_id,
        test_group_stats,
        test_group_stats_with_special_chars,
        test_group_stats_blocks_empty_group_id,
        test_group_graph_calls_correct_url_and_params,
        test_group_graph_url_encodes_group_id,
        test_group_graph_blocks_empty_group_id,
        test_group_graph_http_error_raises,
        test_group_graph_returns_json,
        test_http_error_raises,
        test_add_episode_http_error_raises,
        test_search_http_error_raises,
        test_list_episodes_http_error_raises,
        test_group_stats_http_error_raises,
        test_snapshot_draft_calls_correct_url_and_payload,
        test_snapshot_draft_url_encodes_group_id,
        test_snapshot_draft_blocks_empty_group_id,
        test_snapshot_draft_blocks_invalid_mode,
        test_snapshot_draft_http_error_raises,
        test_snapshot_draft_returns_json,
        test_custom_timeout,
        test_timeout_applied_to_request,
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("Running test_v2_graphiti_http_client tests")
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
