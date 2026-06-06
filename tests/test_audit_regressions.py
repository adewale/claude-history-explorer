import json
from datetime import datetime, timezone
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from claude_history_explorer.cli import _generate_global_summary, _sanitize_output_path, main
from claude_history_explorer.models import GlobalStats, Project, ProjectStats
from claude_history_explorer.parser import parse_session, search_sessions
from claude_history_explorer.stories import generate_project_story
from claude_history_explorer.wrapped import compute_activity_heatmap, compute_trait_scores


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_output_path_rejects_sibling_prefix_escape(tmp_path, monkeypatch):
    workdir = tmp_path / "project"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    with pytest.raises(click.ClickException):
        _sanitize_output_path("../project2/out.md")


def test_search_invalid_regex_reports_click_error_without_traceback():
    result = CliRunner().invoke(main, ["search", "["])

    assert result.exit_code != 0
    assert "Invalid regex" in result.output
    assert "Traceback" not in result.output


def test_search_sessions_deduplicates_message_matching_content_and_tool_input(tmp_path, monkeypatch):
    project_dir = tmp_path / "-tmp-project"
    project_dir.mkdir()
    session_file = project_dir / "abc.jsonl"
    _jsonl(
        session_file,
        [
            {
                "type": "assistant",
                "timestamp": "2025-01-01T00:00:00Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "needle in content"},
                        {"type": "tool_use", "name": "Read", "input": {"query": "needle in tool"}},
                    ]
                },
            }
        ],
    )
    project = Project("-tmp-project", str(tmp_path / "project"), project_dir, [session_file])
    monkeypatch.setattr("claude_history_explorer.parser.list_projects", lambda: [project])

    results = list(search_sessions("needle"))

    assert len(results) == 1
    _, messages, _regex = results[0]
    assert len(messages) == 1
    assert messages[0].content == "needle in content"


def test_global_markdown_summary_handles_projects_with_zero_sessions(tmp_path):
    project = Project("-tmp-empty", str(tmp_path / "empty"), tmp_path / "empty", [])
    project_stats = ProjectStats(
        project=project,
        total_sessions=0,
        total_messages=0,
        total_user_messages=0,
        total_duration_minutes=0,
        agent_sessions=0,
        main_sessions=0,
        total_size_bytes=0,
        avg_messages_per_session=0,
        longest_session_duration="0m",
        most_recent_session=None,
    )
    stats = GlobalStats(
        projects=[project_stats],
        total_projects=1,
        total_sessions=0,
        total_messages=0,
        total_user_messages=0,
        total_duration_minutes=0,
        total_size_bytes=0,
        avg_sessions_per_project=0,
        avg_messages_per_session=0,
        most_active_project=project.path,
        largest_project=project.path,
        most_recent_activity=None,
    )

    summary = _generate_global_summary(stats, "markdown")

    assert "Session Distribution" in summary
    assert "│" in summary


def test_project_story_counts_three_simultaneous_sessions(tmp_path):
    session_files = []
    for index in range(3):
        session_file = tmp_path / f"{index}.jsonl"
        _jsonl(
            session_file,
            [
                {
                    "type": "user",
                    "message": {"content": "hi"},
                    "timestamp": datetime(2025, 1, 1, 12, index, tzinfo=timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                }
            ],
        )
        session_files.append(session_file)
    project = Project("-tmp-project", str(tmp_path), tmp_path, session_files)

    story = generate_project_story(project)

    assert story.concurrent_claude_instances == 3
    assert any("3 Claude instances" in insight for insight in story.concurrent_insights)


def test_parse_session_skips_invalid_utf8_bytes(tmp_path):
    session_file = tmp_path / "bad.jsonl"
    session_file.write_bytes(b"\x80\x81\x82\n")

    session = parse_session(session_file)

    assert session.message_count == 0


def test_circadian_consistency_treats_midnight_wraparound_as_close():
    sessions = []
    for hour in (23, 0):
        sessions.append(
            type(
                "SessionInfoLike",
                (),
                {
                    "start_time": datetime(2025, 1, 1, hour, 0, tzinfo=timezone.utc),
                    "duration_minutes": 30,
                    "message_count": 10,
                    "is_agent": False,
                    "project_name": "proj",
                },
            )()
        )

    heatmap = compute_activity_heatmap(sessions)
    scores = compute_trait_scores(sessions, [], heatmap)

    assert scores["cc"] > 90


def test_decode_project_path_handles_long_hyphenated_existing_component(tmp_path):
    target = tmp_path / "my-five-part-long-folder"
    target.mkdir()
    encoded = str(target).replace("/", "-")
    if not encoded.startswith("-"):
        encoded = "-" + encoded

    assert Project._decode_project_path(encoded) == str(target)
