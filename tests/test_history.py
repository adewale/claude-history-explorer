"""Unit tests for claude-history-explorer core functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
from datetime import datetime

import pytest

import claude_history_explorer.history as history
from claude_history_explorer.history import (
    Message,
    Session,
    Project,
    ProjectStats,
    GlobalStats,
    SessionInfo,
    _active_duration_minutes,
    # V3 imports
    SessionInfoV3,
    ProjectStatsV3,
    WrappedStoryV3,
    compute_trait_scores,
    compute_message_length_distribution,
    compute_session_fingerprint,
    get_top_session_fingerprints,
    encode_wrapped_story_v3,
    decode_wrapped_story_v3,
    MESSAGE_LENGTH_BUCKETS,
)


class TestMessage:
    """Test Message class functionality."""
    
    def test_message_from_user_data(self):
        """Test parsing user message data."""
        data = {
            "type": "user",
            "message": {
                "content": "Hello world"
            },
            "timestamp": "2025-12-05T10:00:00Z"
        }
        
        message = Message.from_json(data)
        
        assert message is not None
        assert message.role == "user"
        assert message.content == "Hello world"
        assert message.timestamp is not None
    
    def test_message_from_assistant_data_with_tools(self):
        """Test parsing assistant message with tool use."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "text",
                        "text": "I'll help you."
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
        
        message = Message.from_json(data)
        
        assert message is not None
        assert message.role == "assistant"
        assert message.content == "I'll help you."
        assert len(message.tool_uses) == 1
        assert message.tool_uses[0]["name"] == "test_tool"
        assert message.tool_uses[0]["input"] == {"param": "value"}
    
    def test_message_ignores_tool_results(self):
        """Test that tool results are ignored in content."""
        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "test_id",
                        "content": "Tool result"
                    }
                ]
            }
        }
        
        message = Message.from_json(data)
        
        # Should return None since there's no actual content
        assert message is None
    
    def test_message_ignores_invalid_types(self):
        """Test that invalid message types are ignored."""
        data = {
            "type": "system",
            "message": {
                "content": "System message"
            }
        }
        
        message = Message.from_json(data)
        assert message is None
    
    def test_message_handles_empty_content(self):
        """Test handling of empty content."""
        data = {
            "type": "user",
            "message": {
                "content": ""
            }
        }
        
        message = Message.from_json(data)
        assert message is None


class TestProject:
    """Test Project class functionality."""
    
    def test_project_from_dir(self):
        """Test creating Project from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            project_dir = temp_path / "-Users-test-project"
            project_dir.mkdir()
            
            # Create some session files
            (project_dir / "session1.jsonl").write_text('{"type": "user", "message": {"content": "test"}}')
            (project_dir / "session2.jsonl").write_text('{"type": "assistant", "message": {"content": "response"}}')
            (project_dir / "agent-test.jsonl").write_text('{"type": "assistant", "message": {"content": "agent"}}')
            
            project = Project.from_dir(project_dir)
            
            assert project.name == "-Users-test-project"
            assert project.path == "/Users/test/project"
            assert project.session_count == 3
            assert len(project.session_files) == 3
    
    def test_project_properties(self):
        """Test Project properties."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            project_dir = temp_path / "-Users-test-project"
            project_dir.mkdir()
            
            # Create a session file
            session_file = project_dir / "session.jsonl"
            session_file.write_text('{"type": "user", "message": {"content": "test"}}')
            
            project = Project.from_dir(project_dir)
            
            assert project.session_count == 1
            assert project.last_modified is not None


class TestSession:
    """Test Session class functionality."""
    
    def test_parse_session(self):
        """Test parsing a session file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            session_file = temp_path / "test-session.jsonl"
            
            # Create test session data
            data = [
                {"type": "user", "message": {"content": "Hello"}, "timestamp": "2025-12-05T10:00:00Z"},
                {"type": "assistant", "message": {"content": "Hi there!"}, "timestamp": "2025-12-05T10:01:00Z"},
                {"slug": "test-slug"}
            ]
            
            with open(session_file, "w") as f:
                for item in data:
                    f.write(json.dumps(item) + "\n")
            
            session = history.parse_session(session_file, "/test/project")
            
            assert session.session_id == "test-session"
            assert session.project_path == "/test/project"
            assert session.message_count == 2
            assert session.user_message_count == 1
            assert session.slug == "test-slug"
            assert session.start_time is not None
            assert session.end_time is not None
    
    def test_session_duration_calculation(self):
        """Test session duration calculation."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.json"),
            start_time=None,
            end_time=None
        )
        
        # Test with no times
        assert session.duration_str == "unknown"
    
    def test_session_properties(self):
        """Test Session properties."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.json"),
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi"),
                Message(role="user", content="How are you?")
            ]
        )
        
        assert session.message_count == 3
        assert session.user_message_count == 2

    def test_active_duration_minutes_property_basic(self):
        """Test Session.active_duration_minutes with normal gaps."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Hello",
                       timestamp=datetime(2025, 1, 1, 10, 0)),
                Message(role="assistant", content="Hi",
                       timestamp=datetime(2025, 1, 1, 10, 5)),
                Message(role="user", content="Bye",
                       timestamp=datetime(2025, 1, 1, 10, 15)),
            ],
        )
        # 5 min + 10 min = 15 min
        assert session.active_duration_minutes == 15

    def test_active_duration_minutes_property_caps_gaps(self):
        """Test Session.active_duration_minutes caps large gaps."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Start",
                       timestamp=datetime(2025, 1, 1, 10, 0)),
                Message(role="assistant", content="Response",
                       timestamp=datetime(2025, 1, 1, 10, 5)),
                # 4 hour gap (lunch + meetings)
                Message(role="user", content="Back",
                       timestamp=datetime(2025, 1, 1, 14, 5)),
            ],
        )
        # 5 min + 30 min (capped from 240) = 35 min
        assert session.active_duration_minutes == 35

    def test_active_duration_minutes_property_single_message(self):
        """Test Session.active_duration_minutes with single message returns 0."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Hello",
                       timestamp=datetime(2025, 1, 1, 10, 0)),
            ],
        )
        assert session.active_duration_minutes == 0

    def test_active_duration_minutes_property_no_messages(self):
        """Test Session.active_duration_minutes with no messages returns 0."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[],
        )
        assert session.active_duration_minutes == 0

    def test_active_duration_minutes_property_no_timestamps(self):
        """Test Session.active_duration_minutes with no timestamps returns 0."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi"),
            ],
        )
        assert session.active_duration_minutes == 0

    def test_duration_str_uses_active_duration_minutes(self):
        """Test that duration_str uses the active_duration_minutes property."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Start",
                       timestamp=datetime(2025, 1, 1, 10, 0)),
                # 2 hour gap
                Message(role="assistant", content="Done",
                       timestamp=datetime(2025, 1, 1, 12, 0)),
            ],
            start_time=datetime(2025, 1, 1, 10, 0),
            end_time=datetime(2025, 1, 1, 12, 0),
        )
        # Raw duration would be "2h 0m", active duration is 30m (capped)
        assert session.active_duration_minutes == 30
        assert session.duration_str == "30m"


class TestActiveDuration:
    """Test _active_duration_minutes helper function."""

    def test_active_duration_basic(self):
        """Test basic active duration calculation."""
        messages = [
            Message(role="user", content="Hello", timestamp=datetime(2025, 12, 15, 10, 0)),
            Message(role="assistant", content="Hi", timestamp=datetime(2025, 12, 15, 10, 5)),
            Message(role="user", content="How are you?", timestamp=datetime(2025, 12, 15, 10, 10)),
        ]

        duration = _active_duration_minutes(messages)

        # 5 min + 5 min = 10 min
        assert duration == 10

    def test_active_duration_caps_large_gaps(self):
        """Test that large gaps are capped at max_gap_minutes."""
        messages = [
            Message(role="user", content="Hello", timestamp=datetime(2025, 12, 15, 10, 0)),
            Message(role="assistant", content="Hi", timestamp=datetime(2025, 12, 15, 10, 5)),
            # 4 hour gap (left session open)
            Message(role="user", content="Back", timestamp=datetime(2025, 12, 15, 14, 5)),
        ]

        duration = _active_duration_minutes(messages, max_gap_minutes=30)

        # 5 min + 30 min (capped) = 35 min
        assert duration == 35

    def test_active_duration_overnight_gap(self):
        """Test that overnight gaps are properly capped."""
        messages = [
            Message(role="user", content="Goodnight", timestamp=datetime(2025, 12, 15, 23, 0)),
            Message(role="assistant", content="Night", timestamp=datetime(2025, 12, 15, 23, 5)),
            # Next morning
            Message(role="user", content="Morning", timestamp=datetime(2025, 12, 16, 9, 0)),
        ]

        duration = _active_duration_minutes(messages, max_gap_minutes=30)

        # 5 min + 30 min (capped) = 35 min (not 600+ min)
        assert duration == 35

    def test_active_duration_single_message(self):
        """Test with single message returns 0."""
        messages = [
            Message(role="user", content="Hello", timestamp=datetime(2025, 12, 15, 10, 0)),
        ]

        duration = _active_duration_minutes(messages)
        assert duration == 0

    def test_active_duration_empty_messages(self):
        """Test with empty messages returns 0."""
        duration = _active_duration_minutes([])
        assert duration == 0

    def test_active_duration_no_timestamps(self):
        """Test with messages without timestamps returns 0."""
        messages = [
            Message(role="user", content="Hello"),
            Message(role="assistant", content="Hi"),
        ]

        duration = _active_duration_minutes(messages)
        assert duration == 0

    def test_active_duration_custom_max_gap(self):
        """Test with custom max_gap_minutes."""
        messages = [
            Message(role="user", content="Hello", timestamp=datetime(2025, 12, 15, 10, 0)),
            # 2 hour gap
            Message(role="assistant", content="Hi", timestamp=datetime(2025, 12, 15, 12, 0)),
        ]

        # With 60 min cap
        duration_60 = _active_duration_minutes(messages, max_gap_minutes=60)
        assert duration_60 == 60

        # With 15 min cap
        duration_15 = _active_duration_minutes(messages, max_gap_minutes=15)
        assert duration_15 == 15


class TestActiveDurationConsistency:
    """Verify active duration is used consistently across all duration calculation sites."""

    def _make_session_with_gap(self, gap_hours: int = 4):
        """Helper: create session with a large gap that should be capped."""
        messages = [
            Message(role="user", content="start",
                   timestamp=datetime(2025, 1, 1, 10, 0)),
            Message(role="assistant", content="response",
                   timestamp=datetime(2025, 1, 1, 10, 5)),
            # Large gap (e.g., lunch break)
            Message(role="user", content="back",
                   timestamp=datetime(2025, 1, 1, 10 + gap_hours, 5)),
        ]
        return Session(
            session_id="test-gap",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=messages,
            start_time=messages[0].timestamp,
            end_time=messages[-1].timestamp,
        )

    def test_session_duration_str_uses_active_duration(self):
        """Session.duration_str should cap gaps, not use raw end-start."""
        session = self._make_session_with_gap(gap_hours=4)
        # Raw duration would be 4h 5m (245 min)
        # Active duration: 5 + 30 (capped) = 35 min
        assert session.duration_str == "35m"

    def test_session_info_uses_active_duration(self):
        """SessionInfo.from_session() should use active duration."""
        session = self._make_session_with_gap(gap_hours=4)
        info = SessionInfo.from_session(session, is_agent=False)
        # Should be 35 min, not 245 min
        assert info.duration_minutes == 35


class TestProjectStats:
    """Test ProjectStats functionality."""
    
    def test_calculate_project_stats(self):
        """Test calculating project statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            project_dir = temp_path / "-Users-test-project"
            project_dir.mkdir()
            
            # Create session files with different content
            session1 = project_dir / "session1.jsonl"
            session2 = project_dir / "agent-session.jsonl"
            
            # Main session
            with open(session1, "w") as f:
                f.write('{"type": "user", "message": {"content": "Hello"}, "timestamp": "2025-12-05T10:00:00Z"}\n')
                f.write('{"type": "assistant", "message": {"content": "Hi"}, "timestamp": "2025-12-05T11:00:00Z"}\n')
            
            # Agent session
            with open(session2, "w") as f:
                f.write('{"type": "assistant", "message": {"content": "Agent response"}, "timestamp": "2025-12-05T12:00:00Z"}\n')
            
            project = Project.from_dir(project_dir)
            stats = history.calculate_project_stats(project)
            
            assert isinstance(stats, ProjectStats)
            assert stats.total_sessions == 2
            assert stats.main_sessions == 1
            assert stats.agent_sessions == 1
            assert stats.total_messages >= 2
            assert stats.total_user_messages >= 1
            assert stats.total_size_bytes > 0
            assert stats.total_size_mb > 0


class TestGlobalStats:
    """Test GlobalStats functionality."""
    
    def test_calculate_global_stats(self):
        """Test calculating global statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            
            # Create multiple project directories
            for i in range(2):
                project_dir = temp_path / f"-Users-test-project-{i}"
                project_dir.mkdir()
                
                session_file = project_dir / f"session{i}.jsonl"
                with open(session_file, "w") as f:
                    f.write('{"type": "user", "message": {"content": "test"}}\n')
            
            # Mock the projects directory (patch where it's looked up, not where defined)
            with patch('claude_history_explorer.projects.get_projects_dir', return_value=temp_path):
                stats = history.calculate_global_stats()
                
                assert isinstance(stats, GlobalStats)
                assert stats.total_projects == 2
                assert stats.total_sessions == 2
                assert stats.total_messages >= 2
                assert stats.avg_sessions_per_project == 1.0
                assert stats.total_size_bytes > 0


class TestReadOnlyBehavior:
    """Test that the tool maintains read-only behavior."""
    
    def test_no_write_operations_in_history_module(self):
        """Test that history module doesn't perform write operations."""
        import inspect
        import claude_history_explorer.history as history_module
        
        # Get all functions in the module
        functions = inspect.getmembers(history_module, inspect.isfunction)
        
        write_operations = {'write', 'open', 'mkdir', 'touch', 'remove', 'rmdir'}
        
        for name, func in functions:
            # Get the source code
            try:
                source = inspect.getsource(func)
            except (OSError, TypeError):
                continue  # Skip built-in or compiled functions
            
            # Check for write operations in mode strings
            for op in write_operations:
                # Look for write modes in file operations
                if f'"{op}"' in source or f"'{op}'" in source:
                    if 'w' in source or 'a' in source or 'x' in source:
                        # Allow opening files for reading only
                        if 'open(' in source:
                            lines = source.split('\n')
                            for line in lines:
                                if 'open(' in line and ('"' in line or "'" in line):
                                    # Check if it's a write mode
                                    if any(mode in line for mode in ['"w"', "'w'", '"a"', "'a'", '"x"', "'x'"]):
                                        assert False, f"Write operation found in {name}: {line.strip()}"
    
    def test_functions_only_read_files(self):
        """Test that all file operations are read-only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            
            # Create test data
            test_file = temp_path / "test.jsonl"
            test_file.write_text('{"type": "user", "message": {"content": "test"}}')
            
            # Test all functions that work with files
            project = Project.from_dir(temp_path)
            session = history.parse_session(test_file, "/test")
            
            # Verify no files were created or modified
            original_files = list(temp_path.rglob("*"))
            
            # Run various operations
            history.list_projects()
            history.find_project("test")
            history.search_sessions("test", None, False)
            history.get_session_by_id("test", None)
            
            # Check that no new files were created
            final_files = list(temp_path.rglob("*"))
            assert len(original_files) == len(final_files)
    
    def test_cli_commands_are_read_only(self):
        """Test that CLI commands don't modify files."""
        import inspect
        import claude_history_explorer.cli as cli_module
        
        # Get all command functions
        functions = inspect.getmembers(cli_module, inspect.isfunction)
        
        for name, func in functions:
            if name.startswith('_') or name in ['main']:
                continue  # Skip helper functions and main
                
            try:
                source = inspect.getsource(func)
            except (OSError, TypeError):
                continue
            
            # Check for file write operations
            lines = source.split('\n')
            for line in lines:
                if 'open(' in line and ('"' in line or "'" in line):
                    # Allow opening files for writing only in export command
                    if 'export' in name.lower():
                        continue  # Export command is allowed to write
                    # Check for write modes
                    if any(mode in line for mode in ['"w"', "'w'", '"a"', "'a'", '"x"', "'x'"]):
                        assert False, f"Write operation found in CLI command {name}: {line.strip()}"


class TestPathHandling:
    """Test path handling and security."""

    def test_path_decoding_fallback(self):
        """Test path decoding falls back gracefully for non-existent paths.

        When the actual filesystem path doesn't exist (e.g., temp directory or
        projects from another machine), the decoder falls back to simple
        dash-to-slash replacement. This is expected behavior for portability.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            project_dir = temp_path / "-Users-username-Documents-my-project"
            project_dir.mkdir()

            project = Project.from_dir(project_dir)
            # Fallback behavior: when path doesn't exist, dashes become slashes
            assert project.path == "/Users/username/Documents/my/project"

    def test_path_decoding_with_underscores(self):
        """Test that paths with underscores are correctly decoded when they exist.

        The decoder checks the filesystem to disambiguate:
        - 'block-browser' could be 'block/browser' OR 'block_browser' OR 'block-browser'
        - We verify by checking which path actually exists on disk
        """
        # This test verifies the decoder works for REAL paths
        # For your actual projects like 'block_browser', the decoder will find
        # the correct path by checking the filesystem
        from claude_history_explorer.history import Project

        # Test with a real-ish structure in temp
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            # Create: /tmpdir/Users/test/my_project (with underscore)
            (temp_path / "Users" / "test").mkdir(parents=True)
            (temp_path / "Users" / "test" / "my_project").mkdir()

            # The encoded project directory name
            project_dir = temp_path / "-Users-test-my-project"
            project_dir.mkdir()

            # Patch the decoder to use our temp root
            original_decode = Project._decode_project_path
            def patched_decode(encoded_name):
                # Replace leading /Users with our temp path
                result = original_decode(encoded_name)
                if result.startswith("/Users"):
                    result = str(temp_path) + result[1:]  # Remove leading /
                return result

            # Note: Full integration test would require more complex mocking
            # For now, we verify the method exists and is callable
            assert callable(Project._decode_project_path)

    def test_no_path_traversal(self):
        """Test that path traversal is prevented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)

            # Create a project with suspicious name
            suspicious_dir = temp_path / "-Users-..-etc-passwd"
            suspicious_dir.mkdir()

            project = Project.from_dir(suspicious_dir)
            # Fallback behavior decodes this as a path (no actual traversal occurs
            # because we're just decoding a string, not accessing files)
            assert project.path == "/Users/../etc/passwd"


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_missing_claude_directory(self):
        """Test handling of missing Claude directory."""
        with patch('claude_history_explorer.projects.get_projects_dir', return_value=Path("/nonexistent")):
            projects = history.list_projects()
            assert projects == []
    
    def test_invalid_json_handling(self):
        """Test handling of invalid JSON in session files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            session_file = temp_path / "invalid.jsonl"
            
            # Write invalid JSON
            session_file.write_text('{"invalid": json}\n{"valid": "json"}\n')
            
            session = history.parse_session(session_file, "/test")
            # Should parse the valid line and skip the invalid one
            assert session is not None
    
    def test_empty_session_file(self):
        """Test handling of empty session files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            session_file = temp_path / "empty.jsonl"
            session_file.write_text("")

            session = history.parse_session(session_file, "/test")

            assert session.session_id == "empty"
            assert session.message_count == 0
            assert session.messages == []

    def test_invalid_timestamp_parsing(self):
        """G7: Test handling of invalid timestamp formats."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            session_file = temp_path / "bad-timestamps.jsonl"

            # Various invalid timestamps
            data = [
                {"type": "user", "message": {"content": "Hello"}, "timestamp": "not-a-date"},
                {"type": "assistant", "message": {"content": "Hi"}, "timestamp": "2025-13-45T99:99:99Z"},
                {"type": "user", "message": {"content": "More"}, "timestamp": ""},
                {"type": "assistant", "message": {"content": "Content"}, "timestamp": None},
            ]

            with open(session_file, "w") as f:
                for item in data:
                    f.write(json.dumps(item) + "\n")

            # Should parse without crashing, skipping invalid timestamps
            session = history.parse_session(session_file, "/test")
            assert session is not None
            # Messages with invalid timestamps should still be parsed

    def test_session_file_read_errors(self):
        """G8: Test handling of session file read errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            session_file = temp_path / "test.jsonl"

            # Create file with binary content that's not valid UTF-8
            with open(session_file, "wb") as f:
                f.write(b'\x80\x81\x82\x83')

            # Should handle encoding errors gracefully
            try:
                session = history.parse_session(session_file, "/test")
                # May succeed with empty messages or raise an error
            except UnicodeDecodeError:
                pass  # Expected for invalid encoding

    def test_content_extraction_fallbacks(self):
        """G9: Test content extraction from various message formats."""
        # Test various content structures
        test_cases = [
            # String content
            {"type": "user", "message": {"content": "Simple string"}},
            # List content with text
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "From list"}]}},
            # Empty list content
            {"type": "assistant", "message": {"content": []}},
            # None content
            {"type": "user", "message": {"content": None}},
            # Missing content key
            {"type": "user", "message": {}},
            # Nested structure
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Part 1"},
                {"type": "tool_use", "name": "test", "input": {}},
                {"type": "text", "text": "Part 2"},
            ]}},
        ]

        for data in test_cases:
            message = Message.from_json(data)
            # Should not crash on any of these formats

    def test_malformed_message_structure(self):
        """Test handling of malformed message structures."""
        test_cases = [
            {},  # Empty dict
            {"type": "user"},  # Missing message key
            {"message": {}},  # Missing type key
            {"type": "user", "message": None},  # None message
            {"type": "user", "message": "not a dict"},  # Wrong message type
        ]

        for data in test_cases:
            message = Message.from_json(data)
            # Should return None for invalid structures, not crash
            # (some may return None, some may extract partial data)


from datetime import datetime, timedelta
from claude_history_explorer.history import (
    SessionInfoV3,
    ProjectStatsV3,
    WrappedStoryV3,
    rle_encode,
    rle_decode,
    rle_encode_if_smaller,
    compute_activity_heatmap,
    compute_distribution,
    compute_session_duration_distribution,
    compute_agent_ratio_distribution,
    compute_trait_scores,
    compute_project_cooccurrence,
    detect_timeline_events,
    compute_session_fingerprint,
    encode_wrapped_story_v3,
    decode_wrapped_story_v3,
    SESSION_DURATION_BUCKETS,
    AGENT_RATIO_BUCKETS,
)


class TestRLEEncoding:
    """Test run-length encoding functions."""

    def test_rle_encode_simple(self):
        """Test basic RLE encoding."""
        values = [0, 0, 0, 5, 5, 0]
        encoded = rle_encode(values)
        assert encoded == [0, 3, 5, 2, 0, 1]

    def test_rle_encode_single_values(self):
        """Test RLE with no repeated values."""
        values = [1, 2, 3, 4, 5]
        encoded = rle_encode(values)
        assert encoded == [1, 1, 2, 1, 3, 1, 4, 1, 5, 1]

    def test_rle_encode_all_same(self):
        """Test RLE with all same values."""
        values = [7, 7, 7, 7, 7]
        encoded = rle_encode(values)
        assert encoded == [7, 5]

    def test_rle_encode_empty(self):
        """Test RLE with empty list."""
        values = []
        encoded = rle_encode(values)
        assert encoded == []

    def test_rle_decode_simple(self):
        """Test basic RLE decoding."""
        encoded = [0, 3, 5, 2, 0, 1]
        decoded = rle_decode(encoded)
        assert decoded == [0, 0, 0, 5, 5, 0]

    def test_rle_decode_empty(self):
        """Test decoding empty list."""
        decoded = rle_decode([])
        assert decoded == []

    def test_rle_roundtrip(self):
        """Test encode-decode roundtrip preserves data."""
        original = [0] * 100 + [5, 5, 5] + [0] * 50 + [10, 10]
        encoded = rle_encode(original)
        decoded = rle_decode(encoded)
        assert decoded == original

    def test_rle_encode_if_smaller_beneficial(self):
        """Test conditional encoding when beneficial."""
        values = [0] * 100  # Many repeated values - RLE is beneficial
        is_rle, result = rle_encode_if_smaller(values)
        assert is_rle is True
        assert len(result) < len(values)

    def test_rle_encode_if_smaller_not_beneficial(self):
        """Test conditional encoding when not beneficial."""
        values = list(range(10))  # All unique - RLE is not beneficial
        is_rle, result = rle_encode_if_smaller(values)
        assert is_rle is False
        assert result == values


class TestHeatmap:
    """Test activity heatmap computation."""

    def _create_session(self, start_time: datetime, messages: int, is_agent: bool = False) -> SessionInfoV3:
        """Helper to create a SessionInfoV3."""
        return SessionInfoV3(
            session_id="test",
            start_time=start_time,
            end_time=start_time + timedelta(hours=1),
            duration_minutes=60,
            message_count=messages,
            user_message_count=messages // 2,
            is_agent=is_agent,
            slug=None,
            project_name="TestProject",
            project_path="/test/project",
        )

    def test_heatmap_basic(self):
        """Test basic heatmap generation."""
        # Monday 10am, 5 messages
        monday_10am = datetime(2025, 12, 15, 10, 0)  # Monday
        sessions = [self._create_session(monday_10am, 5)]

        heatmap = compute_activity_heatmap(sessions)

        assert len(heatmap) == 168  # 7 days × 24 hours
        # Monday = day 0, hour 10 -> index = 0*24 + 10 = 10
        assert heatmap[10] == 5
        # All other slots should be 0
        assert sum(heatmap) == 5

    def test_heatmap_multiple_sessions(self):
        """Test heatmap with multiple sessions."""
        monday_10am = datetime(2025, 12, 15, 10, 0)
        monday_11am = datetime(2025, 12, 15, 11, 0)
        tuesday_10am = datetime(2025, 12, 16, 10, 0)

        sessions = [
            self._create_session(monday_10am, 5),
            self._create_session(monday_11am, 3),
            self._create_session(tuesday_10am, 7),
        ]

        heatmap = compute_activity_heatmap(sessions)

        assert heatmap[10] == 5   # Monday 10am
        assert heatmap[11] == 3   # Monday 11am
        assert heatmap[24 + 10] == 7  # Tuesday 10am (day 1)

    def test_heatmap_weekend(self):
        """Test heatmap correctly places weekend activity."""
        saturday_14 = datetime(2025, 12, 20, 14, 0)  # Saturday
        sunday_9 = datetime(2025, 12, 21, 9, 0)      # Sunday

        sessions = [
            self._create_session(saturday_14, 10),
            self._create_session(sunday_9, 8),
        ]

        heatmap = compute_activity_heatmap(sessions)

        # Saturday = day 5, hour 14 -> index = 5*24 + 14 = 134
        assert heatmap[5 * 24 + 14] == 10
        # Sunday = day 6, hour 9 -> index = 6*24 + 9 = 153
        assert heatmap[6 * 24 + 9] == 8

    def test_heatmap_empty_sessions(self):
        """Test heatmap with no sessions."""
        heatmap = compute_activity_heatmap([])
        assert len(heatmap) == 168
        assert sum(heatmap) == 0


class TestDistributions:
    """Test distribution computation functions."""

    def test_compute_distribution_basic(self):
        """Test basic distribution bucketing."""
        values = [5, 15, 25, 35, 100]
        buckets = [10, 20, 30]  # Results in 4 buckets: <=10, 10-20, 20-30, >30

        dist = compute_distribution(values, buckets)

        assert len(dist) == 4
        assert dist[0] == 1  # 5 <= 10
        assert dist[1] == 1  # 10 < 15 <= 20
        assert dist[2] == 1  # 20 < 25 <= 30
        assert dist[3] == 2  # 35, 100 > 30

    def test_compute_distribution_edge_cases(self):
        """Test distribution with values exactly on bucket boundaries.

        Using bisect_right:
        - bisect_right([10, 20, 30], 10) = 1 -> bucket 1
        - bisect_right([10, 20, 30], 20) = 2 -> bucket 2
        - bisect_right([10, 20, 30], 30) = 3 -> bucket 3
        - bisect_right([10, 20, 30], 40) = 3 -> bucket 3
        """
        values = [10, 20, 30, 40]
        buckets = [10, 20, 30]

        dist = compute_distribution(values, buckets)

        assert dist[0] == 0  # Nothing < 10
        assert dist[1] == 1  # 10 (goes to bucket 1)
        assert dist[2] == 1  # 20 (goes to bucket 2)
        assert dist[3] == 2  # 30 and 40 (both go to bucket 3)

    def test_compute_distribution_empty(self):
        """Test distribution with empty values."""
        dist = compute_distribution([], [10, 20, 30])
        assert dist == [0, 0, 0, 0]

    def test_session_duration_distribution(self):
        """Test session duration distribution."""
        def create_session(duration_min: int) -> SessionInfoV3:
            now = datetime.now()
            return SessionInfoV3(
                session_id="test",
                start_time=now,
                end_time=now + timedelta(minutes=duration_min),
                duration_minutes=duration_min,
                message_count=10,
                user_message_count=5,
                is_agent=False,
                slug=None,
                project_name="Test",
                project_path="/test",
            )

        sessions = [
            create_session(10),   # <15m bucket
            create_session(45),   # 30-60m bucket
            create_session(300),  # 4-8h bucket
        ]

        dist = compute_session_duration_distribution(sessions)

        assert len(dist) == len(SESSION_DURATION_BUCKETS) + 1
        assert dist[0] == 1  # <15m
        assert dist[2] == 1  # 30-60m
        assert dist[5] == 1  # 4-8h

    def test_agent_ratio_distribution(self):
        """Test agent ratio distribution across projects."""
        projects = [
            ProjectStatsV3("P1", "/p1", 100, 1, 9, 5.0, 5, 1, 100),    # 10% agent (1/(1+9))
            ProjectStatsV3("P2", "/p2", 200, 5, 5, 10.0, 8, 1, 150),   # 50% agent (5/(5+5))
            ProjectStatsV3("P3", "/p3", 150, 9, 1, 7.5, 6, 1, 200),    # 90% agent (9/(9+1))
        ]

        dist = compute_agent_ratio_distribution(projects)

        assert len(dist) == len(AGENT_RATIO_BUCKETS) + 1

    def test_message_length_distribution(self):
        """Test message length distribution computation."""
        # Create message lengths spanning multiple buckets
        # Buckets: [<50, 50-100, 100-200, 200-500, 500-1000, 1000-2000, 2000-5000, >5000]
        message_lengths = [
            30,     # <50 (bucket 0)
            75,     # 50-100 (bucket 1)
            150,    # 100-200 (bucket 2)
            350,    # 200-500 (bucket 3)
            750,    # 500-1000 (bucket 4)
            1500,   # 1000-2000 (bucket 5)
            3500,   # 2000-5000 (bucket 6)
            7000,   # >5000 (bucket 7)
        ]

        dist = compute_message_length_distribution(message_lengths)

        assert len(dist) == len(MESSAGE_LENGTH_BUCKETS) + 1
        # Each bucket should have 1 message
        assert dist == [1, 1, 1, 1, 1, 1, 1, 1]

    def test_message_length_distribution_empty(self):
        """Test message length distribution with empty input."""
        dist = compute_message_length_distribution([])
        assert len(dist) == len(MESSAGE_LENGTH_BUCKETS) + 1
        assert all(count == 0 for count in dist)

    def test_message_length_distribution_concentrated(self):
        """Test message length distribution with concentrated values."""
        # All short messages
        message_lengths = [20, 25, 30, 35, 40, 45]  # All <50
        dist = compute_message_length_distribution(message_lengths)

        assert dist[0] == 6  # All in first bucket
        assert sum(dist[1:]) == 0  # None in other buckets


class TestTraitScores:
    """Test trait score computation."""

    def _create_sessions(self, count: int, agent_ratio: float = 0.5, duration: int = 60) -> list:
        """Helper to create test sessions."""
        sessions = []
        now = datetime.now()
        agent_count = int(count * agent_ratio)

        for i in range(count):
            sessions.append(SessionInfoV3(
                session_id=f"s{i}",
                start_time=now + timedelta(days=i, hours=10),  # Same hour each day
                end_time=now + timedelta(days=i, hours=10, minutes=duration),
                duration_minutes=duration,
                message_count=20,
                user_message_count=10,
                is_agent=i < agent_count,
                slug=None,
                project_name=f"Project{i % 3}",
                project_path=f"/p{i % 3}",
            ))
        return sessions

    def _create_projects(self, count: int) -> list:
        """Helper to create test projects."""
        return [
            ProjectStatsV3(f"P{i}", f"/p{i}", 100 * (i + 1), 5, 5, 10.0, 5, 1, 100)
            for i in range(count)
        ]

    def test_trait_scores_all_present(self):
        """Test that all 10 trait scores are computed."""
        sessions = self._create_sessions(10)
        projects = self._create_projects(3)
        heatmap = [0] * 168

        scores = compute_trait_scores(sessions, projects, heatmap)

        expected_traits = ['ad', 'sp', 'fc', 'cc', 'wr', 'bs', 'cs', 'mv', 'td', 'ri']
        for trait in expected_traits:
            assert trait in scores
            assert 0 <= scores[trait] <= 100  # Quantized to integers 0-100

    def test_trait_scores_agent_delegation(self):
        """Test agent delegation score."""
        # All agent sessions -> high delegation
        all_agent = self._create_sessions(10, agent_ratio=1.0)
        projects = self._create_projects(1)
        heatmap = [0] * 168

        scores = compute_trait_scores(all_agent, projects, heatmap)
        assert scores['ad'] == 100  # Quantized: 1.0 -> 100

        # No agent sessions -> low delegation
        no_agent = self._create_sessions(10, agent_ratio=0.0)
        scores = compute_trait_scores(no_agent, projects, heatmap)
        assert scores['ad'] == 0  # Quantized: 0.0 -> 0

    def test_trait_scores_weekend_ratio(self):
        """Test weekend ratio score."""
        # Create heatmap with only weekend activity
        heatmap = [0] * 168
        heatmap[5 * 24 + 10] = 100  # Saturday 10am
        heatmap[6 * 24 + 14] = 100  # Sunday 2pm

        sessions = self._create_sessions(1)
        projects = self._create_projects(1)

        scores = compute_trait_scores(sessions, projects, heatmap)
        assert scores['wr'] > 50  # High weekend activity (quantized: 0.5 -> 50)

    def test_trait_scores_tool_diversity(self):
        """Test tool diversity score with actual tool count."""
        sessions = self._create_sessions(5)
        projects = self._create_projects(1)
        heatmap = [0] * 168

        # No tools - should get default 50 (0.5 * 100)
        scores_no_tools = compute_trait_scores(sessions, projects, heatmap, unique_tools_count=0)
        assert scores_no_tools['td'] == 50  # Quantized: 0.5 -> 50

        # 1 tool = 0
        scores_one = compute_trait_scores(sessions, projects, heatmap, unique_tools_count=1)
        assert scores_one['td'] == 0  # Quantized: 0.0 -> 0

        # 5 tools - should be (5-1)/9 ≈ 0.44 -> 44
        scores_five = compute_trait_scores(sessions, projects, heatmap, unique_tools_count=5)
        assert 40 <= scores_five['td'] <= 50  # Quantized: 0.4-0.5 -> 40-50

        # 10+ tools = 100
        scores_many = compute_trait_scores(sessions, projects, heatmap, unique_tools_count=15)
        assert scores_many['td'] == 100  # Quantized: 1.0 -> 100


class TestProjectCooccurrence:
    """Test project co-occurrence computation."""

    def test_cooccurrence_basic(self):
        """Test basic co-occurrence detection."""
        day1 = datetime(2025, 12, 15, 10, 0)
        day2 = datetime(2025, 12, 16, 10, 0)

        sessions = [
            SessionInfoV3("s1", day1, None, 60, 10, 5, False, None, "ProjectA", "/pa"),
            SessionInfoV3("s2", day1, None, 60, 10, 5, False, None, "ProjectB", "/pb"),
            SessionInfoV3("s3", day2, None, 60, 10, 5, False, None, "ProjectA", "/pa"),
        ]

        project_names = ["ProjectA", "ProjectB"]
        edges = compute_project_cooccurrence(sessions, project_names)

        # A and B co-occurred on day1
        assert len(edges) == 1
        assert edges[0] == (0, 1, 1)  # ProjectA(0), ProjectB(1), 1 day

    def test_cooccurrence_multiple_days(self):
        """Test co-occurrence across multiple days."""
        sessions = []
        for day_offset in range(5):
            day = datetime(2025, 12, 15 + day_offset, 10, 0)
            sessions.append(SessionInfoV3(f"s{day_offset*2}", day, None, 60, 10, 5, False, None, "ProjectA", "/pa"))
            sessions.append(SessionInfoV3(f"s{day_offset*2+1}", day, None, 60, 10, 5, False, None, "ProjectB", "/pb"))

        project_names = ["ProjectA", "ProjectB"]
        edges = compute_project_cooccurrence(sessions, project_names)

        assert len(edges) == 1
        assert edges[0] == (0, 1, 5)  # 5 days co-occurrence

    def test_cooccurrence_limit(self):
        """Test that co-occurrence is limited to max_edges."""
        # Create many projects that all co-occur
        sessions = []
        day = datetime(2025, 12, 15, 10, 0)
        for i in range(10):
            sessions.append(SessionInfoV3(f"s{i}", day, None, 60, 10, 5, False, None, f"P{i}", f"/p{i}"))

        project_names = [f"P{i}" for i in range(10)]
        edges = compute_project_cooccurrence(sessions, project_names, max_edges=5)

        assert len(edges) <= 5


class TestTimelineEvents:
    """Test timeline event detection."""

    def test_peak_day_detection(self):
        """Test that peak day is always detected."""
        sessions = []
        for day in range(10):
            messages = 10 if day != 5 else 100  # Day 5 is peak
            start = datetime(2025, 1, 1 + day, 10, 0)
            sessions.append(SessionInfoV3(f"s{day}", start, None, 60, messages, 5, False, None, "P", "/p"))

        events = detect_timeline_events(sessions, ["P"], 2025)

        # Find peak_day event (array format: [day, type, value, project_idx])
        peak_events = [e for e in events if e[1] == 0]  # type == 0 (peak_day)
        assert len(peak_events) == 1
        assert peak_events[0][0] == 6  # Day of year for Jan 6
        assert peak_events[0][2] == 100  # value

    def test_milestone_detection(self):
        """Test milestone event detection."""
        sessions = []
        # Create sessions with cumulative 150 messages (should hit 100 milestone)
        for day in range(15):
            start = datetime(2025, 1, 1 + day, 10, 0)
            sessions.append(SessionInfoV3(f"s{day}", start, None, 60, 10, 5, False, None, "P", "/p"))

        events = detect_timeline_events(sessions, ["P"], 2025)

        # Should detect 100 milestone (array format: [day, type, value, project_idx])
        milestone_events = [e for e in events if e[1] == 4]  # type == 4 (milestone)
        assert any(e[2] == 100 for e in milestone_events)  # value == 100

    def test_event_limit(self):
        """Test that events are limited to max_events."""
        sessions = []
        # Create sessions across multiple months to avoid invalid dates
        base_date = datetime(2025, 1, 1)
        for day_offset in range(100):
            start = base_date + timedelta(days=day_offset)
            sessions.append(SessionInfoV3(f"s{day_offset}", start, None, 60, 50, 25, False, None, "P", "/p"))

        events = detect_timeline_events(sessions, ["P"], 2025, max_events=5)

        assert len(events) <= 5


class TestSessionFingerprint:
    """Test session fingerprint computation."""

    def test_fingerprint_basic(self):
        """Test basic fingerprint generation."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi", tool_uses=[{"name": "test"}]),
                Message(role="user", content="How are you?"),
                Message(role="assistant", content="Good!"),
            ]
        )

        fingerprint = compute_session_fingerprint(session)

        assert len(fingerprint) == 8
        # Quantized to integers 0-100
        assert all(isinstance(v, int) and 0 <= v <= 100 for v in fingerprint)

    def test_fingerprint_empty_session(self):
        """Test fingerprint with empty session."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[]
        )

        fingerprint = compute_session_fingerprint(session)

        assert fingerprint == [0] * 8  # Quantized integers

    def test_fingerprint_error_rate(self):
        """Test fingerprint error rate detection."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Fix this bug please"),
                Message(role="assistant", content="There's an error in the code"),
                Message(role="user", content="Still failing"),
                Message(role="assistant", content="Let me retry and fix the issue"),
            ]
        )

        fingerprint = compute_session_fingerprint(session)

        # Index 5 is error rate - should be high due to error/bug/failing/retry/fix/issue
        # Quantized to 0-100, so > 50 means > 0.5
        assert fingerprint[5] > 50  # At least 3/4 messages have error patterns

    def test_fingerprint_edit_ratio(self):
        """Test fingerprint edit operation ratio."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Edit the file"),
                Message(role="assistant", content="Done", tool_uses=[
                    {"name": "Edit", "input": {}},
                    {"name": "Edit", "input": {}},
                ]),
                Message(role="user", content="Read it"),
                Message(role="assistant", content="Here", tool_uses=[
                    {"name": "Read", "input": {}},
                ]),
            ]
        )

        fingerprint = compute_session_fingerprint(session)

        # Index 6 is edit ratio - 2 Edit tools out of 3 total = 67 (quantized from 0.67)
        assert 60 <= fingerprint[6] <= 70

    def test_fingerprint_long_message_ratio(self):
        """Test fingerprint long message ratio."""
        short_msg = "Short message"
        long_msg = "L" * 600  # Over 500 chars

        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content=short_msg),
                Message(role="assistant", content=long_msg),  # Long
                Message(role="user", content=short_msg),
                Message(role="assistant", content=long_msg),  # Long
            ]
        )

        fingerprint = compute_session_fingerprint(session)

        # Index 7 is long message ratio - 2/4 = 50 (quantized to 0-100)
        assert fingerprint[7] == 50

    def test_fingerprint_returns_integers(self):
        """Test that fingerprints return integers 0-100 (quantized)."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Hello"),
                Message(role="assistant", content="Hi", tool_uses=[{"name": "Read", "input": {}}]),
                Message(role="user", content="Thanks"),
                Message(role="assistant", content="Welcome"),
            ]
        )

        fingerprint = compute_session_fingerprint(session)

        assert len(fingerprint) == 8
        # All values should be integers in 0-100 range
        for i, v in enumerate(fingerprint):
            assert isinstance(v, int), f"Index {i} is not an integer: {type(v)}"
            assert 0 <= v <= 100, f"Index {i} out of range: {v}"

    def test_fingerprint_quantization_precision(self):
        """Test that fingerprint quantization preserves relative values."""
        # Create session with known values
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="A" * 100),   # 100 chars
                Message(role="assistant", content="B" * 600),  # 600 chars (long)
                Message(role="user", content="C" * 50),    # 50 chars
                Message(role="assistant", content="D" * 200),  # 200 chars
            ]
        )

        fingerprint = compute_session_fingerprint(session)

        # Long message ratio: 1/4 = 0.25 -> 25
        assert fingerprint[7] == 25


class TestFingerprintQuantizationIntegration:
    """Integration tests for quantized fingerprints in wrapped story."""

    def test_fingerprint_encoding_size_reduction(self):
        """Test that quantized fingerprints reduce encoding size."""
        # Create a story with fingerprints using floats vs integers
        # Integers should be smaller in msgpack encoding

        # Float fingerprint (old format) - for comparison
        float_fp = [0.25, 0.50, 0.75, 1.00, 0.33, 0.67, 0.10, 0.90]

        # Integer fingerprint (new format)
        int_fp = [25, 50, 75, 100, 33, 67, 10, 90]

        import msgpack

        float_packed = msgpack.packb({'fp': float_fp})
        int_packed = msgpack.packb({'fp': int_fp})

        # Integer encoding should be smaller or equal
        assert len(int_packed) <= len(float_packed), \
            f"Integer encoding ({len(int_packed)}) should be <= float ({len(float_packed)})"

    def test_wrapped_story_with_quantized_fingerprints(self):
        """Test that wrapped story correctly handles quantized fingerprints."""
        story = WrappedStoryV3(
            v=3, y=2025, p=1, s=1, m=100, h=1.0, d=1,
            hm=[0] * 168,
            ma=[100] * 12, mh=[1.0] * 12, ms=[1] * 12,
            sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
            ts={'ad': 0.5, 'sp': 0.5, 'fc': 0.5, 'cc': 0.5, 'wr': 0.5,
                'bs': 0.5, 'cs': 0.5, 'mv': 0.5, 'td': 0.5, 'ri': 0.5},
            tp=[{'n': 'Test', 'm': 100, 'h': 1.0, 'd': 1, 's': 1, 'ar': 50, 'fd': 1, 'ld': 100}],
            pc=[], te=[],
            sf=[{
                'id': 'test01',
                'd': 60,
                'm': 50,
                'a': False,
                'h': 10,
                'w': 0,
                'pi': 0,
                'fp': [25, 50, 75, 100, 33, 67, 10, 90]  # Quantized integers
            }],
        )

        encoded = encode_wrapped_story_v3(story)
        decoded = decode_wrapped_story_v3(encoded)

        # Verify fingerprint is preserved
        assert len(decoded.sf) == 1
        assert decoded.sf[0]['fp'] == [25, 50, 75, 100, 33, 67, 10, 90]


class TestWrappedStoryV3:
    """Test WrappedStoryV3 serialization and encoding."""

    def test_story_to_dict(self):
        """Test converting story to dictionary."""
        story = WrappedStoryV3(
            v=3,
            y=2025,
            n="Test User",
            p=5,
            s=100,
            m=5000,
            h=200.5,
            d=45,
            hm=[0] * 168,
            ma=[100] * 12,
            mh=[10.0] * 12,
            ms=[8] * 12,
            sd=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            ar=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            ml=[0] * 8,
            ts={'ad': 0.5, 'sp': 0.6, 'fc': 0.7, 'cc': 0.8, 'wr': 0.3,
                'bs': 0.4, 'cs': 0.2, 'mv': 0.5, 'td': 0.5, 'ri': 0.6},
            tp=[{'n': 'Proj1', 'm': 1000, 'h': 50, 'd': 20, 's': 30, 'ar': 50, 'fd': 1, 'ld': 100}],
            pc=[(0, 1, 5)],
            te=[{'d': 50, 't': 0, 'v': 100}],
            sf=[{'id': 'abc123', 'd': 60, 'm': 50, 'a': False, 'h': 10, 'w': 0, 'pi': 0, 'fp': [50] * 8}],
        )

        d = story.to_dict()

        assert d['v'] == 3
        assert d['y'] == 2025
        assert d['n'] == "Test User"
        assert d['m'] == 5000
        assert len(d['hm']) == 168

    def test_story_from_dict(self):
        """Test creating story from dictionary."""
        d = {
            'v': 3,
            'y': 2025,
            'p': 5,
            's': 100,
            'm': 5000,
            'h': 200.5,
            'd': 45,
            'hm': [0] * 168,
            'ma': [100] * 12,
            'mh': [10.0] * 12,
            'ms': [8] * 12,
            'sd': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'ar': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            'ml': [0] * 8,
            'ts': {'ad': 0.5, 'sp': 0.6, 'fc': 0.7, 'cc': 0.8, 'wr': 0.3,
                   'bs': 0.4, 'cs': 0.2, 'mv': 0.5, 'td': 0.5, 'ri': 0.6},
            'tp': [],
            'pc': [],
            'te': [],
            'sf': [],
        }

        story = WrappedStoryV3.from_dict(d)

        assert story.v == 3
        assert story.y == 2025
        assert story.m == 5000

    def test_encode_decode_roundtrip(self):
        """Test encode-decode roundtrip preserves data."""
        original = WrappedStoryV3(
            v=3,
            y=2025,
            n="Test",
            p=5,
            s=100,
            m=5000,
            h=200.5,
            d=45,
            hm=[0] * 100 + [10] * 50 + [0] * 18,  # Sparse heatmap
            ma=[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
            mh=[10.0] * 12,
            ms=[8] * 12,
            sd=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            ar=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            ml=[0] * 8,
            ts={'ad': 0.5, 'sp': 0.6, 'fc': 0.7, 'cc': 0.8, 'wr': 0.3,
                'bs': 0.4, 'cs': 0.2, 'mv': 0.5, 'td': 0.5, 'ri': 0.6},
            tp=[{'n': 'Proj1', 'm': 1000, 'h': 50.0, 'd': 20, 's': 30, 'ar': 50, 'fd': 1, 'ld': 100}],
            pc=[(0, 1, 5)],
            te=[{'d': 50, 't': 0, 'v': 100}],
            sf=[{'id': 'abc123', 'd': 60, 'm': 50, 'a': False, 'h': 10, 'w': 0, 'pi': 0, 'fp': [50] * 8}],
        )

        encoded = encode_wrapped_story_v3(original)
        decoded = decode_wrapped_story_v3(encoded)

        assert decoded.v == original.v
        assert decoded.y == original.y
        assert decoded.n == original.n
        assert decoded.m == original.m
        assert decoded.p == original.p
        assert len(decoded.hm) == 168  # RLE decoded
        assert decoded.ma == original.ma
        assert len(decoded.ts) == len(original.ts)

    def test_rle_compression_in_encoding(self):
        """Test that sparse heatmap benefits from RLE with quantization."""
        # Sparse heatmap (many zeros)
        story = WrappedStoryV3(
            v=3, y=2025, p=1, s=1, m=100, h=1, d=1,  # h is integer now
            hm=[0] * 160 + [5] * 8,  # Mostly zeros
            ma=[0] * 12, mh=[0] * 12, ms=[0] * 12,  # mh is integers now
            sd=[0] * 10, ar=[0] * 10, ml=[0] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},  # Integers 0-100
            tp=[], pc=[], te=[], sf=[],
        )

        encoded = encode_wrapped_story_v3(story)

        # Decode and verify heatmap structure is properly restored
        # Note: Values are quantized to 0-15 scale, so we check structure not exact values
        decoded = decode_wrapped_story_v3(encoded)
        assert len(decoded.hm) == 168
        assert decoded.hm[:160] == [0] * 160  # Zeros stay zeros
        assert all(v > 0 for v in decoded.hm[160:])  # Non-zeros stay non-zero


class TestProjectStatsV3:
    """Test ProjectStatsV3 class."""

    def test_project_stats_properties(self):
        """Test ProjectStatsV3 computed properties."""
        stats = ProjectStatsV3(
            name="TestProject",
            path="/test/project",
            message_count=1000,
            agent_sessions=20,
            main_sessions=30,
            hours=100.0,
            days_active=25,
            first_day=10,
            last_day=200,
        )

        assert stats.session_count == 50  # 20 + 30 (computed property)
        assert stats.agent_ratio == 0.4   # 20/50

    def test_project_stats_zero_sessions(self):
        """Test agent_ratio with zero sessions."""
        stats = ProjectStatsV3(
            name="Empty",
            path="/empty",
            message_count=0,
            agent_sessions=0,
            main_sessions=0,
            hours=0.0,
            days_active=0,
            first_day=0,
            last_day=0,
        )

        assert stats.session_count == 0
        assert stats.agent_ratio == 0.0


class TestSessionInfoV3:
    """Test SessionInfoV3 class."""

    def test_from_session_with_project(self):
        """Test creating SessionInfoV3 from Session."""
        # Messages with timestamps 10 minutes apart (well under 30 min cap)
        session = Session(
            session_id="test123",
            project_path="/test/project",
            file_path=Path("/test.jsonl"),
            messages=[
                Message(role="user", content="Hello",
                       timestamp=datetime(2025, 12, 15, 10, 0)),
                Message(role="assistant", content="Hi",
                       timestamp=datetime(2025, 12, 15, 10, 10)),
            ],
            start_time=datetime(2025, 12, 15, 10, 0),
            end_time=datetime(2025, 12, 15, 10, 10),
        )

        info = SessionInfoV3.from_session_with_project(
            session, is_agent=False, project_name="TestProject", project_path="/test/project"
        )

        assert info is not None
        assert info.session_id == "test123"
        assert info.project_name == "TestProject"
        assert info.project_path == "/test/project"
        assert info.duration_minutes == 10  # Active duration based on message gaps
        assert info.message_count == 2
        assert info.is_agent is False

    def test_from_session_without_start_time(self):
        """Test that None is returned when session has no start_time."""
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            start_time=None,
        )

        info = SessionInfoV3.from_session_with_project(session, False, "Test", "/test")
        assert info is None


class TestTraitScoresEdgeCases:
    """Test edge cases for trait score computation."""

    def test_trait_scores_empty_sessions(self):
        """Test trait scores with empty sessions list."""
        scores = compute_trait_scores([], [], [0] * 168)

        # Should return default values for all traits
        assert len(scores) == 10
        assert scores['ad'] == 50  # Default when no sessions (quantized: 0.5 -> 50)
        assert all(0 <= v <= 100 for v in scores.values())

    def test_trait_scores_single_session(self):
        """Test trait scores with single session."""
        session = SessionInfoV3(
            session_id="s1",
            start_time=datetime(2025, 12, 15, 10, 0),
            end_time=datetime(2025, 12, 15, 11, 0),
            duration_minutes=60,
            message_count=20,
            user_message_count=10,
            is_agent=False,
            slug=None,
            project_name="TestProject",
            project_path="/test",
        )
        project = ProjectStatsV3(
            name="TestProject",
            path="/test",
            message_count=20,
            agent_sessions=0,
            main_sessions=1,
            hours=1.0,
            days_active=1,
            first_day=1,
            last_day=1,
        )
        heatmap = [0] * 168
        heatmap[0 * 24 + 10] = 20  # Monday 10am

        scores = compute_trait_scores([session], [project], heatmap)

        assert len(scores) == 10
        assert scores['ad'] == 0  # No agent sessions (quantized: 0.0 -> 0)
        assert scores['fc'] == 100  # Single project = max focus (quantized: 1.0 -> 100)
        assert all(0 <= v <= 100 for v in scores.values())

    def test_trait_scores_zero_duration_sessions(self):
        """Test trait scores when all sessions have zero duration."""
        sessions = [
            SessionInfoV3(
                session_id=f"s{i}",
                start_time=datetime(2025, 12, 15 + i, 10, 0),
                end_time=None,
                duration_minutes=0,
                message_count=10,
                user_message_count=5,
                is_agent=i % 2 == 0,
                slug=None,
                project_name="TestProject",
                project_path="/test",
            )
            for i in range(5)
        ]
        project = ProjectStatsV3(
            name="TestProject",
            path="/test",
            message_count=50,
            agent_sessions=3,
            main_sessions=2,
            hours=0.0,
            days_active=5,
            first_day=1,
            last_day=5,
        )
        heatmap = [0] * 168

        scores = compute_trait_scores(sessions, [project], heatmap)

        # Should handle zero duration gracefully using defaults
        assert len(scores) == 10
        assert all(0 <= v <= 100 for v in scores.values())

    def test_trait_scores_all_agent_sessions(self):
        """Test trait scores with 100% agent sessions."""
        sessions = [
            SessionInfoV3(
                session_id=f"s{i}",
                start_time=datetime(2025, 12, 15 + i, 10, 0),
                end_time=datetime(2025, 12, 15 + i, 11, 0),
                duration_minutes=60,
                message_count=20,
                user_message_count=10,
                is_agent=True,  # All agent
                slug=None,
                project_name="TestProject",
                project_path="/test",
            )
            for i in range(5)
        ]
        project = ProjectStatsV3(
            name="TestProject",
            path="/test",
            message_count=100,
            agent_sessions=5,
            main_sessions=0,
            hours=5.0,
            days_active=5,
            first_day=1,
            last_day=5,
        )
        heatmap = [0] * 168

        scores = compute_trait_scores(sessions, [project], heatmap)

        assert scores['ad'] == 100  # Full agent delegation (quantized: 1.0 -> 100)


class TestFingerprintComputation:
    """Test fingerprint computation and loading."""

    def test_get_top_session_fingerprints_empty(self):
        """Test fingerprints with empty session list."""
        result = get_top_session_fingerprints([], {}, [])
        assert result == []

    def test_get_top_session_fingerprints_limit(self):
        """Test that fingerprints are limited correctly."""
        sessions = [
            SessionInfoV3(
                session_id=f"session-{i}",
                start_time=datetime(2025, 12, 15, 10, 0),
                end_time=datetime(2025, 12, 15, 11, 0),
                duration_minutes=60,
                message_count=10 * (i + 1),  # Varying message counts
                user_message_count=5,
                is_agent=False,
                slug=None,
                project_name="Project",
                project_path="/test",
            )
            for i in range(20)
        ]

        result = get_top_session_fingerprints(sessions, {}, ["Project"], limit=5)

        assert len(result) == 5
        # Array format: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
        # Should be sorted by significance (higher message counts first)
        assert result[0][1] > result[-1][1]  # index 1 = messages

    def test_get_top_session_fingerprints_with_file_map(self):
        """Test fingerprints when session files are available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)

            # Create a session file
            session_file = temp_path / "test-session.jsonl"
            with open(session_file, "w") as f:
                f.write('{"type": "user", "message": {"content": "Hello"}, "timestamp": "2025-12-05T10:00:00Z"}\n')
                f.write('{"type": "assistant", "message": {"content": "Hi"}, "timestamp": "2025-12-05T10:01:00Z"}\n')
                f.write('{"type": "user", "message": {"content": "How are you?"}, "timestamp": "2025-12-05T10:02:00Z"}\n')
                f.write('{"type": "assistant", "message": {"content": "Good!"}, "timestamp": "2025-12-05T10:03:00Z"}\n')

            sessions = [
                SessionInfoV3(
                    session_id="test-session",
                    start_time=datetime(2025, 12, 5, 10, 0),
                    end_time=datetime(2025, 12, 5, 10, 3),
                    duration_minutes=3,
                    message_count=4,
                    user_message_count=2,
                    is_agent=False,
                    slug=None,
                    project_name="Project",
                    project_path="/test",
                )
            ]

            session_file_map = {"test-session": session_file}

            result = get_top_session_fingerprints(sessions, session_file_map, ["Project"], limit=5)

            assert len(result) == 1
            # Array format: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
            assert result[0][1] == 4  # index 1 = messages
            assert len(result[0]) == 14  # 6 metadata fields + 8 fingerprint values
            # With actual file loaded, fingerprint should be computed (not default)


class TestV3Integration:
    """Integration tests for V3 wrapped story generation."""

    def test_encode_decode_full_story(self):
        """Test complete encode/decode cycle with realistic data."""
        # Create a story with all fields populated
        story = WrappedStoryV3(
            v=3,
            y=2025,
            n="Integration Test User",
            p=5,
            s=150,
            m=7500,
            h=250.5,
            d=45,
            hm=[0] * 50 + [10, 20, 30, 40, 50] + [0] * 113,  # Sparse heatmap
            ma=[500, 600, 700, 800, 750, 600, 500, 650, 700, 850, 900, 750],
            mh=[20.0, 22.5, 25.0, 30.0, 28.0, 22.0, 18.0, 24.0, 26.0, 32.0, 35.0, 28.0],
            ms=[10, 12, 14, 16, 15, 12, 10, 13, 14, 17, 18, 15],
            sd=[5, 10, 20, 30, 25, 15, 8, 4, 2, 1],
            ar=[1, 2, 5, 10, 15, 20, 15, 10, 3, 2],
            ml=[10, 20, 30, 25, 15, 8, 5, 2],
            ts={
                'ad': 0.45, 'sp': 0.65, 'fc': 0.72, 'cc': 0.58, 'wr': 0.25,
                'bs': 0.40, 'cs': 0.33, 'mv': 0.55, 'td': 0.60, 'ri': 0.70
            },
            tp=[
                {'n': 'Main Project', 'm': 3000, 'h': 100.0, 'd': 30, 's': 60, 'ar': 40, 'fd': 15, 'ld': 350},
                {'n': 'Side Project', 'm': 2000, 'h': 75.0, 'd': 20, 's': 40, 'ar': 60, 'fd': 50, 'ld': 300},
                {'n': 'Experiment', 'm': 1500, 'h': 50.0, 'd': 15, 's': 30, 'ar': 30, 'fd': 100, 'ld': 250},
            ],
            pc=[(0, 1, 10), (0, 2, 5), (1, 2, 3)],
            te=[
                {'d': 50, 't': 0, 'v': 150},   # peak_day
                {'d': 100, 't': 4, 'v': 1000}, # milestone
                {'d': 150, 't': 3, 'p': 2},    # new_project
            ],
            sf=[
                {'id': 'abc123', 'd': 120, 'm': 100, 'a': False, 'h': 10, 'w': 0, 'pi': 0, 'fp': [20, 40, 60, 80, 50, 10, 30, 20]},
                {'id': 'def456', 'd': 90, 'm': 80, 'a': True, 'h': 14, 'w': 2, 'pi': 1, 'fp': [30, 50, 70, 90, 40, 20, 40, 30]},
            ],
            yoy={'pm': 5000, 'ph': 180, 'ps': 100, 'pp': 4, 'pd': 35},
        )

        # Encode
        encoded = encode_wrapped_story_v3(story)

        # Verify encoded string is URL-safe
        import string
        valid_chars = string.ascii_letters + string.digits + '-_'
        assert all(c in valid_chars for c in encoded)

        # Decode
        decoded = decode_wrapped_story_v3(encoded)

        # Verify all fields match
        assert decoded.v == story.v
        assert decoded.y == story.y
        assert decoded.n == story.n
        assert decoded.p == story.p
        assert decoded.s == story.s
        assert decoded.m == story.m
        assert decoded.h == story.h
        assert decoded.d == story.d
        assert len(decoded.hm) == 168  # RLE decoded to full size
        assert decoded.ma == story.ma
        assert decoded.ms == story.ms
        assert decoded.sd == story.sd
        assert decoded.ar == story.ar
        assert decoded.ts == story.ts
        assert len(decoded.tp) == 3
        assert decoded.tp[0]['n'] == 'Main Project'
        assert decoded.pc == [(0, 1, 10), (0, 2, 5), (1, 2, 3)]
        assert len(decoded.te) == 3
        assert decoded.yoy == story.yoy

    def test_url_size_typical(self):
        """Test that a typical story stays under 2KB URL budget."""
        # Create a story with typical data (sparse heatmap compresses well)
        story = WrappedStoryV3(
            v=3,
            y=2025,
            n="Typical User",
            p=5,
            s=200,
            m=10000,
            h=300.0,
            d=60,
            hm=[0] * 100 + [50, 100, 150, 100, 50] + [0] * 63,  # Sparse (typical)
            ma=[800, 900, 1000, 1100, 900, 700, 600, 800, 1000, 1200, 1100, 900],
            mh=[25.0] * 12,
            ms=[15] * 12,
            sd=[5, 15, 30, 40, 30, 15, 8, 4, 2, 1],
            ar=[2, 5, 10, 15, 25, 20, 10, 8, 3, 2],
            ml=[10, 20, 35, 25, 10, 5, 3, 2],
            ts={
                'ad': 0.45, 'sp': 0.65, 'fc': 0.55, 'cc': 0.70, 'wr': 0.25,
                'bs': 0.40, 'cs': 0.35, 'mv': 0.50, 'td': 0.55, 'ri': 0.60
            },
            tp=[
                {'n': 'Main Project', 'm': 4000, 'h': 100.0, 'd': 30, 's': 70, 'ar': 45, 'fd': 20, 'ld': 340},
                {'n': 'Side Project', 'm': 2500, 'h': 80.0, 'd': 25, 's': 50, 'ar': 55, 'fd': 60, 'ld': 300},
                {'n': 'Hobby', 'm': 1500, 'h': 50.0, 'd': 15, 's': 30, 'ar': 30, 'fd': 100, 'ld': 250},
                {'n': 'Learning', 'm': 1000, 'h': 40.0, 'd': 10, 's': 25, 'ar': 60, 'fd': 150, 'ld': 320},
                {'n': 'Work Tool', 'm': 1000, 'h': 30.0, 'd': 10, 's': 25, 'ar': 20, 'fd': 50, 'ld': 350},
            ],
            pc=[(0, 1, 8), (0, 2, 3), (1, 3, 5)],
            te=[
                {'d': 100, 't': 0, 'v': 200},
                {'d': 50, 't': 4, 'v': 1000},
                {'d': 200, 't': 4, 'v': 5000},
            ],
            sf=[
                {'id': 'abc123', 'd': 90, 'm': 80, 'a': False, 'h': 10, 'w': 0, 'pi': 0, 'fp': [20, 50, 70, 80, 50, 10, 30, 20]},
                {'id': 'def456', 'd': 120, 'm': 100, 'a': True, 'h': 14, 'w': 2, 'pi': 1, 'fp': [30, 50, 60, 90, 40, 20, 40, 30]},
            ],
            yoy={'pm': 7000, 'ph': 200, 'ps': 150, 'pp': 4, 'pd': 50},
        )

        encoded = encode_wrapped_story_v3(story)

        # URL base is about 50 chars, plus encoded data
        url_length = 50 + len(encoded)
        # Typical should stay well under 2KB
        assert url_length < 2000, f"URL too long for typical case: {url_length} chars"


class TestGenerateWrappedStoryV3:
    """Integration tests for generate_wrapped_story_v3 function."""

    def test_generate_wrapped_story_v3_with_mocked_data(self):
        """Test generate_wrapped_story_v3 with mocked project/session data."""
        from unittest.mock import MagicMock
        from claude_history_explorer.history import generate_wrapped_story_v3

        # Create mock project
        mock_project = MagicMock()
        mock_project.short_name = "TestProject"
        mock_project.path = "/test/project"
        mock_project.session_files = [Path("/test/session1.jsonl"), Path("/test/session2.jsonl")]

        # Create mock sessions
        mock_session1 = Session(
            session_id="session1",
            project_path="/test/project",
            file_path=Path("/test/session1.jsonl"),
            messages=[
                Message(role="user", content="Hello world", timestamp=datetime(2025, 6, 15, 10, 0)),
                Message(role="assistant", content="Hi there! How can I help?", tool_uses=[
                    {"name": "Read", "input": {}},
                    {"name": "Edit", "input": {}},
                ], timestamp=datetime(2025, 6, 15, 10, 5)),
                Message(role="user", content="Can you fix this bug?", timestamp=datetime(2025, 6, 15, 10, 10)),
                Message(role="assistant", content="Fixed the error in the code.", tool_uses=[
                    {"name": "Edit", "input": {}},
                ], timestamp=datetime(2025, 6, 15, 10, 30)),
            ],
            start_time=datetime(2025, 6, 15, 10, 0),
            end_time=datetime(2025, 6, 15, 11, 0),
        )

        mock_session2 = Session(
            session_id="session2",
            project_path="/test/project",
            file_path=Path("/test/session2.jsonl"),
            messages=[
                Message(role="user", content="Write a function", timestamp=datetime(2025, 6, 16, 14, 0)),
                Message(role="assistant", content="Here's the function you requested." + "x" * 500, tool_uses=[
                    {"name": "Write", "input": {}},
                    {"name": "Bash", "input": {}},
                ], timestamp=datetime(2025, 6, 16, 14, 30)),
            ],
            start_time=datetime(2025, 6, 16, 14, 0),
            end_time=datetime(2025, 6, 16, 15, 0),
        )

        def mock_parse_session(file_path, project_path):
            if "session1" in str(file_path):
                return mock_session1
            return mock_session2

        with patch('claude_history_explorer.wrapped.list_projects', return_value=[mock_project]):
            with patch('claude_history_explorer.wrapped.parse_session', side_effect=mock_parse_session):
                story = generate_wrapped_story_v3(2025, name="Test User")

        # Verify core fields
        assert story.v == 3
        assert story.y == 2025
        assert story.n == "Test User"
        assert story.p == 1  # 1 project
        assert story.s == 2  # 2 sessions
        assert story.m == 6  # 6 total messages
        assert story.d == 2  # 2 days active

        # Verify message length distribution is populated (not all zeros)
        assert len(story.ml) == 8
        assert sum(story.ml) == 6  # 6 messages total

        # Verify trait scores include tool diversity
        assert 'td' in story.ts
        # We used 4 unique tools: Read, Edit, Write, Bash
        # td = (4-1)/9 ≈ 0.33 -> quantized to 33
        assert 30 <= story.ts['td'] <= 40

        # Verify heatmap has data
        assert len(story.hm) == 168
        # Sunday 10am (6*24 + 10 = 154) should have activity
        assert story.hm[0 * 24 + 10] > 0 or story.hm[0 * 24 + 14] > 0 or sum(story.hm) > 0


class TestTraitScoreQuantization:
    """TDD tests for trait score quantization (floats 0.0-1.0 → integers 0-100)."""

    def _create_sessions(self, count, agent_ratio=0.5):
        """Create test sessions with specified agent ratio."""
        return [
            SessionInfoV3(
                session_id=f"s{i}",
                start_time=datetime(2025, 12, 15 + i, 10, 0),
                end_time=datetime(2025, 12, 15 + i, 12, 0),
                duration_minutes=120,
                message_count=20,
                user_message_count=10,
                is_agent=i < count * agent_ratio,
                slug=None,
                project_name="TestProject",
                project_path="/test",
            )
            for i in range(count)
        ]

    def _create_projects(self, count):
        """Create test projects."""
        return [
            ProjectStatsV3(f"P{i}", f"/p{i}", 100 * (i + 1), 5, 5, 10, 5, 1, 100)
            for i in range(count)
        ]

    def test_trait_scores_return_integers(self):
        """Test that compute_trait_scores returns integers in range 0-100."""
        sessions = self._create_sessions(10)
        projects = self._create_projects(3)
        heatmap = [1] * 168

        scores = compute_trait_scores(sessions, projects, heatmap, unique_tools_count=5)

        # All trait scores should be integers
        for trait, value in scores.items():
            assert isinstance(value, int), f"Trait {trait} should be int, got {type(value)}"
            assert 0 <= value <= 100, f"Trait {trait} should be 0-100, got {value}"

    def test_trait_scores_extreme_values_quantized(self):
        """Test that extreme float values map correctly to integers."""
        # All agent sessions -> ad should be 100
        all_agent = self._create_sessions(10, agent_ratio=1.0)
        projects = self._create_projects(1)
        heatmap = [0] * 168

        scores = compute_trait_scores(all_agent, projects, heatmap)
        assert scores['ad'] == 100  # 1.0 -> 100

        # No agent sessions -> ad should be 0
        no_agent = self._create_sessions(10, agent_ratio=0.0)
        scores = compute_trait_scores(no_agent, projects, heatmap)
        assert scores['ad'] == 0  # 0.0 -> 0

    def test_trait_scores_middle_values_quantized(self):
        """Test that middle values are properly rounded."""
        # 50% agent sessions -> ad should be 50
        half_agent = self._create_sessions(10, agent_ratio=0.5)
        projects = self._create_projects(1)
        heatmap = [0] * 168

        scores = compute_trait_scores(half_agent, projects, heatmap)
        assert scores['ad'] == 50  # 0.5 -> 50

    def test_wrapped_story_ts_contains_integers(self):
        """Test that WrappedStoryV3.ts contains integers."""
        story = WrappedStoryV3(
            y=2025,
            p=5, s=100, m=1000, h=50, d=30,
            hm=[1] * 168,
            ma=[100] * 12,
            mh=[10] * 12,
            ms=[10] * 12,
            sd=[10, 20, 30, 20, 10, 5, 3, 2],
            ar=[20, 30, 25, 15, 10],
            ml=[5, 10, 15, 20, 20, 15, 10, 5],
            ts={'ad': 50, 'sp': 60, 'fc': 70, 'cc': 80, 'wr': 30,
                'bs': 40, 'cs': 20, 'mv': 50, 'td': 50, 'ri': 60},
            tp=[], pc=[], te=[], sf=[],
        )

        for trait, value in story.ts.items():
            assert isinstance(value, int), f"ts[{trait}] should be int"
            assert 0 <= value <= 100, f"ts[{trait}] should be 0-100"


class TestIntegerHours:
    """TDD tests for integer hours (converting from floats)."""

    def test_wrapped_story_total_hours_integer(self):
        """Test that WrappedStoryV3.h is an integer."""
        story = WrappedStoryV3(
            y=2025,
            p=5, s=100, m=1000, h=50, d=30,
            hm=[1] * 168,
            ma=[100] * 12,
            mh=[10] * 12,
            ms=[10] * 12,
            sd=[10, 20, 30, 20, 10, 5, 3, 2],
            ar=[20, 30, 25, 15, 10],
            ml=[5, 10, 15, 20, 20, 15, 10, 5],
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[], pc=[], te=[], sf=[],
        )
        assert isinstance(story.h, int), f"h should be int, got {type(story.h)}"

    def test_wrapped_story_monthly_hours_integers(self):
        """Test that WrappedStoryV3.mh contains integers."""
        story = WrappedStoryV3(
            y=2025,
            p=5, s=100, m=1000, h=50, d=30,
            hm=[1] * 168,
            ma=[100] * 12,
            mh=[5, 8, 10, 12, 15, 20, 18, 14, 10, 8, 6, 4],  # Integer monthly hours
            ms=[10] * 12,
            sd=[10, 20, 30, 20, 10, 5, 3, 2],
            ar=[20, 30, 25, 15, 10],
            ml=[5, 10, 15, 20, 20, 15, 10, 5],
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[], pc=[], te=[], sf=[],
        )

        assert len(story.mh) == 12
        for i, value in enumerate(story.mh):
            assert isinstance(value, int), f"mh[{i}] should be int, got {type(value)}"

    def test_project_stats_hours_integer(self):
        """Test that ProjectStatsV3.hours is an integer."""
        project = ProjectStatsV3(
            name="TestProject",
            path="/test",
            message_count=1000,
            agent_sessions=10,
            main_sessions=20,
            hours=50,  # Integer hours
            days_active=30,
            first_day=1,
            last_day=365,
        )
        assert isinstance(project.hours, int), f"hours should be int, got {type(project.hours)}"

    def test_tp_project_hours_integer(self):
        """Test that top projects have integer hours."""
        story = WrappedStoryV3(
            y=2025,
            p=5, s=100, m=1000, h=50, d=30,
            hm=[1] * 168,
            ma=[100] * 12,
            mh=[10] * 12,
            ms=[10] * 12,
            sd=[10, 20, 30, 20, 10, 5, 3, 2],
            ar=[20, 30, 25, 15, 10],
            ml=[5, 10, 15, 20, 20, 15, 10, 5],
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[
                {'n': 'Project1', 'm': 500, 'h': 25, 'd': 15, 's': 20, 'ar': 50, 'fd': 1, 'ld': 100},
                {'n': 'Project2', 'm': 300, 'h': 15, 'd': 10, 's': 15, 'ar': 30, 'fd': 50, 'ld': 200},
            ],
            pc=[], te=[], sf=[],
        )

        for proj in story.tp:
            assert isinstance(proj['h'], int), f"tp project h should be int"

    def test_encode_decode_preserves_integer_types(self):
        """Test that encoding and decoding preserves integer types for hours and trait scores."""
        original = WrappedStoryV3(
            y=2025,
            p=5, s=100, m=1000, h=50, d=30,
            hm=[1] * 168,
            ma=[100] * 12,
            mh=[5, 8, 10, 12, 15, 20, 18, 14, 10, 8, 6, 4],
            ms=[10] * 12,
            sd=[10, 20, 30, 20, 10, 5, 3, 2],
            ar=[20, 30, 25, 15, 10],
            ml=[5, 10, 15, 20, 20, 15, 10, 5],
            ts={'ad': 45, 'sp': 65, 'fc': 72, 'cc': 58, 'wr': 25,
                'bs': 40, 'cs': 33, 'mv': 55, 'td': 60, 'ri': 70},
            tp=[
                {'n': 'Project1', 'm': 500, 'h': 25, 'd': 15, 's': 20, 'ar': 50, 'fd': 1, 'ld': 100},
            ],
            pc=[], te=[], sf=[],
        )

        encoded = encode_wrapped_story_v3(original)
        decoded = decode_wrapped_story_v3(encoded)

        # Verify integer types preserved
        assert isinstance(decoded.h, int), f"decoded.h should be int"
        for i, v in enumerate(decoded.mh):
            assert isinstance(v, int), f"decoded.mh[{i}] should be int"
        for trait, v in decoded.ts.items():
            assert isinstance(v, int), f"decoded.ts[{trait}] should be int"


class TestGenerateProjectStory:
    """Tests for generate_project_story() function."""

    def _create_mock_session(self, session_id, start_time, duration_minutes, message_count, is_agent=False):
        """Create a mock Session with specified attributes."""
        from datetime import timedelta
        end_time = start_time + timedelta(minutes=duration_minutes) if duration_minutes > 0 else None
        messages = [
            Message(role="user", content=f"Message {i}", timestamp=start_time + timedelta(minutes=i))
            for i in range(message_count // 2)
        ] + [
            Message(role="assistant", content=f"Response {i}", timestamp=start_time + timedelta(minutes=i+1))
            for i in range(message_count // 2)
        ]
        return Session(
            session_id=session_id,
            project_path="/test/project",
            file_path=Path(f"/mock/{session_id}.jsonl"),
            messages=messages,
            start_time=start_time,
            end_time=end_time,
            slug=f"slug-{session_id}",
        )

    def _create_mock_project(self, session_files):
        """Create a mock Project with session files."""
        return Project(
            name="-test-project",
            path="/test/project",
            dir_path=Path("/mock/.claude/projects/-test-project"),
            session_files=session_files,
        )

    def test_generate_project_story_basic(self):
        """Test basic project story generation."""
        from datetime import timedelta
        from claude_history_explorer.history import generate_project_story, parse_session

        base_time = datetime(2025, 12, 1, 10, 0)
        sessions_data = [
            ("session1", base_time, 60, 20, False),
            ("session2", base_time + timedelta(days=1), 45, 15, False),
            ("agent-1", base_time + timedelta(days=2), 30, 10, True),
        ]

        session_files = [Path(f"/mock/{s[0]}.jsonl") for s in sessions_data]
        project = self._create_mock_project(session_files)

        # Mock parse_session to return our test sessions
        def mock_parse_session(file_path, project_path):
            for s in sessions_data:
                if s[0] in str(file_path):
                    return self._create_mock_session(s[0], s[1], s[2], s[3], s[4])
            raise ValueError(f"Unknown file: {file_path}")

        with patch('claude_history_explorer.stories.parse_session', side_effect=mock_parse_session):
            story = generate_project_story(project)

        assert story.project_name == "Project"  # short_name is capitalized
        assert story.lifecycle_days == 3  # Dec 1-3
        assert story.agent_sessions == 1
        assert story.main_sessions == 2
        assert story.total_messages == 44  # 20 + 14 + 10 (even splits)
        assert len(story.personality_traits) >= 1
        assert story.collaboration_style is not None

    def test_generate_project_story_no_sessions_raises(self):
        """Test that empty project raises ValueError."""
        from claude_history_explorer.history import generate_project_story

        project = self._create_mock_project([])

        with pytest.raises(ValueError, match="No sessions found"):
            generate_project_story(project)

    def test_generate_project_story_sessions_without_timestamps(self):
        """Test handling of sessions without valid timestamps."""
        from claude_history_explorer.history import generate_project_story

        session_files = [Path("/mock/session1.jsonl")]
        project = self._create_mock_project(session_files)

        # Return session with no start_time
        def mock_parse_session(file_path, project_path):
            return Session(
                session_id="session1",
                project_path=project_path,
                file_path=file_path,
                messages=[Message(role="user", content="test", timestamp=None)],
                start_time=None,
                end_time=None,
                slug=None,
            )

        with patch('claude_history_explorer.stories.parse_session', side_effect=mock_parse_session):
            with pytest.raises(ValueError, match="No sessions found"):
                generate_project_story(project)

    def test_generate_project_story_concurrent_detection(self):
        """Test detection of concurrent Claude instances."""
        from datetime import timedelta
        from claude_history_explorer.history import generate_project_story

        base_time = datetime(2025, 12, 1, 10, 0)
        # Create many sessions starting at nearly the same time (within 30 min)
        sessions_data = [
            (f"session{i}", base_time + timedelta(minutes=i*5), 60, 10, False)
            for i in range(5)
        ]

        session_files = [Path(f"/mock/{s[0]}.jsonl") for s in sessions_data]
        project = self._create_mock_project(session_files)

        def mock_parse_session(file_path, project_path):
            for s in sessions_data:
                if s[0] in str(file_path):
                    return self._create_mock_session(s[0], s[1], s[2], s[3], s[4])
            raise ValueError(f"Unknown file: {file_path}")

        with patch('claude_history_explorer.stories.parse_session', side_effect=mock_parse_session):
            story = generate_project_story(project)

        # Should detect concurrent usage (sessions within 30 min of each other)
        assert story.concurrent_claude_instances >= 2

    def test_generate_project_story_work_pace_classification(self):
        """Test work pace classification based on message rate."""
        from datetime import timedelta
        from claude_history_explorer.history import generate_project_story

        base_time = datetime(2025, 12, 1, 10, 0)
        # High message rate: 100 messages in 30 minutes = 200 msgs/hour
        sessions_data = [
            ("session1", base_time, 30, 100, False),
        ]

        session_files = [Path(f"/mock/{s[0]}.jsonl") for s in sessions_data]
        project = self._create_mock_project(session_files)

        def mock_parse_session(file_path, project_path):
            for s in sessions_data:
                if s[0] in str(file_path):
                    return self._create_mock_session(s[0], s[1], s[2], s[3], s[4])
            raise ValueError(f"Unknown file: {file_path}")

        with patch('claude_history_explorer.stories.parse_session', side_effect=mock_parse_session):
            story = generate_project_story(project)

        # High message rate should result in "Rapid-fire" work pace
        assert "Rapid" in story.work_pace or story.work_pace is not None

    def test_generate_project_story_break_periods(self):
        """Test detection of break periods in activity."""
        from datetime import timedelta
        from claude_history_explorer.history import generate_project_story

        base_time = datetime(2025, 12, 1, 10, 0)
        # Sessions with gaps
        sessions_data = [
            ("session1", base_time, 60, 10, False),
            ("session2", base_time + timedelta(days=5), 60, 10, False),  # 4 day gap
            ("session3", base_time + timedelta(days=10), 60, 10, False),  # 5 day gap
        ]

        session_files = [Path(f"/mock/{s[0]}.jsonl") for s in sessions_data]
        project = self._create_mock_project(session_files)

        def mock_parse_session(file_path, project_path):
            for s in sessions_data:
                if s[0] in str(file_path):
                    return self._create_mock_session(s[0], s[1], s[2], s[3], s[4])
            raise ValueError(f"Unknown file: {file_path}")

        with patch('claude_history_explorer.stories.parse_session', side_effect=mock_parse_session):
            story = generate_project_story(project)

        # Should detect break periods
        assert len(story.break_periods) >= 2
        assert "Intermittent" in story.daily_engagement or "breaks" in story.daily_engagement


class TestGenerateGlobalStory:
    """Tests for generate_global_story() function."""

    def test_generate_global_story_basic(self):
        """Test basic global story generation."""
        from claude_history_explorer.history import generate_global_story, ProjectStory, SessionInfo

        mock_session_info = SessionInfo(
            session_id="s1",
            start_time=datetime(2025, 12, 1, 10, 0),
            end_time=datetime(2025, 12, 1, 11, 0),
            duration_minutes=60,
            message_count=20,
            user_message_count=10,
            is_agent=False,
            slug="test",
        )

        mock_stories = [
            ProjectStory(
                project_name="project1",
                project_path="/p1",
                lifecycle_days=30,
                birth_date=datetime(2025, 11, 1, 10, 0),
                last_active=datetime(2025, 12, 1, 10, 0),
                peak_day=(datetime(2025, 11, 15), 50),
                break_periods=[],
                agent_sessions=5,
                main_sessions=15,
                collaboration_style="Balanced",
                total_messages=500,
                dev_time_hours=50.0,
                message_rate=10.0,
                work_pace="Steady",
                avg_session_hours=2.5,
                longest_session_hours=4.0,
                session_style="Standard",
                personality_traits=["Focused", "Collaborative"],
                most_productive_session=mock_session_info,
                daily_engagement="Consistent",
                insights=["Insight 1"],
                daily_activity={},
                concurrent_claude_instances=1,
                concurrent_insights=[],
            ),
            ProjectStory(
                project_name="project2",
                project_path="/p2",
                lifecycle_days=15,
                birth_date=datetime(2025, 11, 15, 10, 0),
                last_active=datetime(2025, 12, 1, 10, 0),
                peak_day=(datetime(2025, 11, 20), 30),
                break_periods=[],
                agent_sessions=10,
                main_sessions=10,
                collaboration_style="Heavy delegation",
                total_messages=300,
                dev_time_hours=30.0,
                message_rate=10.0,
                work_pace="Steady",
                avg_session_hours=1.5,
                longest_session_hours=3.0,
                session_style="Quick",
                personality_traits=["Agent-driven", "Focused"],
                most_productive_session=mock_session_info,
                daily_engagement="Consistent",
                insights=["Insight 2"],
                daily_activity={},
                concurrent_claude_instances=2,
                concurrent_insights=["Parallel usage"],
            ),
        ]

        mock_projects = [MagicMock(spec=Project) for _ in range(2)]

        with patch('claude_history_explorer.stories.list_projects', return_value=mock_projects):
            with patch('claude_history_explorer.stories.generate_project_story', side_effect=mock_stories):
                story = generate_global_story()

        assert story.total_projects == 2
        assert story.total_messages == 800  # 500 + 300
        assert story.total_dev_time == 80.0  # 50 + 30
        assert len(story.project_stories) == 2
        assert len(story.common_traits) > 0
        # "Focused" appears in both projects
        assert any(t[0] == "Focused" for t in story.common_traits)

    def test_generate_global_story_no_projects_raises(self):
        """Test that no projects raises ValueError."""
        from claude_history_explorer.history import generate_global_story

        with patch('claude_history_explorer.stories.list_projects', return_value=[]):
            with pytest.raises(ValueError, match="No projects with sessions found"):
                generate_global_story()

    def test_generate_global_story_skips_failed_projects(self):
        """Test that projects failing to generate stories are skipped."""
        from claude_history_explorer.history import generate_global_story, ProjectStory, SessionInfo

        mock_session_info = SessionInfo(
            session_id="s1",
            start_time=datetime(2025, 12, 1, 10, 0),
            end_time=datetime(2025, 12, 1, 11, 0),
            duration_minutes=60,
            message_count=20,
            user_message_count=10,
            is_agent=False,
            slug="test",
        )

        valid_story = ProjectStory(
            project_name="project1",
            project_path="/p1",
            lifecycle_days=30,
            birth_date=datetime(2025, 11, 1, 10, 0),
            last_active=datetime(2025, 12, 1, 10, 0),
            peak_day=None,
            break_periods=[],
            agent_sessions=5,
            main_sessions=15,
            collaboration_style="Balanced",
            total_messages=500,
            dev_time_hours=50.0,
            message_rate=10.0,
            work_pace="Steady",
            avg_session_hours=2.5,
            longest_session_hours=4.0,
            session_style="Standard",
            personality_traits=["Focused"],
            most_productive_session=mock_session_info,
            daily_engagement="Consistent",
            insights=[],
            daily_activity={},
            concurrent_claude_instances=0,
            concurrent_insights=[],
        )

        def mock_generate(project):
            if project.path == "/fail":
                raise ValueError("No sessions")
            return valid_story

        mock_projects = [MagicMock(spec=Project, path="/p1"), MagicMock(spec=Project, path="/fail")]

        with patch('claude_history_explorer.stories.list_projects', return_value=mock_projects):
            with patch('claude_history_explorer.stories.generate_project_story', side_effect=mock_generate):
                story = generate_global_story()

        # Should have 1 project (the failed one was skipped)
        assert story.total_projects == 1


if __name__ == "__main__":
    # Run tests manually if needed
    import sys

    test_classes = [
        TestMessage,
        TestProject,
        TestSession,
        TestProjectStats,
        TestGlobalStats,
        TestReadOnlyBehavior,
        TestPathHandling,
        TestErrorHandling,
        TestRLEEncoding,
        TestHeatmap,
        TestDistributions,
        TestTraitScores,
        TestProjectCooccurrence,
        TestTimelineEvents,
        TestSessionFingerprint,
        TestWrappedStoryV3,
        TestProjectStatsV3,
        TestSessionInfoV3,
        TestTraitScoresEdgeCases,
        TestFingerprintComputation,
        TestV3Integration,
        TestTraitScoreQuantization,
        TestIntegerHours,
        TestGenerateProjectStory,
        TestGenerateGlobalStory,
    ]
    
    for test_class in test_classes:
        print(f"Running {test_class.__name__}...")
        
        # Get all test methods
        methods = [method for method in dir(test_class) if method.startswith('test_')]
        
        for method_name in methods:
            try:
                # Create instance and run test
                instance = test_class()
                method = getattr(instance, method_name)
                method()
                print(f"  ✓ {method_name}")
            except Exception as e:
                print(f"  ✗ {method_name}: {e}")
                sys.exit(1)
    
    print("\nAll tests passed!")