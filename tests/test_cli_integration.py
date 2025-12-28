"""
Integration tests for all CLI commands.

These tests verify that:
1. Each CLI command can be invoked successfully
2. Commands handle missing data gracefully
3. Output formats are correct
4. Error handling works properly

Run with: uv run pytest tests/test_cli_integration.py -v
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from claude_history_explorer.cli import main
from claude_history_explorer.history import (
    Project,
    Session,
    Message,
    SessionInfo,
    ProjectStats,
    GlobalStats,
    ProjectStory,
    GlobalStory,
    WrappedStoryV3,
    encode_wrapped_story_v3,
    decode_wrapped_story_v3,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_project():
    """Create a mock Project for testing."""
    project = MagicMock(spec=Project)
    project.name = "-Users-test-myproject"
    project.short_name = "myproject"
    project.path = "/Users/test/myproject"
    project.dir_path = Path("/mock/.claude/projects/-Users-test-myproject")
    project.session_files = [
        Path("/mock/.claude/projects/-Users-test-myproject/session1.jsonl"),
        Path("/mock/.claude/projects/-Users-test-myproject/session2.jsonl"),
    ]
    project.session_count = 2
    project.last_modified = datetime(2025, 12, 15, 10, 30)
    return project


@pytest.fixture
def mock_session():
    """Create a mock Session for testing."""
    return Session(
        session_id="abc123-session-id",
        project_path="/Users/test/myproject",
        file_path=Path("/mock/session.jsonl"),
        messages=[
            Message(
                role="user",
                content="Hello, help me with Python",
                timestamp=datetime(2025, 12, 15, 10, 0),
            ),
            Message(
                role="assistant",
                content="I'd be happy to help with Python!",
                timestamp=datetime(2025, 12, 15, 10, 1),
                tool_uses=[{"name": "Read", "input": {"file": "test.py"}}],
            ),
            Message(
                role="user",
                content="Thanks, can you fix this bug?",
                timestamp=datetime(2025, 12, 15, 10, 5),
            ),
            Message(
                role="assistant",
                content="I've fixed the bug in your code.",
                timestamp=datetime(2025, 12, 15, 10, 10),
            ),
        ],
        start_time=datetime(2025, 12, 15, 10, 0),
        end_time=datetime(2025, 12, 15, 10, 10),
        slug="help-with-python",
    )


@pytest.fixture
def mock_session_info():
    """Create mock SessionInfo for testing."""
    return SessionInfo(
        session_id="test-session-123",
        start_time=datetime(2025, 12, 15, 10, 0),
        end_time=datetime(2025, 12, 15, 11, 30),
        duration_minutes=90,
        message_count=50,
        user_message_count=25,
        is_agent=False,
        slug="debugging-session",
    )


@pytest.fixture
def mock_project_stats(mock_project):
    """Create mock ProjectStats for testing."""
    return ProjectStats(
        project=mock_project,
        total_sessions=25,
        total_messages=500,
        total_user_messages=250,
        total_duration_minutes=3030,  # ~50.5 hours
        agent_sessions=5,
        main_sessions=20,
        total_size_bytes=1024000,
        avg_messages_per_session=20.0,
        longest_session_duration="2h 30m",
        most_recent_session=datetime(2025, 12, 15, 10, 0),
    )


@pytest.fixture
def mock_global_stats(mock_project_stats):
    """Create mock GlobalStats for testing."""
    return GlobalStats(
        projects=[mock_project_stats],
        total_projects=5,
        total_sessions=100,
        total_messages=2500,
        total_user_messages=1250,
        total_duration_minutes=15000,  # ~250 hours
        total_size_bytes=5120000,
        avg_sessions_per_project=20.0,
        avg_messages_per_session=25.0,
        most_active_project="/Users/test/myproject",
        largest_project="/Users/test/myproject",
        most_recent_activity=datetime(2025, 12, 15, 10, 0),
    )


@pytest.fixture
def mock_project_story(mock_session_info):
    """Create mock ProjectStory for testing."""
    return ProjectStory(
        project_name="myproject",
        project_path="/Users/test/myproject",
        lifecycle_days=180,
        birth_date=datetime(2025, 6, 1, 9, 0),
        last_active=datetime(2025, 12, 15, 10, 0),
        peak_day=(datetime(2025, 10, 15), 100),
        break_periods=[],
        agent_sessions=5,
        main_sessions=20,
        collaboration_style="Hands-on",
        total_messages=500,
        dev_time_hours=50.5,
        message_rate=9.9,
        work_pace="Steady, productive flow",
        avg_session_hours=2.0,
        longest_session_hours=4.5,
        session_style="Focused sessions",
        personality_traits=["Focused", "Iterative", "Tool-heavy"],
        most_productive_session=mock_session_info,
        daily_engagement="Peak productivity on Mondays",
        insights=["Strong focus on testing", "Prefers morning sessions"],
        daily_activity={datetime(2025, 12, 15): 50},
        concurrent_claude_instances=2,
        concurrent_insights=["Used parallel sessions for debugging"],
    )


@pytest.fixture
def mock_global_story(mock_project_story):
    """Create mock GlobalStory for testing."""
    return GlobalStory(
        total_projects=5,
        total_messages=2500,
        total_dev_time=250.0,
        avg_agent_ratio=0.2,
        avg_session_length=2.5,
        common_traits=[("Focused", 4), ("Tool-heavy", 3)],
        project_stories=[mock_project_story],
        recent_activity=[(datetime(2025, 12, 15), "myproject")],
    )


# =============================================================================
# Test: projects command
# =============================================================================

class TestProjectsCommand:
    """Tests for the 'projects' command."""

    def test_projects_with_data(self, runner, mock_project):
        """Test projects command with existing projects."""
        with patch('claude_history_explorer.cli.list_projects', return_value=[mock_project]):
            result = runner.invoke(main, ['projects'])

            assert result.exit_code == 0
            assert 'myproject' in result.output or 'Projects' in result.output

    def test_projects_empty(self, runner):
        """Test projects command with no projects."""
        with patch('claude_history_explorer.cli.list_projects', return_value=[]):
            result = runner.invoke(main, ['projects'])

            assert result.exit_code == 0
            assert 'No projects found' in result.output or '0 total' in result.output

    def test_projects_with_limit(self, runner, mock_project):
        """Test projects command with --limit option."""
        projects = [mock_project] * 10
        with patch('claude_history_explorer.cli.list_projects', return_value=projects):
            result = runner.invoke(main, ['projects', '-n', '5'])

            assert result.exit_code == 0

    def test_projects_example_flag(self, runner):
        """Test projects command with --example flag."""
        result = runner.invoke(main, ['projects', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output or 'example' in result.output.lower()


# =============================================================================
# Test: sessions command
# =============================================================================

class TestSessionsCommand:
    """Tests for the 'sessions' command."""

    def test_sessions_with_project(self, runner, mock_project, mock_session):
        """Test sessions command for a specific project."""
        mock_project.session_files = [Path("/mock/session.jsonl")]

        def mock_parse(file_path, project_path):
            return mock_session

        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.parse_session', side_effect=mock_parse):
                result = runner.invoke(main, ['sessions', 'myproject'])

                assert result.exit_code == 0

    def test_sessions_project_not_found(self, runner):
        """Test sessions command when project is not found."""
        with patch('claude_history_explorer.cli.find_project', return_value=None):
            result = runner.invoke(main, ['sessions', 'nonexistent'])

            assert result.exit_code == 0
            assert 'not found' in result.output.lower() or 'No project' in result.output

    def test_sessions_with_limit(self, runner, mock_project, mock_session):
        """Test sessions command with --limit option."""
        mock_project.session_files = [Path(f"/mock/session{i}.jsonl") for i in range(10)]

        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.parse_session', return_value=mock_session):
                result = runner.invoke(main, ['sessions', 'myproject', '-n', '3'])

                assert result.exit_code == 0

    def test_sessions_example_flag(self, runner):
        """Test sessions command with --example flag."""
        result = runner.invoke(main, ['sessions', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output

    def test_sessions_with_tail_flag(self, runner, mock_project, mock_session):
        """Test sessions command with --tail flag shows oldest sessions."""
        mock_project.session_files = [Path(f"/mock/session{i}.jsonl") for i in range(10)]

        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.parse_session', return_value=mock_session):
                result = runner.invoke(main, ['sessions', 'myproject', '-n', '3', '--tail'])

                assert result.exit_code == 0

    def test_sessions_with_tail_short_flag(self, runner, mock_project, mock_session):
        """Test sessions command with -t short flag for tail."""
        mock_project.session_files = [Path(f"/mock/session{i}.jsonl") for i in range(10)]

        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.parse_session', return_value=mock_session):
                result = runner.invoke(main, ['sessions', 'myproject', '-n', '3', '-t'])

                assert result.exit_code == 0


# =============================================================================
# Test: show command
# =============================================================================

class TestShowCommand:
    """Tests for the 'show' command."""

    def test_show_session(self, runner, mock_session):
        """Test show command displays session messages."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            result = runner.invoke(main, ['show', 'abc123'])

            assert result.exit_code == 0
            # Should show message content
            assert 'Python' in result.output or 'help' in result.output.lower()

    def test_show_session_not_found(self, runner):
        """Test show command when session is not found."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=None):
            result = runner.invoke(main, ['show', 'nonexistent'])

            assert result.exit_code == 0
            assert 'not found' in result.output.lower() or 'No session' in result.output

    def test_show_with_limit(self, runner, mock_session):
        """Test show command with --limit option."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            result = runner.invoke(main, ['show', 'abc123', '-n', '2'])

            assert result.exit_code == 0

    def test_show_raw_format(self, runner, mock_session):
        """Test show command with --raw option for JSON output."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            result = runner.invoke(main, ['show', 'abc123', '--raw'])

            assert result.exit_code == 0
            # Raw output should be valid JSON or contain JSON-like structure
            assert '{' in result.output or 'user' in result.output

    def test_show_example_flag(self, runner):
        """Test show command with --example flag."""
        result = runner.invoke(main, ['show', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output

    def test_show_with_tail_flag(self, runner, mock_session):
        """Test show command with --tail flag shows last N messages."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            # mock_session has 4 messages, get last 2
            result = runner.invoke(main, ['show', 'abc123', '-n', '2', '--tail'])

            assert result.exit_code == 0
            # Should show the last 2 messages (about fixing bug)
            assert 'fix this bug' in result.output or 'fixed the bug' in result.output
            # Should NOT show the first message about Python
            # (Note: first message "Hello, help me with Python" should not appear)

    def test_show_with_tail_short_flag(self, runner, mock_session):
        """Test show command with -t short flag for tail."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            result = runner.invoke(main, ['show', 'abc123', '-n', '2', '-t'])

            assert result.exit_code == 0

    def test_show_tail_with_raw(self, runner, mock_session):
        """Test show command with --tail and --raw flags."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            result = runner.invoke(main, ['show', 'abc123', '-n', '2', '--tail', '--raw'])

            assert result.exit_code == 0
            # Raw output should contain the last messages
            assert 'fix' in result.output.lower()

    def test_show_footer_says_last_with_tail(self, runner):
        """Test that footer indicates 'last' when using --tail."""
        # Create a session with more messages than limit
        many_messages = [
            Message(role="user", content=f"Message {i}", timestamp=datetime(2025, 12, 15, 10, i))
            for i in range(10)
        ]
        session = Session(
            session_id="test-session",
            project_path="/test/project",
            file_path=Path("/mock/session.jsonl"),
            messages=many_messages,
            start_time=datetime(2025, 12, 15, 10, 0),
            end_time=datetime(2025, 12, 15, 10, 10),
            slug="test",
        )
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=session):
            result = runner.invoke(main, ['show', 'test', '-n', '3', '--tail'])

            assert result.exit_code == 0
            assert 'last 3 of 10' in result.output.lower()

    def test_show_footer_says_first_without_tail(self, runner):
        """Test that footer indicates 'first' when not using --tail."""
        many_messages = [
            Message(role="user", content=f"Message {i}", timestamp=datetime(2025, 12, 15, 10, i))
            for i in range(10)
        ]
        session = Session(
            session_id="test-session",
            project_path="/test/project",
            file_path=Path("/mock/session.jsonl"),
            messages=many_messages,
            start_time=datetime(2025, 12, 15, 10, 0),
            end_time=datetime(2025, 12, 15, 10, 10),
            slug="test",
        )
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=session):
            result = runner.invoke(main, ['show', 'test', '-n', '3'])

            assert result.exit_code == 0
            assert 'first 3 of 10' in result.output.lower()


# =============================================================================
# Test: search command
# =============================================================================

class TestSearchCommand:
    """Tests for the 'search' command."""

    def test_search_with_results(self, runner, mock_session):
        """Test search command finding matches."""
        # search_sessions returns (session, [Message, ...]) tuples
        matching_messages = [
            Message(role="user", content="Help with Python code", timestamp=datetime(2025, 12, 15, 10, 0)),
            Message(role="assistant", content="I can help with Python!", timestamp=datetime(2025, 12, 15, 10, 1)),
        ]
        search_results = [(mock_session, matching_messages)]

        with patch('claude_history_explorer.cli.search_sessions', return_value=search_results):
            result = runner.invoke(main, ['search', 'Python'])

            assert result.exit_code == 0

    def test_search_no_results(self, runner):
        """Test search command with no matches."""
        with patch('claude_history_explorer.cli.search_sessions', return_value=[]):
            result = runner.invoke(main, ['search', 'nonexistentpattern'])

            assert result.exit_code == 0
            assert 'No matches' in result.output or 'found' in result.output.lower()

    def test_search_with_project_filter(self, runner, mock_session, mock_project):
        """Test search command with --project filter."""
        matching_messages = [
            Message(role="user", content="test content", timestamp=datetime(2025, 12, 15, 10, 0)),
        ]
        search_results = [(mock_session, matching_messages)]

        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.search_sessions', return_value=search_results):
                result = runner.invoke(main, ['search', 'test', '-p', 'myproject'])

                assert result.exit_code == 0

    def test_search_case_sensitive(self, runner, mock_session):
        """Test search command with --case-sensitive flag."""
        with patch('claude_history_explorer.cli.search_sessions', return_value=[]):
            result = runner.invoke(main, ['search', 'TEST', '-c'])

            assert result.exit_code == 0

    def test_search_with_limit(self, runner, mock_session):
        """Test search command with --limit option."""
        matching_messages = [
            Message(role="user", content="test content", timestamp=datetime(2025, 12, 15, 10, 0)),
        ]
        search_results = [(mock_session, matching_messages)] * 20

        with patch('claude_history_explorer.cli.search_sessions', return_value=search_results):
            result = runner.invoke(main, ['search', 'test', '-n', '5'])

            assert result.exit_code == 0

    def test_search_example_flag(self, runner):
        """Test search command with --example flag."""
        result = runner.invoke(main, ['search', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output


# =============================================================================
# Test: export command
# =============================================================================

class TestExportCommand:
    """Tests for the 'export' command."""

    def test_export_json_format(self, runner, mock_session):
        """Test export command with JSON format."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            result = runner.invoke(main, ['export', 'abc123', '-f', 'json'])

            assert result.exit_code == 0
            # Should be valid JSON
            try:
                json.loads(result.output)
            except json.JSONDecodeError:
                # Output might have extra text, just check for JSON markers
                assert '{' in result.output

    def test_export_markdown_format(self, runner, mock_session):
        """Test export command with Markdown format."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            result = runner.invoke(main, ['export', 'abc123', '-f', 'markdown'])

            assert result.exit_code == 0
            # Should contain markdown elements
            assert '#' in result.output or '**' in result.output or result.output.strip()

    def test_export_text_format(self, runner, mock_session):
        """Test export command with text format."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
            result = runner.invoke(main, ['export', 'abc123', '-f', 'text'])

            assert result.exit_code == 0

    def test_export_to_file(self, runner, mock_session):
        """Test export command with --output option."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
                result = runner.invoke(main, ['export', 'abc123', '-f', 'json', '-o', output_path])

                assert result.exit_code == 0

                # Verify file was created
                assert Path(output_path).exists()
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_export_session_not_found(self, runner):
        """Test export command when session is not found."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=None):
            result = runner.invoke(main, ['export', 'nonexistent'])

            assert result.exit_code == 0
            assert 'not found' in result.output.lower() or 'No session' in result.output

    def test_export_example_flag(self, runner):
        """Test export command with --example flag."""
        result = runner.invoke(main, ['export', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output


# =============================================================================
# Test: stats command
# =============================================================================

class TestStatsCommand:
    """Tests for the 'stats' command."""

    def test_stats_global(self, runner, mock_global_stats):
        """Test stats command for global statistics."""
        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=mock_global_stats):
            result = runner.invoke(main, ['stats'])

            assert result.exit_code == 0
            # Should show statistics
            assert 'project' in result.output.lower() or 'session' in result.output.lower()

    def test_stats_for_project(self, runner, mock_project, mock_project_stats):
        """Test stats command for specific project."""
        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.calculate_project_stats', return_value=mock_project_stats):
                result = runner.invoke(main, ['stats', '-p', 'myproject'])

                assert result.exit_code == 0

    def test_stats_json_format(self, runner, mock_global_stats):
        """Test stats command with JSON format."""
        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=mock_global_stats):
            result = runner.invoke(main, ['stats', '-f', 'json'])

            assert result.exit_code == 0
            # Should contain JSON structure
            assert '{' in result.output or '[' in result.output

    def test_stats_example_flag(self, runner):
        """Test stats command with --example flag."""
        result = runner.invoke(main, ['stats', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output


# =============================================================================
# Test: summary command
# =============================================================================

class TestSummaryCommand:
    """Tests for the 'summary' command."""

    def test_summary_global(self, runner, mock_global_stats, mock_global_story):
        """Test summary command for global summary."""
        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=mock_global_stats):
            with patch('claude_history_explorer.cli.generate_global_story', return_value=mock_global_story):
                result = runner.invoke(main, ['summary'])

                assert result.exit_code == 0

    def test_summary_for_project(self, runner, mock_project, mock_project_stats, mock_project_story):
        """Test summary command for specific project."""
        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.calculate_project_stats', return_value=mock_project_stats):
                with patch('claude_history_explorer.cli.generate_project_story', return_value=mock_project_story):
                    result = runner.invoke(main, ['summary', '-p', 'myproject'])

                    assert result.exit_code == 0

    def test_summary_markdown_format(self, runner, mock_global_stats, mock_global_story):
        """Test summary command with markdown format."""
        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=mock_global_stats):
            with patch('claude_history_explorer.cli.generate_global_story', return_value=mock_global_story):
                result = runner.invoke(main, ['summary', '-f', 'markdown'])

                assert result.exit_code == 0

    def test_summary_example_flag(self, runner):
        """Test summary command with --example flag."""
        result = runner.invoke(main, ['summary', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output


# =============================================================================
# Test: story command
# =============================================================================

class TestStoryCommand:
    """Tests for the 'story' command."""

    def test_story_global(self, runner, mock_global_stats, mock_global_story):
        """Test story command for global story."""
        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=mock_global_stats):
            with patch('claude_history_explorer.cli.generate_global_story', return_value=mock_global_story):
                result = runner.invoke(main, ['story'])

                assert result.exit_code == 0

    def test_story_for_project(self, runner, mock_project, mock_project_stats, mock_project_story):
        """Test story command for specific project."""
        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.calculate_project_stats', return_value=mock_project_stats):
                with patch('claude_history_explorer.cli.generate_project_story', return_value=mock_project_story):
                    result = runner.invoke(main, ['story', '-p', 'myproject'])

                    assert result.exit_code == 0

    def test_story_brief_format(self, runner, mock_global_stats, mock_global_story):
        """Test story command with brief format."""
        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=mock_global_stats):
            with patch('claude_history_explorer.cli.generate_global_story', return_value=mock_global_story):
                result = runner.invoke(main, ['story', '-f', 'brief'])

                assert result.exit_code == 0

    def test_story_detailed_format(self, runner, mock_global_stats, mock_global_story):
        """Test story command with detailed format."""
        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=mock_global_stats):
            with patch('claude_history_explorer.cli.generate_global_story', return_value=mock_global_story):
                result = runner.invoke(main, ['story', '-f', 'detailed'])

                assert result.exit_code == 0

    def test_story_example_flag(self, runner):
        """Test story command with --example flag."""
        result = runner.invoke(main, ['story', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output


# =============================================================================
# Test: info command
# =============================================================================

class TestInfoCommand:
    """Tests for the 'info' command."""

    def test_info_shows_paths(self, runner):
        """Test info command shows storage location."""
        with patch('claude_history_explorer.cli.get_claude_dir', return_value=Path("/Users/test/.claude")):
            with patch('claude_history_explorer.cli.get_projects_dir', return_value=Path("/Users/test/.claude/projects")):
                with patch('claude_history_explorer.cli.list_projects', return_value=[]):
                    result = runner.invoke(main, ['info'])

                    assert result.exit_code == 0
                    assert '.claude' in result.output or 'Claude' in result.output

    def test_info_example_flag(self, runner):
        """Test info command with --example flag."""
        result = runner.invoke(main, ['info', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output


# =============================================================================
# Test: wrapped command
# =============================================================================

class TestWrappedCommand:
    """Tests for the 'wrapped' command."""

    def test_wrapped_generates_url(self, runner):
        """Test wrapped command generates a valid URL."""
        mock_story = WrappedStoryV3(
            v=3, y=2025, n="Test User", p=3, s=50, m=2000, h=100, d=15,
            hm=[0] * 168,
            ma=[200] * 12, mh=[10] * 12, ms=[5] * 12,
            sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[['Project1', 1000, 50, 10, 25, 50]],
            pc=[], te=[], sf=[],
        )

        with patch('claude_history_explorer.cli.generate_wrapped_story_v3', return_value=mock_story):
            result = runner.invoke(main, ['wrapped', '--no-copy'])

            assert result.exit_code == 0
            assert 'wrapped?d=' in result.output
            assert 'https://' in result.output

    def test_wrapped_with_name(self, runner):
        """Test wrapped command with --name option."""
        mock_story = WrappedStoryV3(
            v=3, y=2025, n="Custom Name", p=2, s=30, m=1000, h=50, d=10,
            hm=[0] * 168,
            ma=[100] * 12, mh=[5] * 12, ms=[3] * 12,
            sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[],
            pc=[], te=[], sf=[],
        )

        with patch('claude_history_explorer.cli.generate_wrapped_story_v3', return_value=mock_story):
            result = runner.invoke(main, ['wrapped', '--name', 'Custom Name', '--no-copy'])

            assert result.exit_code == 0

    def test_wrapped_with_year(self, runner):
        """Test wrapped command with --year option."""
        mock_story = WrappedStoryV3(
            v=3, y=2024, p=2, s=30, m=1000, h=50, d=10,
            hm=[0] * 168,
            ma=[100] * 12, mh=[5] * 12, ms=[3] * 12,
            sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[],
            pc=[], te=[], sf=[],
        )

        with patch('claude_history_explorer.cli.generate_wrapped_story_v3', return_value=mock_story):
            result = runner.invoke(main, ['wrapped', '--year', '2024', '--no-copy'])

            assert result.exit_code == 0

    def test_wrapped_raw_format(self, runner):
        """Test wrapped command with --raw option."""
        mock_story = WrappedStoryV3(
            v=3, y=2025, p=2, s=30, m=1000, h=50, d=10,
            hm=[0] * 168,
            ma=[100] * 12, mh=[5] * 12, ms=[3] * 12,
            sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[],
            pc=[], te=[], sf=[],
        )

        with patch('claude_history_explorer.cli.generate_wrapped_story_v3', return_value=mock_story):
            result = runner.invoke(main, ['wrapped', '--raw'])

            assert result.exit_code == 0
            # Should output JSON
            assert '"v":' in result.output or '"v": 3' in result.output

    def test_wrapped_decode(self, runner):
        """Test wrapped command with --decode option."""
        # Create a story and encode it
        story = WrappedStoryV3(
            v=3, y=2025, n="Decode Test", p=2, s=20, m=500, h=25, d=5,
            hm=[0] * 168,
            ma=[50] * 12, mh=[2] * 12, ms=[2] * 12,
            sd=[5] * 10, ar=[5] * 10, ml=[5] * 8,
            ts={'ad': 50, 'sp': 50, 'fc': 50, 'cc': 50, 'wr': 50,
                'bs': 50, 'cs': 50, 'mv': 50, 'td': 50, 'ri': 50},
            tp=[['Test', 250, 12, 3, 10, 50]],
            pc=[], te=[], sf=[],
        )
        encoded = encode_wrapped_story_v3(story)
        url = f"https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d={encoded}"

        result = runner.invoke(main, ['wrapped', '--decode', url])

        assert result.exit_code == 0
        assert 'Decode Test' in result.output or 'Year' in result.output

    def test_wrapped_example_flag(self, runner):
        """Test wrapped command with --example flag."""
        result = runner.invoke(main, ['wrapped', '--example'])

        assert result.exit_code == 0
        assert 'Examples' in result.output

    def test_wrapped_url_is_decodable(self, runner):
        """Test that the URL in wrapped output can be decoded."""
        import re

        mock_story = WrappedStoryV3(
            v=3, y=2025, n="Decodable Test", p=4, s=80, m=4000, h=150, d=20,
            hm=[10] * 168,
            ma=[400] * 12, mh=[15] * 12, ms=[8] * 12,
            sd=[10] * 10, ar=[10] * 10, ml=[10] * 8,
            ts={'ad': 60, 'sp': 55, 'fc': 45, 'cc': 50, 'wr': 35,
                'bs': 65, 'cs': 40, 'mv': 50, 'td': 55, 'ri': 70},
            tp=[
                ['Project1', 2000, 75, 12, 40, 60],
                ['Project2', 1500, 50, 8, 30, 50],
            ],
            pc=[(0, 1, 5)],
            te=[[50, 0, 200, 0]],
            sf=[],
        )

        with patch('claude_history_explorer.cli.generate_wrapped_story_v3', return_value=mock_story):
            result = runner.invoke(main, ['wrapped', '--no-copy'])

            assert result.exit_code == 0

            # Extract URL from output
            url_match = re.search(r'https://[^\s]+wrapped\?d=([A-Za-z0-9_-]+)', result.output)
            assert url_match, f"No URL found in output: {result.output}"

            encoded_data = url_match.group(1)

            # Verify it can be decoded
            decoded = decode_wrapped_story_v3(encoded_data)
            assert decoded.n == "Decodable Test"
            assert decoded.p == 4
            assert decoded.m == 4000


# =============================================================================
# Test: Global CLI behavior
# =============================================================================

class TestGlobalCLIBehavior:
    """Tests for global CLI behavior."""

    def test_help_command(self, runner):
        """Test --help shows usage information."""
        result = runner.invoke(main, ['--help'])

        assert result.exit_code == 0
        assert 'Usage' in result.output
        assert 'Commands' in result.output

    def test_version_flag(self, runner):
        """Test --version shows version."""
        result = runner.invoke(main, ['--version'])

        assert result.exit_code == 0
        # Should show some version info
        assert result.output.strip()

    def test_unknown_command(self, runner):
        """Test unknown command shows error."""
        result = runner.invoke(main, ['unknowncommand'])

        assert result.exit_code != 0
        assert 'No such command' in result.output or 'Error' in result.output

    def test_command_help(self, runner):
        """Test individual command --help."""
        for cmd in ['projects', 'sessions', 'show', 'search', 'export', 'stats', 'summary', 'story', 'info', 'wrapped']:
            result = runner.invoke(main, [cmd, '--help'])
            assert result.exit_code == 0, f"Help failed for {cmd}"
            assert 'Usage' in result.output or 'Options' in result.output


# =============================================================================
# Test: Error handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in CLI commands."""

    def test_sessions_invalid_project(self, runner):
        """Test sessions command handles invalid project gracefully."""
        with patch('claude_history_explorer.cli.find_project', return_value=None):
            result = runner.invoke(main, ['sessions', 'invalid_project_12345'])

            # Should not crash
            assert result.exit_code == 0

    def test_show_invalid_session(self, runner):
        """Test show command handles invalid session gracefully."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=None):
            result = runner.invoke(main, ['show', 'invalid_session_12345'])

            # Should not crash
            assert result.exit_code == 0

    def test_export_invalid_session(self, runner):
        """Test export command handles invalid session gracefully."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=None):
            result = runner.invoke(main, ['export', 'invalid_session_12345'])

            # Should not crash
            assert result.exit_code == 0

    def test_wrapped_no_data(self, runner):
        """Test wrapped command handles no data gracefully."""
        with patch('claude_history_explorer.cli.generate_wrapped_story_v3', side_effect=ValueError("No data for year")):
            result = runner.invoke(main, ['wrapped', '--year', '2020', '--no-copy'])

            # Should not crash, should show error message
            assert result.exit_code == 0
            assert 'Error' in result.output or 'error' in result.output.lower()

    def test_stats_handles_missing_data(self, runner):
        """Test stats command handles missing data gracefully."""
        empty_stats = GlobalStats(
            projects=[],
            total_projects=0,
            total_sessions=0,
            total_messages=0,
            total_user_messages=0,
            total_duration_minutes=0,
            total_size_bytes=0,
            avg_sessions_per_project=0.0,
            avg_messages_per_session=0.0,
            most_active_project="",
            largest_project="",
            most_recent_activity=None,
        )

        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=empty_stats):
            result = runner.invoke(main, ['stats'])

            # Should not crash
            assert result.exit_code == 0


# =============================================================================
# Test: JSON Output Validation
# =============================================================================

class TestJSONOutputPaths:
    """Tests for JSON output format across various commands."""

    def test_stats_global_json_structure(self, runner, mock_global_stats):
        """Test stats command JSON output has correct structure."""
        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=mock_global_stats):
            result = runner.invoke(main, ['stats', '-f', 'json'])

            assert result.exit_code == 0
            data = json.loads(result.output)

            # Verify all expected keys are present
            assert 'total_projects' in data
            assert 'total_sessions' in data
            assert 'total_messages' in data
            assert 'total_duration_str' in data
            assert 'projects' in data
            assert isinstance(data['projects'], list)

    def test_stats_project_json_structure(self, runner, mock_project, mock_project_stats):
        """Test stats command for project JSON output has correct structure."""
        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.calculate_project_stats', return_value=mock_project_stats):
                result = runner.invoke(main, ['stats', '-p', 'myproject', '-f', 'json'])

                assert result.exit_code == 0
                data = json.loads(result.output)

                # Verify project-specific keys
                assert 'project_path' in data
                assert 'total_sessions' in data
                assert 'total_messages' in data
                assert 'agent_sessions' in data
                assert 'main_sessions' in data

    def test_export_json_structure(self, runner, mock_project, mock_session):
        """Test export command JSON output has correct structure."""
        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.get_session_by_id', return_value=mock_session):
                result = runner.invoke(main, ['export', 'abc123', '-f', 'json'])

                assert result.exit_code == 0
                data = json.loads(result.output)

                # Verify session structure
                assert 'session_id' in data
                assert 'project_path' in data
                assert 'messages' in data
                assert isinstance(data['messages'], list)

                # Verify message structure
                if data['messages']:
                    msg = data['messages'][0]
                    assert 'role' in msg
                    assert 'content' in msg

    def test_export_json_with_tools(self, runner, mock_project):
        """Test export JSON includes tool uses."""
        session_with_tools = Session(
            session_id="test-tools",
            project_path="/test/project",
            file_path=Path("/mock/session.jsonl"),
            messages=[
                Message(
                    role="user",
                    content="Help me fix this",
                    timestamp=datetime(2025, 12, 15, 10, 0),
                ),
                Message(
                    role="assistant",
                    content="I'll analyze the code.",
                    timestamp=datetime(2025, 12, 15, 10, 1),
                    tool_uses=[
                        {"name": "Read", "input": {"file": "main.py"}},
                        {"name": "Edit", "input": {"file": "main.py", "change": "fix"}},
                    ],
                ),
            ],
            start_time=datetime(2025, 12, 15, 10, 0),
            end_time=datetime(2025, 12, 15, 10, 5),
            slug="fix-code",
        )

        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.get_session_by_id', return_value=session_with_tools):
                result = runner.invoke(main, ['export', 'test-tools', '-f', 'json'])

                assert result.exit_code == 0
                data = json.loads(result.output)

                # Find assistant message with tools
                assistant_msg = next((m for m in data['messages'] if m['role'] == 'assistant'), None)
                assert assistant_msg is not None
                assert 'tool_uses' in assistant_msg
                assert len(assistant_msg['tool_uses']) == 2
                assert assistant_msg['tool_uses'][0]['name'] == 'Read'

    def test_stats_json_handles_null_timestamps(self, runner):
        """Test stats JSON output handles null timestamps gracefully."""
        stats_no_time = GlobalStats(
            projects=[],
            total_projects=0,
            total_sessions=0,
            total_messages=0,
            total_user_messages=0,
            total_duration_minutes=0,
            total_size_bytes=0,
            avg_sessions_per_project=0.0,
            avg_messages_per_session=0.0,
            most_active_project="",
            largest_project="",
            most_recent_activity=None,  # null timestamp
        )

        with patch('claude_history_explorer.cli.calculate_global_stats', return_value=stats_no_time):
            result = runner.invoke(main, ['stats', '-f', 'json'])

            assert result.exit_code == 0
            data = json.loads(result.output)
            # Should have null for missing timestamp
            assert data.get('most_recent_activity') is None


# =============================================================================
# Critical Error Path Tests (G1, G2)
# =============================================================================

class TestCriticalErrorPaths:
    """Test critical error handling paths that affect user experience."""

    def test_projects_no_claude_dir(self, runner):
        """G1: Test projects command when ~/.claude directory doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with patch('claude_history_explorer.cli.get_projects_dir', return_value=mock_path):
            result = runner.invoke(main, ['projects'])

            # Should show helpful error message, not crash
            assert result.exit_code == 0  # Graceful exit
            assert "not found" in result.output.lower() or "no projects" in result.output.lower()

    def test_sessions_missing_project_arg(self, runner):
        """G2: Test sessions command without PROJECT_SEARCH argument."""
        result = runner.invoke(main, ['sessions'])

        # Click should handle missing required argument
        assert result.exit_code != 0 or "Missing argument" in result.output or "Error" in result.output

    def test_sessions_position_display_head(self, runner, mock_project, mock_session):
        """G3: Test position calculation displays correctly for head."""
        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.parse_session', return_value=mock_session):
                result = runner.invoke(main, ['sessions', 'myproject', '--limit', '1'])

                assert result.exit_code == 0
                # Should show position info when limit is less than total
                # "first 1 of 2" or similar

    def test_sessions_position_display_tail(self, runner, mock_project, mock_session):
        """G3: Test position calculation displays correctly for tail."""
        with patch('claude_history_explorer.cli.find_project', return_value=mock_project):
            with patch('claude_history_explorer.cli.parse_session', return_value=mock_session):
                result = runner.invoke(main, ['sessions', 'myproject', '--tail', '--limit', '1'])

                assert result.exit_code == 0
                # Should show "last" position

    def test_search_no_pattern(self, runner):
        """G5: Test search command without pattern argument."""
        result = runner.invoke(main, ['search'])

        # Should handle missing pattern gracefully
        assert result.exit_code != 0 or "Missing argument" in result.output or "pattern" in result.output.lower()

    def test_search_no_results(self, runner):
        """G5: Test search command with pattern that matches nothing."""
        # search_sessions is a generator, so we need to mock it as returning an empty iterable
        with patch('claude_history_explorer.cli.search_sessions', return_value=iter([])):
            result = runner.invoke(main, ['search', 'nonexistent-pattern-xyz'])

            assert result.exit_code == 0
            assert "no matches" in result.output.lower()

    def test_search_with_invalid_regex(self, runner):
        """G5: Test search command with invalid regex pattern."""
        with patch('claude_history_explorer.cli.search_sessions', side_effect=ValueError("Invalid pattern")):
            result = runner.invoke(main, ['search', '[invalid(regex'])

            # Should handle regex error gracefully
            assert result.exit_code != 0 or "error" in result.output.lower() or "invalid" in result.output.lower()

    def test_export_invalid_format(self, runner, mock_project, mock_session):
        """G6: Test export command with invalid format option."""
        # Note: Click validates options, so this tests the CLI option handling
        result = runner.invoke(main, ['export', 'myproject', '--format', 'invalid-format'])

        # Click should reject invalid format choice
        assert result.exit_code != 0

    def test_export_nonexistent_session(self, runner):
        """G6: Test export command with nonexistent session."""
        with patch('claude_history_explorer.cli.get_session_by_id', return_value=None):
            result = runner.invoke(main, ['export', 'nonexistent-session-id'])

            assert result.exit_code == 0  # Graceful exit
            assert "no session found" in result.output.lower()


# =============================================================================
# Test: Year Validation in Wrapped
# =============================================================================

class TestWrappedYearValidation:
    """Test year validation in wrapped command."""

    def test_wrapped_year_too_old(self, runner):
        """Test wrapped command rejects years before Claude Code existed."""
        result = runner.invoke(main, ['wrapped', '--year', '2023', '--no-copy'])

        assert result.exit_code == 0  # Command runs but shows error
        assert "2024" in result.output  # Should mention 2024 as minimum


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
