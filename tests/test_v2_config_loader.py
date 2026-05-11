import json
import os
import sys
import tempfile
from unittest.mock import MagicMock

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Pre-seed fake langgraph module so jasmine_v2.core.graph can import without error
_fake_langgraph = MagicMock()
_fake_langgraph.graph.StateGraph = MagicMock
_fake_langgraph.graph.END = object()
sys.modules["langgraph"] = _fake_langgraph
sys.modules["langgraph.graph"] = _fake_langgraph.graph

from jasmine_v2.core.config import load_config
from jasmine_v2.core.events import IncomingEvent

# Mock build_jasmine_graph before importing runner
mock_graph = MagicMock()
mock_graph.invoke = lambda state: state

import jasmine_v2.core.graph
jasmine_v2.core.graph.build_jasmine_graph = lambda: mock_graph

# Reset runner module cache so it picks up the mock
if "jasmine_v2.core.runner" in sys.modules:
    del sys.modules["jasmine_v2.core.runner"]

from jasmine_v2.core.runner import run_event


def test_load_config_from_path():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"key": "value", "nested": {"a": 1}}, f)
        path = f.name

    try:
        result = load_config(path)
        assert result == {"key": "value", "nested": {"a": 1}}
    finally:
        os.unlink(path)

    print("PASS: test_load_config_from_path")


def test_load_config_missing_file():
    result = load_config("/nonexistent/path/config.json")
    assert result == {}
    print("PASS: test_load_config_missing_file")


def test_load_config_invalid_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write("this is not json {")
        path = f.name

    try:
        result = load_config(path)
        assert result == {}
    finally:
        os.unlink(path)

    print("PASS: test_load_config_invalid_json")


def test_load_config_default_path():
    # Default path should resolve to repo root config.json which exists and is valid
    result = load_config()
    assert isinstance(result, dict)
    assert "jasmine_filter" in result or result == {}
    print("PASS: test_load_config_default_path")


def test_runner_includes_config():
    event = IncomingEvent(
        transport="cli",
        chat_id="test_chat",
        user_id="test_user",
        user_name="Test",
        text="hello",
    )
    result = run_event(event)
    assert "config" in result
    assert isinstance(result["config"], dict)
    print("PASS: test_runner_includes_config")


if __name__ == "__main__":
    test_load_config_from_path()
    test_load_config_missing_file()
    test_load_config_invalid_json()
    test_load_config_default_path()
    test_runner_includes_config()
    print("\nAll tests passed!")
