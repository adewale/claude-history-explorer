import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import click
import msgpack
import pytest
from click.testing import CliRunner

from claude_history_explorer.cli import _generate_global_summary, _sanitize_output_path, main
from claude_history_explorer.models import GlobalStats, Message, Project, ProjectStats, Session
from claude_history_explorer.parser import get_session_by_id, parse_session, search_sessions
from claude_history_explorer.stories import generate_project_story
from claude_history_explorer.utils import _compile_regex_safe
from claude_history_explorer.wrapped import (
    compute_activity_heatmap,
    compute_session_fingerprint,
    compute_trait_scores,
    decode_wrapped_story_v3,
    generate_wrapped_story_v3,
)


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
    _, messages = results[0]
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


def test_parse_session_reads_lines_with_an_explicit_size_bound(monkeypatch, tmp_path):
    class BoundedOnlyFile:
        def __init__(self):
            self.lines = [
                b"x" * 250 + b"\n",
                b'{"type":"user","timestamp":"2025-01-01T00:00:00Z","message":{"content":"ok"}}\n',
                b"",
            ]
            self.sizes: list[int] = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def __iter__(self):
            raise AssertionError("parse_session must use bounded readline(), not file iteration")

        def readline(self, size: int = -1):
            assert size > 0
            self.sizes.append(size)
            return self.lines.pop(0)

    fake_file = BoundedOnlyFile()
    monkeypatch.setattr("claude_history_explorer.parser.MAX_LINE_BYTES", 200)
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: fake_file)

    session = parse_session(tmp_path / "bounded.jsonl")

    assert session.message_count == 1
    assert session.messages[0].content == "ok"
    assert fake_file.sizes and max(fake_file.sizes) == 201


def test_parse_session_discards_only_the_oversized_physical_line(monkeypatch, tmp_path):
    session_file = tmp_path / "oversized.jsonl"
    valid = b'{"type":"user","timestamp":"2025-01-01T00:00:00Z","message":{"content":"ok"}}\n'
    session_file.write_bytes(b"x" * 250 + b"\n" + valid)
    monkeypatch.setattr("claude_history_explorer.parser.MAX_LINE_BYTES", 200)

    session = parse_session(session_file)

    assert session.message_count == 1
    assert session.messages[0].content == "ok"


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


def test_search_project_filter_miss_does_not_search_all_projects(monkeypatch):
    monkeypatch.setattr("claude_history_explorer.cli.find_project", lambda _name: None)
    with patch("claude_history_explorer.cli.search_sessions") as search_mock:
        result = CliRunner().invoke(main, ["search", "needle", "-p", "missing-project"])

    assert result.exit_code == 0
    assert "No project found" in result.output
    search_mock.assert_not_called()


def test_show_project_filter_miss_does_not_search_all_projects(monkeypatch):
    monkeypatch.setattr("claude_history_explorer.cli.find_project", lambda _name: None)
    with patch("claude_history_explorer.cli.get_session_by_id") as session_mock:
        result = CliRunner().invoke(main, ["show", "abc123", "-p", "missing-project"])

    assert result.exit_code == 0
    assert "No project found" in result.output
    session_mock.assert_not_called()


def test_export_project_filter_miss_does_not_export_from_all_projects(monkeypatch):
    monkeypatch.setattr("claude_history_explorer.cli.find_project", lambda _name: None)
    with patch("claude_history_explorer.cli.get_session_by_id") as session_mock:
        result = CliRunner().invoke(main, ["export", "abc123", "-p", "missing-project"])

    assert result.exit_code == 0
    assert "No project found" in result.output
    session_mock.assert_not_called()


def test_session_partial_id_matches_substrings_for_documented_partial_lookup(tmp_path):
    session_file = tmp_path / "abc-middle-def.jsonl"
    _jsonl(
        session_file,
        [
            {
                "type": "user",
                "message": {"content": "hello"},
                "timestamp": "2025-01-01T00:00:00Z",
            }
        ],
    )
    project = Project("-tmp-project", "/tmp/project", tmp_path, [session_file])

    session = get_session_by_id("middle", project)

    assert session is not None
    assert session.session_id == "abc-middle-def"


def test_regex_safety_rejects_bounded_optional_backtracking_pattern():
    with pytest.raises(ValueError, match="slow matching"):
        _compile_regex_safe(r"^(a?){30}a{30}$")


def test_session_fingerprint_quarters_start_in_first_bucket_for_short_sessions(tmp_path):
    def make_session(message_count: int) -> Session:
        messages = [Message(role="user", content=str(i)) for i in range(message_count)]
        return Session(
            session_id=f"s{message_count}",
            project_path="/tmp/project",
            file_path=tmp_path / f"s{message_count}.jsonl",
            messages=messages,
        )

    assert compute_session_fingerprint(make_session(2))[:4] == [100, 0, 100, 0]
    assert compute_session_fingerprint(make_session(3))[:4] == [100, 100, 100, 0]
    assert compute_session_fingerprint(make_session(5))[:4] == [100, 50, 50, 50]


def _encode_msgpack_payload(payload: dict) -> str:
    packed = msgpack.packb(payload, use_bin_type=True)
    return base64.urlsafe_b64encode(packed).rstrip(b"=").decode("ascii")


def _valid_wrapped_payload(**overrides) -> dict:
    payload = {
        "v": 3,
        "y": 2025,
        "p": 1,
        "s": 1,
        "m": 1,
        "h": 1,
        "d": 1,
        "hm": [0] * 168,
        "ma": [0] * 12,
        "mh": [0] * 12,
        "ms": [0] * 12,
        "sd": [0] * 10,
        "ar": [0] * 10,
        "ml": [0] * 8,
        "ts": {"ad": 50, "sp": 50, "fc": 50, "cc": 50, "wr": 50, "bs": 50, "cs": 50, "mv": 50, "td": 50, "ri": 50},
        "tp": [["Project", 1, 1, 1, 1, 0]],
        "pc": [],
        "te": [],
        "sf": [],
        "ls": 1,
        "sk": [0, 0, 0, 0],
        "tk": {"total": 0, "input": 0, "output": 0, "cache_read": 0, "cache_create": 0, "models": {}},
    }
    payload.update(overrides)
    return payload


def test_python_wrapped_decode_rejects_future_wire_versions():
    encoded = _encode_msgpack_payload(_valid_wrapped_payload(v=4))

    with pytest.raises(ValueError, match="version"):
        decode_wrapped_story_v3(encoded)


def test_python_wrapped_decode_rejects_rle_heatmap_with_wrong_expanded_size():
    encoded = _encode_msgpack_payload(_valid_wrapped_payload(hm=[0, 169], hm_rle=True))

    with pytest.raises(ValueError, match="heatmap"):
        decode_wrapped_story_v3(encoded)


def test_python_wrapped_decode_rejects_non_base64url_payloads():
    with pytest.raises(ValueError, match="Invalid"):
        decode_wrapped_story_v3("!!!!")


def test_python_wrapped_decode_rejects_oversized_payloads_before_unpacking():
    with pytest.raises(ValueError, match="too large"):
        decode_wrapped_story_v3("A" * 100_001)


def test_wrapped_keeps_distinct_projects_with_same_basename(tmp_path, monkeypatch):
    def write_session(path: Path, content: str) -> None:
        _jsonl(
            path,
            [
                {
                    "type": "user",
                    "timestamp": "2025-06-01T10:00:00Z",
                    "message": {"content": content},
                }
            ],
        )

    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first_file = first_dir / "first-session.jsonl"
    second_file = second_dir / "second-session.jsonl"
    write_session(first_file, "first")
    write_session(second_file, "second")
    projects = [
        Project("-work-app", "/work/app", first_dir, [first_file]),
        Project("-archive-app", "/archive/app", second_dir, [second_file]),
    ]
    monkeypatch.setattr("claude_history_explorer.wrapped.list_projects", lambda: projects)

    story = generate_wrapped_story_v3(2025)

    assert story.p == 2
    assert len(story.tp) == 2
    assert {project[0] for project in story.tp} == {"app", "app (2)"}


def test_decode_project_path_handles_long_hyphenated_existing_component(tmp_path):
    target = tmp_path / "my-five-part-long-folder"
    target.mkdir()
    encoded = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in str(target))

    assert Project._decode_project_path(encoded) == str(target)
