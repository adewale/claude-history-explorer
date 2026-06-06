#!/usr/bin/env python3
"""Privacy-preserving smoke test against the local Claude Code corpus.

Run from the repository root:

    uv run --locked python scripts/smoketest_local_corpus.py

The smoke test exercises the installed CLI surface against ~/.claude/projects,
captures command output instead of printing transcript content, and deletes any
exported artifacts by default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from claude_history_explorer.parser import parse_session  # noqa: E402
from claude_history_explorer.projects import list_projects  # noqa: E402

CLI = [sys.executable, "-m", "claude_history_explorer.cli"]
COMMANDS = [
    "info",
    "projects",
    "sessions",
    "show",
    "search",
    "export",
    "stats",
    "summary",
    "story",
    "wrapped",
]


class SmokeFailure(AssertionError):
    """Raised when a smoke-test check fails."""


@dataclass(frozen=True)
class CorpusSelection:
    project_path: str
    session_id: str
    wrapped_year: int
    search_pattern: str
    project_count: int
    session_count: int
    message_count: int


def _safe_label(args: Sequence[str]) -> str:
    return "claude-history " + " ".join(shlex.quote(arg) for arg in args)


def run_cli(args: Sequence[str], *, label: str | None = None, timeout: int = 90) -> str:
    """Run a CLI command and return stdout without echoing corpus content."""
    env = os.environ.copy()
    env.update({"PYTHONIOENCODING": "utf-8", "NO_COLOR": "1", "COLUMNS": "240"})
    result = subprocess.run(
        CLI + list(args),
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    display = label or _safe_label(args)
    if result.returncode != 0:
        stderr = result.stderr.strip().splitlines()[:3]
        raise SmokeFailure(
            f"{display} failed with exit {result.returncode}; stderr={stderr!r}; "
            f"stdout_bytes={len(result.stdout.encode('utf-8', errors='replace'))}"
        )
    return result.stdout


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def require_nonempty_output(output: str, label: str) -> None:
    require(bool(output.strip()), f"{label} produced no output")


def require_file(path: Path, label: str) -> None:
    require(path.exists(), f"{label} did not create {path.name}")
    require(path.stat().st_size > 0, f"{label} created an empty {path.name}")


def _find_search_pattern(session) -> str:
    """Find a literal token that should match the selected session."""
    for message in session.messages:
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{2,}", message.content):
            if 3 <= len(token) <= 64:
                return re.escape(token)
    return "."  # Last-resort regex: any non-empty message content.


def select_corpus() -> CorpusSelection:
    projects = list_projects()
    require(projects, "No Claude Code projects found in ~/.claude/projects")

    total_sessions = sum(len(project.session_files) for project in projects)
    current_year = time.localtime().tm_year
    fallback = None

    for project in projects:
        for session_file in project.session_files:
            session = parse_session(session_file, project.path)
            if session.message_count == 0:
                continue
            if fallback is None:
                fallback = (project, session)
            if session.start_time and 2024 <= session.start_time.year <= current_year:
                return CorpusSelection(
                    project_path=project.path,
                    session_id=session.session_id,
                    wrapped_year=session.start_time.year,
                    search_pattern=_find_search_pattern(session),
                    project_count=len(projects),
                    session_count=total_sessions,
                    message_count=session.message_count,
                )

    require(fallback is not None, "No parseable non-empty sessions found in local corpus")
    project, session = fallback
    year = session.start_time.year if session.start_time else current_year
    require(2024 <= year <= current_year, "No session year is valid for Wrapped smoke testing")
    return CorpusSelection(
        project_path=project.path,
        session_id=session.session_id,
        wrapped_year=year,
        search_pattern=_find_search_pattern(session),
        project_count=len(projects),
        session_count=total_sessions,
        message_count=session.message_count,
    )


def check_cli_help_and_examples() -> None:
    require_nonempty_output(run_cli(["--help"]), "top-level help")
    require_nonempty_output(run_cli(["--version"]), "version")
    for command in COMMANDS:
        require_nonempty_output(run_cli([command, "--help"]), f"{command} --help")
        require_nonempty_output(run_cli([command, "--example"]), f"{command} --example")


def check_discovery_and_stats(selection: CorpusSelection) -> None:
    require_nonempty_output(run_cli(["info"]), "info")
    require_nonempty_output(run_cli(["projects", "--limit", "10"]), "projects")
    require_nonempty_output(run_cli(["stats", "--format", "table"]), "stats table")
    require_nonempty_output(run_cli(["stats", "--show-worktype"]), "stats worktype")

    stats_json = run_cli(["stats", "--format", "json"])
    stats = json.loads(stats_json)
    require(stats["total_projects"] >= selection.project_count, "stats under-reported projects")
    require(stats["total_sessions"] >= selection.session_count, "stats under-reported sessions")

    project_stats = json.loads(
        run_cli(
            [
                "stats",
                "--project",
                selection.project_path,
                "--format",
                "json",
                "--show-worktype",
            ],
            label="claude-history stats --project <selected-project> --format json --show-worktype",
        )
    )
    require(project_stats["total_sessions"] >= 1, "project stats did not include selected session")


def check_session_browsing_and_search(selection: CorpusSelection) -> None:
    project_label = "<selected-project>"
    session_label = "<selected-session>"

    require_nonempty_output(
        run_cli(
            ["sessions", "--head", "--limit", "1", selection.project_path],
            label=f"claude-history sessions --head --limit 1 {project_label}",
        ),
        "sessions --head",
    )
    require_nonempty_output(
        run_cli(
            ["sessions", "--tail", "--limit", "1", selection.project_path],
            label=f"claude-history sessions --tail --limit 1 {project_label}",
        ),
        "sessions --tail",
    )

    for mode in ("--head", "--tail"):
        require_nonempty_output(
            run_cli(
                [
                    "show",
                    selection.session_id,
                    "--project",
                    selection.project_path,
                    mode,
                    "--limit",
                    "1",
                ],
                label=f"claude-history show {session_label} --project {project_label} {mode} --limit 1",
            ),
            f"show {mode}",
        )

    raw_show = run_cli(
        [
            "show",
            selection.session_id,
            "--project",
            selection.project_path,
            "--raw",
            "--limit",
            "1",
        ],
        label=f"claude-history show {session_label} --project {project_label} --raw --limit 1",
    )
    require('"role"' in raw_show and '"content"' in raw_show, "show --raw lacked message fields")

    for extra_args, label in (
        (["--limit", "1", "--context", "20"], "search"),
        (["--case-sensitive", "--limit", "1", "--context", "0"], "search --case-sensitive"),
    ):
        output = run_cli(
            ["search", selection.search_pattern, "--project", selection.project_path, *extra_args],
            label=f"claude-history {label} <corpus-token> --project {project_label}",
        )
        require("No matches found" not in output, f"{label} did not match the selected corpus token")


def check_exports_summaries_and_stories(selection: CorpusSelection, workdir: Path) -> None:
    project_label = "<selected-project>"
    session_label = "<selected-session>"

    export_suffix = {"json": ".json", "markdown": ".md", "text": ".txt"}
    for output_format, suffix in export_suffix.items():
        output_path = workdir / f"session-{output_format}{suffix}"
        run_cli(
            [
                "export",
                selection.session_id,
                "--project",
                selection.project_path,
                "--format",
                output_format,
                "--output",
                str(output_path),
            ],
            label=f"claude-history export {session_label} --project {project_label} --format {output_format}",
        )
        require_file(output_path, f"export {output_format}")
        if output_format == "json":
            exported = json.loads(output_path.read_text(encoding="utf-8"))
            require(exported["session_id"] == selection.session_id, "export json session_id mismatch")
            require(len(exported["messages"]) >= selection.message_count, "export json lost messages")

    for output_format in ("text", "markdown"):
        for scope, args in (
            ("global", []),
            ("project", ["--project", selection.project_path]),
        ):
            output_path = workdir / f"summary-{scope}-{output_format}.out"
            run_cli(
                ["summary", *args, "--format", output_format, "--output", str(output_path)],
                label=f"claude-history summary {scope} --format {output_format}",
            )
            require_file(output_path, f"summary {scope} {output_format}")

    for output_format in ("brief", "detailed", "timeline"):
        for scope, args in (
            ("global", []),
            ("project", ["--project", selection.project_path]),
        ):
            output_path = workdir / f"story-{scope}-{output_format}.out"
            run_cli(
                ["story", *args, "--format", output_format, "--output", str(output_path)],
                label=f"claude-history story {scope} --format {output_format}",
            )
            require_file(output_path, f"story {scope} {output_format}")


def check_wrapped(selection: CorpusSelection) -> None:
    raw = run_cli(
        ["wrapped", "--year", str(selection.wrapped_year), "--name", "Local Smoke", "--raw"],
        label="claude-history wrapped --year <selected-year> --raw",
        timeout=120,
    )
    require("Error:" not in raw, "wrapped --raw reported an error")
    story = json.loads(raw)
    require(story["y"] == selection.wrapped_year, "wrapped raw year mismatch")
    require(story["s"] >= 1, "wrapped raw did not include sessions")

    url_output = run_cli(
        ["wrapped", "--year", str(selection.wrapped_year), "--name", "Local Smoke", "--no-copy"],
        label="claude-history wrapped --year <selected-year> --no-copy",
        timeout=120,
    )
    require("Error:" not in url_output, "wrapped URL generation reported an error")
    match = re.search(r"https://[^\s]+/wrapped\?d=([A-Za-z0-9_-]+)", url_output)
    require(match is not None, "wrapped output did not include a share URL")
    encoded = match.group(1)
    url = match.group(0)

    for decode_arg, label in ((url, "wrapped --decode <url>"), (encoded, "wrapped --decode <encoded>")):
        decoded = run_cli(["wrapped", "--decode", decode_arg], label=f"claude-history {label}")
        require("Failed to decode" not in decoded and "Error:" not in decoded, f"{label} failed")
        require(str(selection.wrapped_year) in decoded, f"{label} did not show the selected year")


def run_check(name: str, func: Callable[[], None], timings: list[tuple[str, float]]) -> None:
    start = time.perf_counter()
    func()
    elapsed = time.perf_counter() - start
    timings.append((name, elapsed))
    print(f"✓ {name} ({elapsed:.2f}s)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Keep temporary export/summary/story artifacts for manual inspection.",
    )
    args = parser.parse_args()

    print("Local Claude corpus smoke test")
    selection = select_corpus()
    print(
        "Corpus: "
        f"{selection.project_count} project(s), "
        f"{selection.session_count} session file(s); "
        f"selected 1 session with {selection.message_count} message(s); "
        f"Wrapped year {selection.wrapped_year}."
    )

    timings: list[tuple[str, float]] = []
    temp_context = tempfile.TemporaryDirectory(prefix="claude-history-local-smoke-")
    try:
        workdir = Path(temp_context.name)
        run_check("help, version, and examples", check_cli_help_and_examples, timings)
        run_check("discovery and stats", lambda: check_discovery_and_stats(selection), timings)
        run_check("sessions, show, and search", lambda: check_session_browsing_and_search(selection), timings)
        run_check(
            "export, summary, and story outputs",
            lambda: check_exports_summaries_and_stories(selection, workdir),
            timings,
        )
        run_check("wrapped generate/decode", lambda: check_wrapped(selection), timings)
    except SmokeFailure as exc:
        print(f"✗ smoke test failed: {exc}", file=sys.stderr)
        if args.keep_artifacts:
            print(f"Artifacts kept at: {temp_context.name}", file=sys.stderr)
        else:
            temp_context.cleanup()
        return 1
    except Exception as exc:  # pragma: no cover - defensive script boundary
        print(f"✗ unexpected smoke test error: {type(exc).__name__}: {exc}", file=sys.stderr)
        if args.keep_artifacts:
            print(f"Artifacts kept at: {temp_context.name}", file=sys.stderr)
        else:
            temp_context.cleanup()
        return 1

    if args.keep_artifacts:
        print(f"Artifacts kept at: {temp_context.name}")
    else:
        temp_context.cleanup()

    total = sum(elapsed for _, elapsed in timings)
    print(f"All {len(timings)} smoke-test groups passed in {total:.2f}s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
