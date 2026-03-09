"""Frequency analysis for Claude Code conversation history.

Scans sessions and tallies repeated user prompts and Bash commands.
Reports facts (count, project spread). Does not classify or recommend.

Public API:
    compute_frequency(project, limit, min_count, min_length) -> FrequencyResult

See docs/FREQUENCY_SPEC.md for the full specification.
"""

import os
import re
import shlex
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional, Protocol

from .models import Project
from .parser import parse_session
from .projects import list_projects, find_project
from .stemmer import stem


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class FrequencyEntry:
    """A single row in the frequency table.

    Attributes:
        normalised: Canonical form displayed to the user
        count: Total occurrences across all matched sessions
        project_spread: Distinct projects this pattern appears in
        projects: Project paths (for drill-down / JSON output)
        examples: 2-3 raw (pre-normalisation) strings for context
    """

    normalised: str
    count: int
    project_spread: int
    projects: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


@dataclass
class FrequencyResult:
    """Complete output of a frequency analysis.

    Attributes:
        prompt_entries: Ranked by count descending
        bash_entries: Ranked by count descending
        project_path: None for global analysis, project path when scoped
    """

    prompt_entries: list[FrequencyEntry] = field(default_factory=list)
    bash_entries: list[FrequencyEntry] = field(default_factory=list)
    project_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Prompt normalisation
# ---------------------------------------------------------------------------

FILLER_PREFIXES = [
    "can you ",
    "could you ",
    "would you ",
    "please ",
    "go ahead and ",
    "now ",
    "ok ",
    "okay ",
    "also ",
    "then ",
    "next ",
    "hey ",
    "hi ",
    "so ",
]

STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "this",
        "that",
        "these",
        "those",
        "my",
        "your",
        "its",
        "our",
        "their",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "for",
        "to",
        "in",
        "on",
        "of",
        "and",
        "or",
        "i",
        "me",
        "we",
        "us",
        "do",
        "does",
        "did",
        "all",
        "any",
        "some",
        "just",
        "only",
        "so",
        "if",
        "but",
        "not",
        "no",
        "up",
        "out",
        "about",
        "make",
        "sure",
    }
)


def _extract_instruction(text: str) -> str:
    """Pull out the actionable first sentence/line.

    Most user prompts are an instruction followed by context (error traces,
    code blocks, file contents). The repeated part is the instruction.
    """
    # If it has a code fence, only keep what's before it
    fence = text.find("```")
    if fence > 0:
        text = text[:fence]

    # Take the first line if multi-line
    first_line = text.split("\n")[0].strip()

    # If the first line is very long, it's probably pasted content
    if len(first_line) > 150:
        m = re.match(r"^(.+?[.!?])\s", first_line)
        if m:
            return m.group(1)
        return first_line[:150]

    return first_line


def _clean_prompt(text: str) -> str:
    """Deterministic text cleanup: lowercase, collapse whitespace, strip filler."""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.strip("?.!,;:")

    # Iteratively strip filler prefixes until stable
    changed = True
    while changed:
        changed = False
        for prefix in FILLER_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix) :]
                changed = True
    return text.strip()


def _remove_stopwords(text: str) -> str:
    """Remove common English stopwords. Never returns empty."""
    tokens = text.split()
    kept = [t for t in tokens if t not in STOPWORDS]
    return " ".join(kept) if kept else text


def _stem_tokens(text: str) -> str:
    """Apply Porter stemming to each token."""
    return " ".join(stem(t) for t in text.split())


def normalise_prompt(text: str) -> str:
    """Full prompt normalisation pipeline.

    Pass 1: First-sentence extraction
    Pass 2: Deterministic text cleanup
    Pass 3: Stopword removal + Porter stemming

    Args:
        text: Raw user prompt

    Returns:
        Normalised canonical form (used as grouping key)
    """
    text = _extract_instruction(text)
    text = _clean_prompt(text)
    text = _remove_stopwords(text)
    text = _stem_tokens(text)
    return text


# ---------------------------------------------------------------------------
# Bash normalisation
# ---------------------------------------------------------------------------

# How many subcommand tokens to keep after the binary name
SUBCOMMAND_DEPTH = {
    "git": 1,
    "npm": 2,
    "npx": 1,
    "yarn": 2,
    "pnpm": 2,
    "cargo": 1,
    "docker": 1,
    "docker-compose": 1,
    "kubectl": 1,
    "python": 1,
    "go": 1,
    "make": 1,
    "gh": 2,
}


def _normalise_single_command(cmd: str) -> str:
    """Normalise a single command (no pipes, no &&/;)."""
    cmd = cmd.strip()
    if not cmd:
        return ""

    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()

    if not tokens:
        return ""

    binary = os.path.basename(tokens[0])
    rest = tokens[1:]

    # Special case: export FOO=value → export FOO=... (truncate secrets)
    if binary == "export" and rest:
        parts = []
        for token in rest:
            if "=" in token:
                var_name = token.split("=", 1)[0]
                parts.append(f"{var_name}=...")
            else:
                parts.append(token)
        return f"export {' '.join(parts)}"

    # Special case: python -m <module>
    if binary == "python" and len(rest) >= 2 and rest[0] == "-m":
        return f"python -m {rest[1]}"

    depth = SUBCOMMAND_DEPTH.get(binary, 0)
    subcmd_tokens = []
    for token in rest[:depth]:
        if token.startswith("-"):
            break
        subcmd_tokens.append(token)

    if subcmd_tokens:
        return f"{binary} {' '.join(subcmd_tokens)}"
    return binary


def normalise_bash(command: str) -> list[str]:
    """Normalise a Bash command, splitting compound commands.

    Splits on && and ; (each segment → separate frequency entry).
    Pipes are kept together (a pipeline is one operation).

    Args:
        command: Raw Bash command string

    Returns:
        List of normalised command segments
    """
    # Split on && and ; (not inside quotes — good enough for common cases)
    segments = re.split(r"\s*(?:&&|;)\s*", command)

    results = []
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        if "|" in segment:
            pipe_parts = segment.split("|")
            normalised_parts = [_normalise_single_command(p) for p in pipe_parts]
            normalised_parts = [p for p in normalised_parts if p]
            if normalised_parts:
                results.append(" | ".join(normalised_parts))
        else:
            normalised = _normalise_single_command(segment)
            if normalised:
                results.append(normalised)

    return results


# ---------------------------------------------------------------------------
# Similarity merge
# ---------------------------------------------------------------------------


class SimilarityMerger(Protocol):
    """Protocol for pluggable similarity merge strategies.

    Implementations must merge similar keys in a Counter and return:
    - The merged counter
    - A mapping from every original key to its canonical (surviving) key
    """

    def merge(
        self,
        counter: Counter,
        threshold: float,
    ) -> tuple[Counter, dict[str, str]]:
        """Merge similar keys in counter.

        Args:
            counter: Keys are normalised strings, values are counts
            threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            merged_counter: New counter with merged keys
            canonical_for: Mapping from original key to canonical key
        """
        ...


class SequenceMatcherMerger:
    """Merge similar keys using difflib.SequenceMatcher.

    O(n^2) on number of distinct keys. Fine for n < 100.
    """

    def merge(
        self,
        counter: Counter,
        threshold: float = 0.75,
    ) -> tuple[Counter, dict[str, str]]:
        # Sort keys by count descending so the highest-count key becomes canonical
        keys = sorted(counter.keys(), key=lambda k: counter[k], reverse=True)
        merged: dict[str, int] = {}
        canonical_for: dict[str, str] = {}

        for key in keys:
            best_match = None
            best_ratio = -1.0
            for canon in merged:
                ratio = SequenceMatcher(None, key, canon).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = canon
            if best_match and best_ratio >= threshold:
                merged[best_match] += counter[key]
                canonical_for[key] = best_match
            else:
                merged[key] = counter[key]
                canonical_for[key] = key

        return Counter(merged), canonical_for


# Default merger instance
_default_merger = SequenceMatcherMerger()


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def compute_frequency(
    project: Optional[str] = None,
    limit: int = 20,
    min_count: int = 3,
    min_length: int = 4,
    merger: Optional[SimilarityMerger] = None,
    merge_threshold: float = 0.75,
) -> FrequencyResult:
    """Walk sessions, tally prompts and bash commands, return ranked results.

    Args:
        project: Project search string (partial match), or None for global
        limit: Maximum entries per table
        min_count: Minimum occurrences to include
        min_length: Minimum prompt character length (filters "y", "ok")
        merger: Similarity merge strategy (default: SequenceMatcherMerger)
        merge_threshold: Threshold for similarity merge (0.0 to 1.0)

    Returns:
        FrequencyResult with prompt_entries and bash_entries, ranked by count

    Raises:
        ValueError: If project is specified but not found
    """
    if merger is None:
        merger = _default_merger

    # Resolve project scope
    resolved_project = None
    if project:
        resolved_project = find_project(project)
        if not resolved_project:
            raise ValueError(f"No project found matching '{project}'")
        projects = [resolved_project]
    else:
        projects = list_projects()

    if not projects:
        return FrequencyResult(
            project_path=resolved_project.path if resolved_project else None,
        )

    # Accumulators
    prompt_counter: Counter = Counter()
    prompt_projects: dict[str, set[str]] = {}
    prompt_examples: dict[str, list[str]] = {}

    bash_counter: Counter = Counter()
    bash_projects: dict[str, set[str]] = {}
    bash_examples: dict[str, list[str]] = {}

    # Walk all sessions
    for proj in projects:
        for session_file in proj.session_files:
            session = parse_session(session_file, proj.path)

            for msg in session.messages:
                if msg.role == "user" and msg.content:
                    raw = msg.content.strip()
                    if len(raw) < min_length:
                        continue

                    key = normalise_prompt(raw)
                    if not key:
                        continue

                    prompt_counter[key] += 1
                    prompt_projects.setdefault(key, set()).add(proj.path)
                    examples = prompt_examples.setdefault(key, [])
                    # Store first line of raw as example (not the full paste)
                    raw_first_line = raw.split("\n")[0][:200]
                    if len(examples) < 3 and raw_first_line not in examples:
                        examples.append(raw_first_line)

                elif msg.role == "assistant":
                    for tool_use in msg.tool_uses:
                        if tool_use.get("name") != "Bash":
                            continue
                        command = tool_use.get("input", {}).get("command", "")
                        if not command.strip():
                            continue

                        raw_cmd = command.strip()
                        for normalised_cmd in normalise_bash(raw_cmd):
                            bash_counter[normalised_cmd] += 1
                            bash_projects.setdefault(normalised_cmd, set()).add(
                                proj.path
                            )
                            examples = bash_examples.setdefault(normalised_cmd, [])
                            if len(examples) < 3 and raw_cmd not in examples:
                                examples.append(raw_cmd[:200])

    # Filter by min_count before merge (reduces merge cost)
    prompt_counter = Counter(
        {k: v for k, v in prompt_counter.items() if v >= min_count}
    )
    bash_counter = Counter(
        {k: v for k, v in bash_counter.items() if v >= min_count}
    )

    # Merge similar prompts (not Bash — structural decomposition is enough)
    merged_prompt_counter, prompt_canonical = merger.merge(
        prompt_counter, merge_threshold
    )

    # Rebuild project sets and examples after merge
    merged_prompt_projects: dict[str, set[str]] = {}
    merged_prompt_examples: dict[str, list[str]] = {}
    for original_key, canonical_key in prompt_canonical.items():
        projects_set = merged_prompt_projects.setdefault(canonical_key, set())
        projects_set.update(prompt_projects.get(original_key, set()))

        examples_list = merged_prompt_examples.setdefault(canonical_key, [])
        for ex in prompt_examples.get(original_key, []):
            if len(examples_list) < 3 and ex not in examples_list:
                examples_list.append(ex)

    # Build entries
    prompt_entries = _build_entries(
        merged_prompt_counter, merged_prompt_projects, merged_prompt_examples, limit
    )
    bash_entries = _build_entries(
        bash_counter, bash_projects, bash_examples, limit
    )

    return FrequencyResult(
        prompt_entries=prompt_entries,
        bash_entries=bash_entries,
        project_path=resolved_project.path if resolved_project else None,
    )


def _build_entries(
    counter: Counter,
    projects_map: dict[str, set[str]],
    examples_map: dict[str, list[str]],
    limit: int,
) -> list[FrequencyEntry]:
    """Build sorted FrequencyEntry list from counter data."""
    # Sort by count desc, then project_spread desc
    ranked = sorted(
        counter.items(),
        key=lambda item: (item[1], len(projects_map.get(item[0], set()))),
        reverse=True,
    )[:limit]

    entries = []
    for key, count in ranked:
        proj_set = projects_map.get(key, set())
        entries.append(
            FrequencyEntry(
                normalised=key,
                count=count,
                project_spread=len(proj_set),
                projects=sorted(proj_set),
                examples=examples_map.get(key, []),
            )
        )

    return entries
