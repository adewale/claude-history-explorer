"""Test configuration and fixtures for claude-history-explorer."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from claude_history_explorer.history import Message, Session, Project


def pytest_configure():
    """Configure pytest for our tests."""
    pass


def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def sample_message_data():
    """Sample message data for testing."""
    return {
        "type": "user",
        "message": {
            "content": "Hello, how are you?"
        },
        "timestamp": "2025-12-05T10:00:00Z"
    }


def sample_assistant_message_data():
    """Sample assistant message data with tool use."""
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": "I'll help you with that."
                },
                {
                    "type": "tool_use",
                    "name": "test_tool",
                    "input": {"param": "value"}
                }
            ]
        },
        "timestamp": "2025-12-05T10:01:00Z"
    }


def sample_tool_result_data():
    """Sample tool result message data."""
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "test_id",
                    "content": "Tool result"
                }
            ]
        },
        "timestamp": "2025-12-05T10:02:00Z"
    }


def sample_session_file(temp_dir_func):
    """Create a sample session JSONL file."""
    temp_path = temp_dir_func()
    session_file = temp_path / "test-session.jsonl"
    
    msg_data = sample_message_data()
    assistant_data = sample_assistant_message_data()
    
    with open(session_file, "w") as f:
        f.write(json.dumps(msg_data) + "\n")
        f.write(json.dumps(assistant_data) + "\n")
        f.write(json.dumps({"type": "other", "data": "ignored"}) + "\n")  # Should be ignored
    
    return session_file


def sample_project_dir(temp_dir_func):
    """Create a sample project directory structure."""
    temp_path = temp_dir_func()
    project_dir = temp_path / "-Users-test-project"
    project_dir.mkdir()
    
    # Create session file
    session_file = project_dir / "test-session.jsonl"
    msg_data = sample_message_data()
    assistant_data = sample_assistant_message_data()
    
    with open(session_file, "w") as f:
        f.write(json.dumps(msg_data) + "\n")
        f.write(json.dumps(assistant_data) + "\n")
    
    # Create an agent session file
    agent_file = project_dir / "agent-test.jsonl"
    agent_file.write_text(json.dumps({
        "type": "assistant",
        "message": {"content": "Agent response"}
    }) + "\n")
    
    return project_dir


def sample_project():
    """Create a sample Project object."""
    return Project(
        name="-Users-test-project",
        path="/Users/test/project",
        dir_path=Path("/mock/path"),
        session_files=[]
    )


def sample_session():
    """Create a sample Session object."""
    return Session(
        session_id="test-session",
        project_path="/Users/test/project",
        file_path=Path("/mock/test-session.jsonl"),
        messages=[
            Message(role="user", content="Hello", timestamp=None),
            Message(role="assistant", content="Hi there!", timestamp=None)
        ],
        start_time=None,
        end_time=None,
        slug="test-slug"
    )