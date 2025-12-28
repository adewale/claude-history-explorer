"""Unit tests for split modules.

These tests verify that each module functions correctly in isolation
and that imports work as expected after the module split.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestModuleImports:
    """Test that all modules can be imported correctly."""

    def test_import_models(self):
        """Test importing from models module."""
        from claude_history_explorer.models import (
            GlobalStats,
            GlobalStory,
            Message,
            Project,
            ProjectStats,
            ProjectStatsV3,
            ProjectStory,
            Session,
            SessionInfo,
            SessionInfoV3,
            TokenUsage,
            WrappedStoryV3,
        )

        # Verify classes are importable
        assert Message is not None
        assert Session is not None
        assert Project is not None

    def test_import_utils(self):
        """Test importing from utils module."""
        from claude_history_explorer.utils import (
            _active_duration_minutes,
            _compile_regex_safe,
            classify,
            format_duration,
            format_timestamp,
        )

        assert format_duration is not None
        assert classify is not None

    def test_import_projects(self):
        """Test importing from projects module."""
        from claude_history_explorer.projects import (
            find_project,
            get_claude_dir,
            get_projects_dir,
            list_projects,
        )

        assert list_projects is not None
        assert find_project is not None

    def test_import_parser(self):
        """Test importing from parser module."""
        from claude_history_explorer.parser import (
            get_session_by_id,
            parse_session,
            search_sessions,
        )

        assert parse_session is not None
        assert search_sessions is not None

    def test_import_stats(self):
        """Test importing from stats module."""
        from claude_history_explorer.stats import (
            calculate_global_stats,
            calculate_project_stats,
        )

        assert calculate_project_stats is not None
        assert calculate_global_stats is not None

    def test_import_stories(self):
        """Test importing from stories module."""
        from claude_history_explorer.stories import (
            generate_global_story,
            generate_project_story,
        )

        assert generate_project_story is not None
        assert generate_global_story is not None

    def test_import_wrapped(self):
        """Test importing from wrapped module."""
        from claude_history_explorer.wrapped import (
            compute_activity_heatmap,
            decode_wrapped_story_v3,
            encode_wrapped_story_v3,
            generate_wrapped_story_v3,
        )

        assert compute_activity_heatmap is not None
        assert encode_wrapped_story_v3 is not None

    def test_backward_compat_import_from_history(self):
        """Test that imports from history still work."""
        from claude_history_explorer.history import (
            GlobalStats,
            Message,
            Project,
            Session,
            calculate_global_stats,
            calculate_project_stats,
            find_project,
            generate_project_story,
            list_projects,
            parse_session,
            search_sessions,
        )

        assert Message is not None
        assert list_projects is not None
        assert parse_session is not None


class TestUtils:
    """Test utility functions."""

    def test_format_duration_minutes(self):
        """Test formatting durations in minutes."""
        from claude_history_explorer.utils import format_duration

        assert format_duration(0) == "0m"
        assert format_duration(30) == "30m"
        assert format_duration(59) == "59m"

    def test_format_duration_hours(self):
        """Test formatting durations with hours."""
        from claude_history_explorer.utils import format_duration

        assert format_duration(60) == "1h 0m"
        assert format_duration(90) == "1h 30m"
        assert format_duration(120) == "2h 0m"
        assert format_duration(150) == "2h 30m"

    def test_format_timestamp_with_datetime(self):
        """Test formatting a valid datetime."""
        from claude_history_explorer.utils import format_timestamp

        dt = datetime(2025, 12, 15, 14, 30)
        assert format_timestamp(dt) == "2025-12-15 14:30"

    def test_format_timestamp_with_none(self):
        """Test formatting None returns unknown."""
        from claude_history_explorer.utils import format_timestamp

        assert format_timestamp(None) == "unknown"

    def test_format_timestamp_custom_format(self):
        """Test formatting with custom format."""
        from claude_history_explorer.utils import format_timestamp

        dt = datetime(2025, 12, 15, 14, 30, 45)
        assert format_timestamp(dt, "%Y-%m-%d") == "2025-12-15"

    def test_classify_high(self):
        """Test classification with high value."""
        from claude_history_explorer.utils import classify

        thresholds = [(30, "high"), (20, "medium"), (10, "low")]
        assert classify(35, thresholds, "minimal") == "high"

    def test_classify_medium(self):
        """Test classification with medium value."""
        from claude_history_explorer.utils import classify

        thresholds = [(30, "high"), (20, "medium"), (10, "low")]
        assert classify(25, thresholds, "minimal") == "medium"

    def test_classify_low(self):
        """Test classification with low value."""
        from claude_history_explorer.utils import classify

        thresholds = [(30, "high"), (20, "medium"), (10, "low")]
        assert classify(15, thresholds, "minimal") == "low"

    def test_classify_default(self):
        """Test classification falls to default."""
        from claude_history_explorer.utils import classify

        thresholds = [(30, "high"), (20, "medium"), (10, "low")]
        assert classify(5, thresholds, "minimal") == "minimal"

    def test_compile_regex_safe_valid_pattern(self):
        """Test compiling a safe regex pattern."""
        from claude_history_explorer.utils import _compile_regex_safe

        pattern = _compile_regex_safe(r"test\s+\w+")
        assert pattern.search("test hello")

    def test_compile_regex_safe_redos_pattern_raises(self):
        """Test that ReDoS-vulnerable patterns raise ValueError."""
        from claude_history_explorer.utils import _compile_regex_safe

        with pytest.raises(ValueError, match="nested quantifiers"):
            _compile_regex_safe(r"(a+)+b")

    def test_active_duration_minutes_empty(self):
        """Test active duration with no messages."""
        from claude_history_explorer.models import Message
        from claude_history_explorer.utils import _active_duration_minutes

        assert _active_duration_minutes([]) == 0

    def test_active_duration_minutes_single_message(self):
        """Test active duration with single message."""
        from claude_history_explorer.models import Message
        from claude_history_explorer.utils import _active_duration_minutes

        msgs = [Message(role="user", content="test", timestamp=datetime.now())]
        assert _active_duration_minutes(msgs) == 0


class TestProjects:
    """Test project discovery functions."""

    def test_get_claude_dir(self):
        """Test getting Claude directory path."""
        from claude_history_explorer.projects import get_claude_dir

        path = get_claude_dir()
        assert path.name == ".claude"

    def test_get_projects_dir(self):
        """Test getting projects directory path."""
        from claude_history_explorer.projects import get_projects_dir

        path = get_projects_dir()
        assert path.name == "projects"
        assert path.parent.name == ".claude"

    def test_list_projects_empty_dir(self):
        """Test listing projects from empty directory."""
        from claude_history_explorer.projects import list_projects

        with patch(
            "claude_history_explorer.projects.get_projects_dir",
            return_value=Path("/nonexistent"),
        ):
            projects = list_projects()
            assert projects == []

    def test_find_project_not_found(self):
        """Test finding a project that doesn't exist."""
        from claude_history_explorer.projects import find_project

        with patch("claude_history_explorer.projects.list_projects", return_value=[]):
            result = find_project("nonexistent")
            assert result is None


class TestParser:
    """Test JSONL parsing functions."""

    def test_parse_session_empty_file(self):
        """Test parsing an empty session file."""
        from claude_history_explorer.parser import parse_session

        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", mode="w", delete=False
        ) as f:
            f.write("")
            f.flush()
            session = parse_session(Path(f.name), "/test")
            assert session.message_count == 0

    def test_parse_session_with_messages(self):
        """Test parsing a session with messages."""
        from claude_history_explorer.parser import parse_session

        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", mode="w", delete=False
        ) as f:
            f.write('{"type": "user", "message": {"content": "hello"}}\n')
            f.write('{"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}\n')
            f.flush()
            session = parse_session(Path(f.name), "/test")
            assert session.message_count == 2

    def test_parse_session_extracts_slug(self):
        """Test that session slug is extracted."""
        from claude_history_explorer.parser import parse_session

        with tempfile.NamedTemporaryFile(
            suffix=".jsonl", mode="w", delete=False
        ) as f:
            f.write('{"slug": "test-session"}\n')
            f.write('{"type": "user", "message": {"content": "hello"}}\n')
            f.flush()
            session = parse_session(Path(f.name), "/test")
            assert session.slug == "test-session"

    def test_search_sessions_with_pattern(self):
        """Test searching sessions with a pattern."""
        from claude_history_explorer.parser import search_sessions
        from claude_history_explorer.models import Project

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            project_dir = temp_path / "-test-project"
            project_dir.mkdir()

            session_file = project_dir / "session1.jsonl"
            session_file.write_text(
                '{"type": "user", "message": {"content": "find this NEEDLE here"}}\n'
            )

            mock_project = Project.from_dir(project_dir)
            with patch(
                "claude_history_explorer.parser.list_projects",
                return_value=[mock_project],
            ):
                results = list(search_sessions("NEEDLE"))
                assert len(results) == 1
                session, matches = results[0]
                assert len(matches) == 1


class TestModels:
    """Test data model classes."""

    def test_message_from_json_user(self):
        """Test creating Message from user JSON."""
        from claude_history_explorer.models import Message

        data = {
            "type": "user",
            "message": {"content": "hello"},
            "timestamp": "2025-12-15T10:00:00Z",
        }
        msg = Message.from_json(data)
        assert msg is not None
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_message_from_json_assistant(self):
        """Test creating Message from assistant JSON."""
        from claude_history_explorer.models import Message

        data = {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "response"}]},
        }
        msg = Message.from_json(data)
        assert msg is not None
        assert msg.role == "assistant"
        assert msg.content == "response"

    def test_message_from_json_with_tool_use(self):
        """Test creating Message with tool usage."""
        from claude_history_explorer.models import Message

        data = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Using tool"},
                    {"type": "tool_use", "name": "Read", "input": {"path": "/test"}},
                ]
            },
        }
        msg = Message.from_json(data)
        assert msg is not None
        assert len(msg.tool_uses) == 1
        assert msg.tool_uses[0]["name"] == "Read"

    def test_session_properties(self):
        """Test Session computed properties."""
        from claude_history_explorer.models import Message, Session

        msgs = [
            Message(role="user", content="hello", timestamp=datetime(2025, 12, 15, 10, 0)),
            Message(role="assistant", content="hi", timestamp=datetime(2025, 12, 15, 10, 5)),
        ]
        session = Session(
            session_id="test",
            project_path="/test",
            file_path=Path("/test.jsonl"),
            messages=msgs,
            start_time=datetime(2025, 12, 15, 10, 0),
            end_time=datetime(2025, 12, 15, 10, 5),
        )

        assert session.message_count == 2
        assert session.user_message_count == 1
        assert session.active_duration_minutes == 5

    def test_project_short_name(self):
        """Test Project short_name property."""
        from claude_history_explorer.models import Project

        project = Project(
            name="-Users-test-my_project",
            path="/Users/test/my_project",
            dir_path=Path("/claude/projects/-Users-test-my_project"),
            session_files=[],
        )
        assert project.short_name == "My Project"

    def test_token_usage_total(self):
        """Test TokenUsage total property."""
        from claude_history_explorer.models import TokenUsage

        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150


class TestStats:
    """Test statistics functions."""

    def test_calculate_project_stats(self):
        """Test calculating project stats."""
        from claude_history_explorer.models import Project
        from claude_history_explorer.stats import calculate_project_stats

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            project_dir = temp_path / "-test"
            project_dir.mkdir()

            session_file = project_dir / "session1.jsonl"
            session_file.write_text(
                '{"type": "user", "message": {"content": "test"}}\n'
            )

            project = Project.from_dir(project_dir)
            stats = calculate_project_stats(project)

            assert stats.total_sessions == 1
            assert stats.total_messages >= 1
            assert stats.total_size_bytes > 0


class TestWrapped:
    """Test wrapped format functions."""

    def test_rle_encode_decode(self):
        """Test RLE encoding and decoding."""
        from claude_history_explorer.wrapped import rle_decode, rle_encode

        original = [0, 0, 0, 5, 5, 0, 0, 0, 0]
        encoded = rle_encode(original)
        decoded = rle_decode(encoded)
        assert decoded == original

    def test_rle_encode_if_smaller(self):
        """Test RLE encode only when beneficial."""
        from claude_history_explorer.wrapped import rle_encode_if_smaller

        # Many repeated values - RLE should be smaller
        many_repeats = [0] * 100
        is_rle, data = rle_encode_if_smaller(many_repeats)
        assert is_rle is True
        assert len(data) < len(many_repeats)

        # Unique values - RLE won't help
        unique = list(range(10))
        is_rle, data = rle_encode_if_smaller(unique)
        assert is_rle is False
        assert data == unique

    def test_quantize_heatmap(self):
        """Test heatmap quantization."""
        from claude_history_explorer.wrapped import quantize_heatmap

        heatmap = [0, 50, 100]
        quantized = quantize_heatmap(heatmap, scale=10)
        assert quantized == [0, 5, 10]

    def test_compute_distribution(self):
        """Test distribution bucketing."""
        from claude_history_explorer.wrapped import compute_distribution

        values = [5, 15, 25, 35]
        buckets = [10, 20, 30]
        dist = compute_distribution(values, buckets)
        # Buckets: <10, 10-20, 20-30, >=30
        assert dist == [1, 1, 1, 1]

    def test_compute_streak_stats_empty(self):
        """Test streak stats with no dates."""
        from claude_history_explorer.wrapped import compute_streak_stats

        result = compute_streak_stats(set(), 2025)
        assert result == [0, 0, 0, 0]

    def test_encode_decode_wrapped_story_v3(self):
        """Test encoding and decoding WrappedStoryV3."""
        from claude_history_explorer.wrapped import (
            decode_wrapped_story_v3,
            encode_wrapped_story_v3,
        )
        from claude_history_explorer.models import WrappedStoryV3

        story = WrappedStoryV3(y=2025, p=5, s=10, m=100, h=50, d=30)
        encoded = encode_wrapped_story_v3(story)
        decoded = decode_wrapped_story_v3(encoded)

        assert decoded.y == 2025
        assert decoded.p == 5
        assert decoded.s == 10
        assert decoded.m == 100
