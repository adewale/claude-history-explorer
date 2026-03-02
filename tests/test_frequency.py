"""Comprehensive tests for the frequency analysis feature.

Organised in four layers:
1. Prompt normalisation unit tests
2. Bash normalisation unit tests
3. Similarity merge tests (SequenceMatcher, with abstraction for future swap)
4. Integration tests (compute_frequency + CLI)

Run with: uv run pytest tests/test_frequency.py -v
"""

import json
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from claude_history_explorer.cli import main
from claude_history_explorer.frequency import (
    FrequencyEntry,
    FrequencyResult,
    SequenceMatcherMerger,
    SimilarityMerger,
    _clean_prompt,
    _extract_instruction,
    _normalise_single_command,
    _remove_stopwords,
    _stem_tokens,
    compute_frequency,
    normalise_bash,
    normalise_prompt,
)
from claude_history_explorer.models import Message, Project, Session


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


def _make_session(
    messages_data: list[dict],
    project_path: str = "/Users/test/myproject",
    session_id: str = "test-session",
) -> Session:
    """Build a Session from simplified message specs.

    Each dict in messages_data can have:
        role: "user" or "assistant"
        content: str (for user messages)
        bash: str (for assistant messages with Bash tool use)
    """
    messages = []
    for i, md in enumerate(messages_data):
        role = md.get("role", "user")
        # Spread timestamps across hours/minutes to avoid minute overflow
        hour = 10 + (i // 60)
        minute = i % 60
        if role == "user":
            messages.append(
                Message(
                    role="user",
                    content=md.get("content", ""),
                    timestamp=datetime(2025, 12, 15, hour, minute),
                )
            )
        elif role == "assistant":
            tool_uses = []
            if "bash" in md:
                tool_uses.append(
                    {"name": "Bash", "input": {"command": md["bash"]}}
                )
            messages.append(
                Message(
                    role="assistant",
                    content=md.get("content", ""),
                    timestamp=datetime(2025, 12, 15, hour, minute),
                    tool_uses=tool_uses,
                )
            )

    return Session(
        session_id=session_id,
        project_path=project_path,
        file_path=Path(f"/mock/{session_id}.jsonl"),
        messages=messages,
        start_time=datetime(2025, 12, 15, 10, 0),
        end_time=datetime(2025, 12, 15, 10 + (len(messages) // 60), len(messages) % 60),
    )


def _make_mock_project(
    name: str = "-Users-test-myproject",
    path: str = "/Users/test/myproject",
    session_files: list[Path] | None = None,
) -> MagicMock:
    """Create a mock Project."""
    project = MagicMock(spec=Project)
    project.name = name
    project.path = path
    project.short_name = path.split("/")[-1]
    project.dir_path = Path(f"/mock/.claude/projects/{name}")
    project.session_files = session_files or []
    project.session_count = len(project.session_files)
    return project


# =============================================================================
# Prompt normalisation: Pass 1 — First-sentence extraction
# =============================================================================


class TestExtractInstruction:
    """Pass 1: extract the actionable first sentence/line."""

    def test_single_line(self):
        assert _extract_instruction("run the tests") == "run the tests"

    def test_multiline_keeps_first(self):
        text = "run the tests\nhere is some context\nmore context"
        assert _extract_instruction(text) == "run the tests"

    def test_code_fence_stripped(self):
        text = "fix this error\n```\nTraceback (most recent call last):\n  ...\n```"
        assert _extract_instruction(text) == "fix this error"

    def test_code_fence_at_start_kept(self):
        # Fence at position 0 → don't strip (nothing before it)
        text = "```\nsome code\n```"
        assert _extract_instruction(text) == "```"

    def test_long_line_truncated(self):
        long_text = "x" * 200
        assert len(_extract_instruction(long_text)) == 150

    def test_long_line_with_sentence(self):
        long_text = "Fix the bug. " + "x" * 200
        assert _extract_instruction(long_text) == "Fix the bug."

    def test_empty(self):
        assert _extract_instruction("") == ""

    def test_whitespace_only(self):
        assert _extract_instruction("   \n   ") == ""


# =============================================================================
# Prompt normalisation: Pass 2 — Deterministic text cleanup
# =============================================================================


class TestCleanPrompt:
    """Pass 2: lowercase, collapse whitespace, strip filler."""

    def test_lowercase(self):
        assert _clean_prompt("Run The Tests") == "run the tests"

    def test_collapse_whitespace(self):
        assert _clean_prompt("run   the    tests") == "run the tests"

    def test_strip_trailing_punctuation(self):
        assert _clean_prompt("run the tests?") == "run the tests"
        assert _clean_prompt("run the tests!") == "run the tests"
        assert _clean_prompt("run the tests...") == "run the tests"

    def test_strip_single_prefix(self):
        assert _clean_prompt("please run the tests") == "run the tests"

    def test_strip_nested_prefixes(self):
        assert _clean_prompt("ok now please run the tests") == "run the tests"

    def test_strip_all_filler_prefixes(self):
        for prefix in [
            "can you ", "could you ", "would you ", "please ",
            "go ahead and ", "now ", "ok ", "okay ",
            "also ", "then ", "next ", "hey ", "hi ", "so ",
        ]:
            result = _clean_prompt(f"{prefix}run the tests")
            assert result == "run the tests", f"Failed for prefix: {prefix!r}"

    def test_multiple_filler_layers(self):
        assert _clean_prompt("hey can you please run the tests") == "run the tests"

    def test_empty(self):
        assert _clean_prompt("") == ""

    def test_only_punctuation(self):
        assert _clean_prompt("???") == ""


# =============================================================================
# Prompt normalisation: Pass 3 — Stopword removal + stemming
# =============================================================================


class TestRemoveStopwords:
    """Stopword removal — never returns empty."""

    def test_removes_stopwords(self):
        assert _remove_stopwords("run the tests") == "run tests"

    def test_preserves_content_words(self):
        assert _remove_stopwords("fix lint errors") == "fix lint errors"

    def test_all_stopwords(self):
        # When ALL words are stopwords, return original
        assert _remove_stopwords("do it") == "do it"

    def test_mixed(self):
        assert _remove_stopwords("make sure the tests pass") == "tests pass"

    def test_empty(self):
        assert _remove_stopwords("") == ""


class TestStemTokens:
    """Porter stemming applied to each token."""

    def test_running(self):
        assert _stem_tokens("running") == "run"

    def test_tests(self):
        assert _stem_tokens("tests") == "test"

    def test_multiple_tokens(self):
        assert _stem_tokens("running tests") == "run test"

    def test_already_stemmed(self):
        assert _stem_tokens("run test") == "run test"

    def test_empty(self):
        assert _stem_tokens("") == ""


# =============================================================================
# Prompt normalisation: Full pipeline
# =============================================================================


class TestNormalisePrompt:
    """End-to-end prompt normalisation."""

    def test_basic(self):
        assert normalise_prompt("run the tests") == "run test"

    def test_filler_and_case(self):
        assert normalise_prompt("Can you please run the tests?") == "run test"

    def test_nested_filler(self):
        assert normalise_prompt("ok now please run the tests") == "run test"

    def test_multiline_with_code(self):
        text = "run the tests\n```\nERROR: test_foo failed\n```"
        assert normalise_prompt(text) == "run test"

    def test_fix_lint_errors(self):
        assert normalise_prompt("fix the lint errors") == "fix lint error"

    def test_commit_and_push(self):
        assert normalise_prompt("commit and push") == "commit push"

    def test_review_this_pr(self):
        # "review" stems to "review", "pr" stays as "pr"
        result = normalise_prompt("review this PR")
        assert "review" in result

    def test_different_phrasings_same_result(self):
        """Variants of the same intent should normalise identically."""
        variants = [
            "run the tests",
            "Run tests",
            "can you run the tests?",
            "please run the tests",
            "ok run tests",
        ]
        results = {normalise_prompt(v) for v in variants}
        assert len(results) == 1, f"Got different results: {results}"

    def test_deploying_variants(self):
        variants = [
            "deploy the application",
            "deploying the application",
        ]
        results = {normalise_prompt(v) for v in variants}
        assert len(results) == 1, f"Got different results: {results}"


# =============================================================================
# Bash normalisation: single command
# =============================================================================


class TestNormaliseSingleCommand:
    """Test structural decomposition of individual commands."""

    def test_git_subcommand(self):
        assert _normalise_single_command("git diff --staged src/foo.py") == "git diff"

    def test_npm_two_levels(self):
        assert _normalise_single_command("npm run test --verbose") == "npm run test"

    def test_npm_run_build(self):
        assert _normalise_single_command("npm run build") == "npm run build"

    def test_python_m(self):
        assert _normalise_single_command("python -m pytest tests/") == "python -m pytest"

    def test_cargo(self):
        assert _normalise_single_command("cargo test -- --nocapture") == "cargo test"

    def test_docker(self):
        assert _normalise_single_command("docker build -t myimg .") == "docker build"

    def test_gh_two_levels(self):
        assert _normalise_single_command("gh pr create --title t") == "gh pr create"

    def test_make(self):
        assert _normalise_single_command("make build") == "make build"

    def test_unknown_binary(self):
        # Not in the depth table → binary name only
        assert _normalise_single_command("eslint --fix src/") == "eslint"

    def test_full_path_stripped(self):
        assert _normalise_single_command("/usr/local/bin/git diff") == "git diff"

    def test_empty(self):
        assert _normalise_single_command("") == ""

    def test_whitespace_only(self):
        assert _normalise_single_command("   ") == ""

    def test_flag_stops_subcommand(self):
        # "git -c core.autocrlf=true commit" — flag before subcommand
        result = _normalise_single_command("git -c core.autocrlf=true commit")
        assert result == "git"

    def test_shlex_failure_fallback(self):
        # Unbalanced quotes — should fall back to .split()
        result = _normalise_single_command("echo 'unbalanced")
        assert result == "echo"


# =============================================================================
# Bash normalisation: compound commands
# =============================================================================


class TestNormaliseBash:
    """Test compound command splitting and pipeline handling."""

    def test_single_command(self):
        # npm has depth 2, so "npm test" keeps the subcommand
        assert normalise_bash("npm test") == ["npm test"]

    def test_and_chain(self):
        assert normalise_bash("git add . && git commit -m 'fix'") == [
            "git add",
            "git commit",
        ]

    def test_semicolon_chain(self):
        assert normalise_bash("cd /tmp; ls -la") == ["cd", "ls"]

    def test_pipeline_kept_together(self):
        assert normalise_bash("grep error log.txt | wc -l") == ["grep | wc"]

    def test_mixed_chain_and_pipe(self):
        result = normalise_bash("grep foo | wc -l && echo done")
        assert result == ["grep | wc", "echo"]

    def test_empty(self):
        assert normalise_bash("") == []

    def test_whitespace_only(self):
        assert normalise_bash("   ") == []

    def test_complex_real_world(self):
        result = normalise_bash(
            "cd /home/user/project && npm run test && npm run build"
        )
        assert result == ["cd", "npm run test", "npm run build"]


# =============================================================================
# Similarity merge: SequenceMatcherMerger
# =============================================================================


class TestSequenceMatcherMerger:
    """Test the default similarity merge implementation.

    Written to be agnostic of the specific algorithm so they also serve as
    a spec for any future SimilarityMerger implementation (e.g., character
    n-gram Jaccard).
    """

    def setup_method(self):
        self.merger = SequenceMatcherMerger()

    def test_merge_identical_keys(self):
        """Identical keys should remain as one entry."""
        c = Counter({"fix build": 10})
        merged, canonical = self.merger.merge(c, threshold=0.75)
        assert len(merged) == 1
        assert merged["fix build"] == 10
        assert canonical["fix build"] == "fix build"

    def test_merge_similar_keys(self):
        """Similar keys (above threshold) should be merged."""
        # ratio("fix build error", "fix build errors") ≈ 0.97
        c = Counter({"fix build error": 5, "fix build errors": 3})
        merged, canonical = self.merger.merge(c, threshold=0.75)
        assert len(merged) == 1
        total = sum(merged.values())
        assert total == 8

    def test_no_merge_dissimilar_keys(self):
        """Dissimilar keys (below threshold) should stay separate."""
        c = Counter({"run test": 5, "fix lint": 3})
        merged, canonical = self.merger.merge(c, threshold=0.75)
        assert len(merged) == 2
        assert merged["run test"] == 5
        assert merged["fix lint"] == 3

    def test_higher_count_becomes_canonical(self):
        """The key with the higher count should become the canonical form."""
        c = Counter({"run test": 10, "run tests": 3})
        merged, canonical = self.merger.merge(c, threshold=0.75)
        # "run test" has higher count, so it should be canonical
        assert canonical["run tests"] == "run test"

    def test_canonical_mapping_complete(self):
        """Every original key should appear in the canonical_for mapping."""
        c = Counter({"a b c": 5, "x y z": 3, "a b d": 2})
        merged, canonical = self.merger.merge(c, threshold=0.75)
        assert set(canonical.keys()) == {"a b c", "x y z", "a b d"}

    def test_empty_counter(self):
        """Empty counter should produce empty results."""
        c = Counter()
        merged, canonical = self.merger.merge(c, threshold=0.75)
        assert len(merged) == 0
        assert len(canonical) == 0

    def test_single_entry(self):
        """Single entry should pass through unchanged."""
        c = Counter({"run test": 5})
        merged, canonical = self.merger.merge(c, threshold=0.75)
        assert len(merged) == 1
        assert merged["run test"] == 5

    def test_threshold_0_merges_everything(self):
        """Threshold 0 should merge all keys into one."""
        c = Counter({"abc": 5, "xyz": 3})
        merged, canonical = self.merger.merge(c, threshold=0.0)
        assert len(merged) == 1

    def test_threshold_1_merges_nothing(self):
        """Threshold 1.0 should merge nothing (only exact matches)."""
        c = Counter({"run test": 5, "run tests": 3})
        merged, canonical = self.merger.merge(c, threshold=1.0)
        assert len(merged) == 2

    # --- Properties that any SimilarityMerger must satisfy ---

    def test_count_conservation(self):
        """Total count must be preserved after merge."""
        c = Counter({"fix build error": 5, "fix build failur": 3, "run test": 10})
        original_total = sum(c.values())
        merged, _ = self.merger.merge(c, threshold=0.75)
        assert sum(merged.values()) == original_total

    def test_merged_count_never_exceeds_original_total(self):
        """No single merged entry can exceed the original total."""
        c = Counter({"a": 5, "b": 3, "c": 2})
        merged, _ = self.merger.merge(c, threshold=0.0)
        original_total = sum(c.values())
        for count in merged.values():
            assert count <= original_total

    def test_deterministic(self):
        """Same input should always produce the same output."""
        c = Counter({"fix error": 5, "fix failur": 3, "run test": 10})
        result1 = self.merger.merge(c, threshold=0.75)
        result2 = self.merger.merge(c, threshold=0.75)
        assert result1[0] == result2[0]
        assert result1[1] == result2[1]


# =============================================================================
# Integration: compute_frequency
# =============================================================================


class TestComputeFrequency:
    """Test the full computation pipeline with mocked session data."""

    def _mock_parse_session(self, sessions_by_path):
        """Return a parse_session function that returns pre-built sessions."""

        def parse_fn(file_path, project_path=""):
            return sessions_by_path.get(str(file_path), _make_session([]))

        return parse_fn

    def test_basic_prompt_counting(self):
        """Prompts repeated >= min_count should appear in results."""
        session = _make_session(
            [
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
            ]
        )

        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )

        with (
            patch("claude_history_explorer.frequency.list_projects", return_value=[project]),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(min_count=2)

        assert len(result.prompt_entries) >= 1
        entry = result.prompt_entries[0]
        assert entry.count == 3
        assert entry.normalised == "run test"

    def test_basic_bash_counting(self):
        """Bash commands repeated >= min_count should appear in results."""
        session = _make_session(
            [
                {"role": "assistant", "bash": "npm test"},
                {"role": "assistant", "bash": "npm test"},
                {"role": "assistant", "bash": "npm test"},
            ]
        )

        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )

        with (
            patch("claude_history_explorer.frequency.list_projects", return_value=[project]),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(min_count=2)

        assert len(result.bash_entries) >= 1
        entry = result.bash_entries[0]
        assert entry.count == 3
        assert entry.normalised == "npm test"

    def test_min_count_filter(self):
        """Entries below min_count should be excluded."""
        session = _make_session(
            [
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "fix the bug"},
                {"role": "assistant", "content": "ok"},
            ]
        )

        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )

        with (
            patch("claude_history_explorer.frequency.list_projects", return_value=[project]),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(min_count=2)

        # Each prompt appears only once — both should be filtered
        assert len(result.prompt_entries) == 0

    def test_min_length_filter(self):
        """Short prompts below min_length should be excluded."""
        session = _make_session(
            [
                {"role": "user", "content": "y"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "y"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "y"},
                {"role": "assistant", "content": "ok"},
            ]
        )

        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )

        with (
            patch("claude_history_explorer.frequency.list_projects", return_value=[project]),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(min_count=1, min_length=4)

        assert len(result.prompt_entries) == 0

    def test_project_spread(self):
        """project_spread should reflect distinct projects."""
        session_a = _make_session(
            [
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
            ],
            project_path="/project/a",
        )
        session_b = _make_session(
            [
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
            ],
            project_path="/project/b",
        )

        project_a = _make_mock_project(
            name="-project-a",
            path="/project/a",
            session_files=[Path("/mock/sa.jsonl")],
        )
        project_b = _make_mock_project(
            name="-project-b",
            path="/project/b",
            session_files=[Path("/mock/sb.jsonl")],
        )

        sessions = {
            "/mock/sa.jsonl": session_a,
            "/mock/sb.jsonl": session_b,
        }

        def mock_parse(file_path, project_path=""):
            return sessions[str(file_path)]

        with (
            patch(
                "claude_history_explorer.frequency.list_projects",
                return_value=[project_a, project_b],
            ),
            patch(
                "claude_history_explorer.frequency.parse_session",
                side_effect=mock_parse,
            ),
        ):
            result = compute_frequency(min_count=2)

        assert len(result.prompt_entries) >= 1
        assert result.prompt_entries[0].project_spread == 2

    def test_compound_bash_split(self):
        """&& chains should produce separate entries."""
        session = _make_session(
            [
                {"role": "assistant", "bash": "git add . && git commit -m 'fix'"},
                {"role": "assistant", "bash": "git add . && git commit -m 'feat'"},
                {"role": "assistant", "bash": "git add . && git commit -m 'chore'"},
            ]
        )

        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )

        with (
            patch("claude_history_explorer.frequency.list_projects", return_value=[project]),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(min_count=2)

        normalised_cmds = {e.normalised for e in result.bash_entries}
        assert "git add" in normalised_cmds
        assert "git commit" in normalised_cmds

    def test_no_sessions_empty_result(self):
        """No projects should produce empty but valid result."""
        with patch("claude_history_explorer.frequency.list_projects", return_value=[]):
            result = compute_frequency()

        assert len(result.prompt_entries) == 0
        assert len(result.bash_entries) == 0

    def test_examples_populated(self):
        """Examples should contain raw pre-normalisation strings."""
        session = _make_session(
            [
                {"role": "user", "content": "Run the tests"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "run tests please"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "Can you run the tests?"},
                {"role": "assistant", "content": "ok"},
            ]
        )

        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )

        with (
            patch("claude_history_explorer.frequency.list_projects", return_value=[project]),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(min_count=2)

        assert len(result.prompt_entries) >= 1
        entry = result.prompt_entries[0]
        assert len(entry.examples) >= 1
        # Examples should be raw strings, not normalised
        assert any("test" in ex.lower() for ex in entry.examples)

    def test_limit_respected(self):
        """Output should respect the limit parameter."""
        messages = []
        for i in range(30):
            messages.append({"role": "user", "content": f"do thing {i}"})
            messages.append({"role": "assistant", "content": "ok"})
            messages.append({"role": "user", "content": f"do thing {i}"})
            messages.append({"role": "assistant", "content": "ok"})
            messages.append({"role": "user", "content": f"do thing {i}"})
            messages.append({"role": "assistant", "content": "ok"})

        session = _make_session(messages)
        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )

        with (
            patch("claude_history_explorer.frequency.list_projects", return_value=[project]),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(limit=5, min_count=2)

        assert len(result.prompt_entries) <= 5

    def test_project_scope(self):
        """When project is specified, result.project_path should be set."""
        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )
        session = _make_session([], project_path="/Users/test/myproject")

        with (
            patch(
                "claude_history_explorer.frequency.find_project",
                return_value=project,
            ),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(project="myproject", min_count=1)

        assert result.project_path == "/Users/test/myproject"

    def test_project_not_found_raises(self):
        """Unknown project should raise ValueError."""
        with patch(
            "claude_history_explorer.frequency.find_project",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="No project found"):
                compute_frequency(project="nonexistent")

    def test_sorted_by_count(self):
        """Entries should be sorted by count descending."""
        session = _make_session(
            [
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "run the tests"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "fix the bug"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "fix the bug"},
                {"role": "assistant", "content": "ok"},
            ]
        )

        project = _make_mock_project(
            session_files=[Path("/mock/s1.jsonl")]
        )

        with (
            patch("claude_history_explorer.frequency.list_projects", return_value=[project]),
            patch(
                "claude_history_explorer.frequency.parse_session",
                return_value=session,
            ),
        ):
            result = compute_frequency(min_count=2)

        counts = [e.count for e in result.prompt_entries]
        assert counts == sorted(counts, reverse=True)


# =============================================================================
# CLI integration
# =============================================================================


class TestFrequencyCLI:
    """Test the `frequency` CLI command."""

    def test_table_output(self, runner):
        """Table output should include expected headers."""
        mock_result = FrequencyResult(
            prompt_entries=[
                FrequencyEntry(
                    normalised="run test",
                    count=47,
                    project_spread=12,
                    projects=["/p1", "/p2"],
                    examples=["run the tests"],
                ),
            ],
            bash_entries=[
                FrequencyEntry(
                    normalised="npm run test",
                    count=30,
                    project_spread=5,
                    projects=["/p1"],
                    examples=["npm run test --verbose"],
                ),
            ],
        )

        with patch(
            "claude_history_explorer.cli.compute_frequency",
            return_value=mock_result,
        ):
            result = runner.invoke(main, ["frequency"])
            assert result.exit_code == 0
            assert "run test" in result.output
            assert "47" in result.output
            assert "npm run test" in result.output

    def test_json_output(self, runner):
        """JSON output should be valid and contain expected fields."""
        mock_result = FrequencyResult(
            prompt_entries=[
                FrequencyEntry(
                    normalised="run test",
                    count=10,
                    project_spread=3,
                    projects=["/p1", "/p2", "/p3"],
                    examples=["run the tests", "Run tests"],
                ),
            ],
            bash_entries=[],
        )

        with patch(
            "claude_history_explorer.cli.compute_frequency",
            return_value=mock_result,
        ):
            result = runner.invoke(main, ["frequency", "-f", "json"])
            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "prompts" in data
            assert "commands" in data
            assert data["prompts"][0]["normalised"] == "run test"
            assert data["prompts"][0]["count"] == 10
            assert len(data["prompts"][0]["examples"]) == 2

    def test_empty_results(self, runner):
        """Empty results should show informational message."""
        mock_result = FrequencyResult()

        with patch(
            "claude_history_explorer.cli.compute_frequency",
            return_value=mock_result,
        ):
            result = runner.invoke(main, ["frequency"])
            assert result.exit_code == 0
            assert "No repeated patterns" in result.output

    def test_project_scope(self, runner):
        """--project flag should be passed through."""
        mock_result = FrequencyResult(
            project_path="/Users/test/myproject",
            prompt_entries=[
                FrequencyEntry(
                    normalised="run test",
                    count=5,
                    project_spread=1,
                    projects=["/Users/test/myproject"],
                    examples=["run the tests"],
                ),
            ],
        )

        with patch(
            "claude_history_explorer.cli.compute_frequency",
            return_value=mock_result,
        ) as mock_fn:
            result = runner.invoke(main, ["frequency", "-p", "myproject"])
            assert result.exit_code == 0
            mock_fn.assert_called_once_with(
                project="myproject",
                limit=20,
                min_count=3,
                min_length=4,
            )

    def test_project_not_found(self, runner):
        """Unknown project should show error message."""
        with patch(
            "claude_history_explorer.cli.compute_frequency",
            side_effect=ValueError("No project found matching 'nonexistent'"),
        ):
            result = runner.invoke(main, ["frequency", "-p", "nonexistent"])
            assert result.exit_code == 0  # Click doesn't set exit code for handled errors
            assert "No project found" in result.output

    def test_scoped_view_no_projects_column(self, runner):
        """When scoped to a project, the Projects column should not appear."""
        mock_result = FrequencyResult(
            project_path="/Users/test/myproject",
            prompt_entries=[
                FrequencyEntry(
                    normalised="run test",
                    count=5,
                    project_spread=1,
                    projects=["/Users/test/myproject"],
                    examples=["run the tests"],
                ),
            ],
        )

        with patch(
            "claude_history_explorer.cli.compute_frequency",
            return_value=mock_result,
        ):
            result = runner.invoke(main, ["frequency", "-p", "myproject"])
            assert result.exit_code == 0
            assert "run test" in result.output
            # Check that the project path appears in the title (scoped view)
            assert "/Users/test/myproject" in result.output

    def test_custom_limit(self, runner):
        """--limit should be passed through."""
        mock_result = FrequencyResult()

        with patch(
            "claude_history_explorer.cli.compute_frequency",
            return_value=mock_result,
        ) as mock_fn:
            runner.invoke(main, ["frequency", "-n", "5"])
            mock_fn.assert_called_once_with(
                project=None,
                limit=5,
                min_count=3,
                min_length=4,
            )

    def test_custom_min_count(self, runner):
        """--min-count should be passed through."""
        mock_result = FrequencyResult()

        with patch(
            "claude_history_explorer.cli.compute_frequency",
            return_value=mock_result,
        ) as mock_fn:
            runner.invoke(main, ["frequency", "--min-count", "10"])
            mock_fn.assert_called_once_with(
                project=None,
                limit=20,
                min_count=10,
                min_length=4,
            )
