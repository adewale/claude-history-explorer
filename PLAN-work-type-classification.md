# Work Type Classification - Implementation Plan

## Overview

Add work type classification as an **opt-in feature** triggered by a new CLI command.
Do NOT modify Wrapped. Keep it simple and focused.

---

## Design Principles

| Principle | Rationale |
|-----------|-----------|
| **Project-level classification** | Projects ARE the natural unit; paths encode intent |
| **Path patterns only** | More reliable than keyword matching on message content |
| **6 categories (not 9)** | Simpler, less overlap, clearer meaning |
| **Opt-in via CLI command** | Don't clutter existing commands; users trigger when wanted |
| **Reuse existing structures** | Add to `ProjectStats`, don't create parallel classes |
| **Salvage PR #4 value** | Extract file patterns, names, formatting; discard keywords |

---

## Categories (Consolidated from PR #4's 9 → 6)

```
coding      → "Software Development" (default)
writing     → "Writing & Documentation"
analysis    → "Data Analysis"
research    → "Research & Literature"
teaching    → "Teaching & Grading"
design      → "Design & UX"
```

**Removed categories:**
- `research_tooling` → merged into `coding`
- `admin` → too rare, merged into `other`
- `communication` → too rare, merged into `writing`
- `planning` → too generic ("plan" matches "explanation"), merged into `coding`

---

## File Changes

### 1. Delete: `claude_history_explorer/work_classifier.py` (348 lines)

Remove the orphaned module entirely. We're replacing it with ~60 lines integrated
into existing modules.

### 2. Delete: `tests/test_work_classifier.py` (414 lines)

Replace with focused tests for the new implementation.

### 3. Modify: `claude_history_explorer/history.py`

Add approximately 60 lines:

```python
# =============================================================================
# Work Type Classification
# =============================================================================

# Pattern Design Principles:
# 1. Extensions use $ anchor: r"\.tex$" (matches end of path)
# 2. Directories use enclosing slashes: r"/papers?/" (avoids partial matches)
# 3. Terminal directories use (?:/|$): r"/thesis(?:/|$)" (matches /thesis or /thesis/)
# 4. All patterns are matched case-insensitively

WORK_TYPE_PATTERNS = {
    "writing": [
        # File extensions (anchored at end)
        r"\.tex$", r"\.md$", r"\.docx?$", r"\.rst$", r"\.txt$",
        # Directory patterns (enclosed or terminal)
        r"/papers?/", r"/docs?/", r"/documentation/",
        r"/thesis(?:/|$)", r"/dissertation(?:/|$)",
        r"/manuscripts?(?:/|$)", r"/proposals?(?:/|$)", r"/drafts?(?:/|$)",
        r"/writing(?:/|$)", r"/book(?:/|$)", r"/chapter(?:/|$)",
    ],
    "analysis": [
        # File extensions
        r"\.csv$", r"\.xlsx?$", r"\.ipynb$", r"\.r$", r"\.rmd$",
        r"\.parquet$", r"\.feather$", r"\.sav$",  # Data formats
        # Directory patterns
        r"/data/", r"/datasets?/", r"/analysis/", r"/analytics/",
        r"/results?/", r"/notebooks?/", r"/jupyter/",
        r"/statistics?(?:/|$)", r"/viz(?:/|$)", r"/visuali[sz]ations?(?:/|$)",
    ],
    "research": [
        # File extensions
        r"\.bib$", r"\.ris$", r"\.enw$",  # Bibliography formats
        # Directory patterns
        r"/research/", r"/literature/", r"/lit[-_]?review/",
        r"/bibliography(?:/|$)", r"/references(?:/|$)", r"/sources(?:/|$)",
        r"/reading(?:/|$)", r"/papers[-_]to[-_]read(?:/|$)",
    ],
    "teaching": [
        # Directory patterns (no common file extensions)
        r"/courses?/", r"/class(?:es)?/", r"/teaching/",
        r"/grading(?:/|$)", r"/assignments?(?:/|$)", r"/homework(?:/|$)",
        r"/syllabus(?:/|$)", r"/syllabi(?:/|$)",
        r"/students?(?:/|$)", r"/rubrics?(?:/|$)", r"/lectures?(?:/|$)",
        r"/exams?(?:/|$)", r"/quizzes?(?:/|$)",
    ],
    "design": [
        # File extensions
        r"\.fig$", r"\.sketch$", r"\.xd$", r"\.psd$", r"\.ai$",
        r"\.svg$", r"\.figma$",
        # Directory patterns
        r"/design/", r"/designs/", r"/ui/", r"/ux/",
        r"/mockups?(?:/|$)", r"/wireframes?(?:/|$)", r"/prototypes?(?:/|$)",
        r"/assets(?:/|$)", r"/icons(?:/|$)", r"/illustrations?(?:/|$)",
    ],
    # Note: "coding" has no patterns - it's the default for Claude Code
}

WORK_TYPE_INFO = {
    "coding": {
        "name": "Software Development",
        "description": "Coding, debugging, infrastructure",
    },
    "writing": {
        "name": "Writing & Documentation",
        "description": "Papers, proposals, documentation",
    },
    "analysis": {
        "name": "Data Analysis",
        "description": "Statistics, data processing, visualization",
    },
    "research": {
        "name": "Research & Literature",
        "description": "Literature review, reading, synthesis",
    },
    "teaching": {
        "name": "Teaching & Grading",
        "description": "Course materials, grading, feedback",
    },
    "design": {
        "name": "Design & UX",
        "description": "UI/UX design, mockups, wireframes",
    },
}


def classify_project(path: str) -> str:
    """Classify a project by its path.

    Uses file patterns to determine work type. Returns 'coding' as default
    since this is Claude Code.

    Args:
        path: Project path (e.g., "/Users/me/papers/thesis")

    Returns:
        Work type ID: 'coding', 'writing', 'analysis', 'research', or 'teaching'
    """
    path_lower = path.lower()
    for work_type, patterns in WORK_TYPE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, path_lower, re.IGNORECASE):
                return work_type
    return "coding"


def get_work_type_name(work_type: str) -> str:
    """Get human-readable name for a work type."""
    return WORK_TYPE_INFO.get(work_type, {}).get("name", work_type.title())
```

Add `work_type` field to `ProjectStats`:

```python
@dataclass
class ProjectStats:
    project: Project
    total_sessions: int
    total_messages: int
    total_user_messages: int
    total_duration_minutes: int
    agent_sessions: int
    main_sessions: int
    total_size_bytes: int
    avg_messages_per_session: float
    longest_session_duration: str
    most_recent_session: Optional[datetime]
    work_type: str = "coding"  # ← ADD THIS
```

Modify `calculate_project_stats()` to set work_type:

```python
def calculate_project_stats(project: Project) -> ProjectStats:
    # ... existing code ...
    return ProjectStats(
        project=project,
        # ... existing fields ...
        work_type=classify_project(project.path),  # ← ADD THIS
    )
```

Add `__all__` exports:

```python
__all__ = [
    # ... existing ...
    "classify_project",
    "get_work_type_name",
    "WORK_TYPE_INFO",
]
```

### 4. Modify: `claude_history_explorer/cli.py`

Add new `worktype` command (~80 lines):

```python
@main.command()
@click.option(
    "--project", "-p", default=None,
    help="Show work type for specific project only"
)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["table", "json", "chart"]),
    default="chart",
    help="Output format"
)
@click.option("--example", is_flag=True, help="Show usage examples")
def worktype(project: str, output_format: str, example: bool):
    """Analyze work type distribution across projects.

    Classifies projects into work types based on their paths:
    - Software Development (coding, debugging)
    - Writing & Documentation (papers, docs)
    - Data Analysis (notebooks, data processing)
    - Research & Literature (literature review)
    - Teaching & Grading (courses, assignments)
    """
    if example:
        show_examples("worktype")
        return

    from .history import (
        calculate_global_stats,
        classify_project,
        get_work_type_name,
        WORK_TYPE_INFO,
    )

    stats = calculate_global_stats(project)

    # Aggregate by work type
    by_type = defaultdict(lambda: {"hours": 0, "messages": 0, "projects": 0})

    for project_stats in stats.projects:
        wt = project_stats.work_type
        by_type[wt]["hours"] += project_stats.total_duration_minutes / 60
        by_type[wt]["messages"] += project_stats.total_messages
        by_type[wt]["projects"] += 1

    total_hours = sum(d["hours"] for d in by_type.values())

    if output_format == "json":
        # JSON output
        output = {
            "total_hours": round(total_hours, 1),
            "breakdown": {
                wt: {
                    "name": get_work_type_name(wt),
                    "hours": round(d["hours"], 1),
                    "percentage": round(100 * d["hours"] / total_hours, 1) if total_hours else 0,
                    "messages": d["messages"],
                    "projects": d["projects"],
                }
                for wt, d in by_type.items()
            }
        }
        console.print_json(data=output)

    elif output_format == "table":
        # Table output
        table = Table(title="Work Type Distribution")
        table.add_column("Work Type", style="cyan")
        table.add_column("Hours", justify="right")
        table.add_column("Percentage", justify="right")
        table.add_column("Projects", justify="right")

        for wt, d in sorted(by_type.items(), key=lambda x: x[1]["hours"], reverse=True):
            pct = 100 * d["hours"] / total_hours if total_hours else 0
            table.add_row(
                get_work_type_name(wt),
                f"{d['hours']:.1f}h",
                f"{pct:.1f}%",
                str(d["projects"]),
            )

        console.print(table)

    else:  # chart (default)
        # ASCII bar chart
        console.print("\n[bold]Work Type Distribution[/bold]")
        console.print("=" * 55)
        console.print()

        sorted_types = sorted(by_type.items(), key=lambda x: x[1]["hours"], reverse=True)

        for wt, d in sorted_types:
            pct = 100 * d["hours"] / total_hours if total_hours else 0
            if pct < 1:
                continue
            bar_len = int(pct / 5)  # 20 chars max
            bar = "█" * bar_len + "░" * (20 - bar_len)
            name = get_work_type_name(wt)
            console.print(f"{name:<24} {bar} {d['hours']:>6.1f}h ({pct:>4.1f}%)")

        console.print()
        console.print(f"[dim]Total: {total_hours:.1f} hours across {len(stats.projects)} projects[/dim]")
```

Add to `stats` command as optional flag:

```python
@main.command()
@click.option("--by-worktype", is_flag=True, help="Group statistics by work type")
# ... existing options ...
def stats(project: str, output_format: str, by_worktype: bool, example: bool):
    # ... existing code ...

    if by_worktype:
        # Show work type breakdown
        # (Similar logic to worktype command but integrated)
```

### 5. Add: `tests/test_work_type.py` (~50 lines)

```python
"""Tests for work type classification."""

import pytest
from claude_history_explorer.history import (
    classify_project,
    get_work_type_name,
    WORK_TYPE_PATTERNS,
    WORK_TYPE_INFO,
)


class TestClassifyProject:
    """Test project classification by path."""

    # === Positive tests: paths that SHOULD match ===

    def test_papers_directory_is_writing(self):
        assert classify_project("/Users/me/papers/thesis") == "writing"

    def test_tex_extension_is_writing(self):
        assert classify_project("/project/paper.tex") == "writing"

    def test_docs_directory_is_writing(self):
        assert classify_project("/Users/me/docs/manual") == "writing"

    def test_terminal_thesis_is_writing(self):
        # Terminal directory without trailing slash
        assert classify_project("/Users/me/thesis") == "writing"
        assert classify_project("/Users/me/thesis/") == "writing"

    def test_data_directory_is_analysis(self):
        assert classify_project("/Users/me/data/experiment") == "analysis"

    def test_ipynb_extension_is_analysis(self):
        assert classify_project("/project/notebook.ipynb") == "analysis"

    def test_csv_extension_is_analysis(self):
        assert classify_project("/project/results.csv") == "analysis"

    def test_research_directory_is_research(self):
        assert classify_project("/Users/me/research/lit-review") == "research"

    def test_bib_extension_is_research(self):
        assert classify_project("/project/references.bib") == "research"

    def test_course_directory_is_teaching(self):
        assert classify_project("/Users/me/courses/cs101") == "teaching"

    def test_grading_directory_is_teaching(self):
        assert classify_project("/work/grading/hw1") == "teaching"

    def test_design_directory_is_design(self):
        assert classify_project("/Users/me/design/app-mockups") == "design"

    def test_figma_extension_is_design(self):
        assert classify_project("/project/components.fig") == "design"

    def test_ui_directory_is_design(self):
        assert classify_project("/Users/me/ui/dashboard") == "design"

    def test_default_is_coding(self):
        assert classify_project("/Users/me/code/myapp") == "coding"
        assert classify_project("/random/project") == "coding"
        assert classify_project("/src/main.py") == "coding"

    def test_case_insensitive(self):
        assert classify_project("/PAPERS/THESIS") == "writing"
        assert classify_project("/Data/Results") == "analysis"

    # === Negative tests: paths that should NOT false-positive ===

    def test_no_false_positive_on_partial_match(self):
        # "thesis" should not match inside "synthesis"
        assert classify_project("/Users/me/synthesis-project") == "coding"
        # "data" should not match inside "metadata"
        assert classify_project("/Users/me/metadata-service") == "coding"
        # "draft" should not match inside "craftsman"
        assert classify_project("/Users/me/craftsman-tools") == "coding"

    def test_no_false_positive_on_extension_substring(self):
        # ".tex" should not match ".texture" or ".text"
        assert classify_project("/project/file.texture") == "coding"
        # ".csv" should not match ".csvx"
        assert classify_project("/project/file.csvx") == "coding"

    def test_mid_path_requires_slashes(self):
        # "/data/" requires slashes on both sides for mid-path
        assert classify_project("/mydata/project") == "coding"  # no leading slash before "data"
        assert classify_project("/project/database") == "coding"  # "data" is substring


class TestWorkTypeInfo:
    """Test work type metadata."""

    def test_all_types_have_info(self):
        for work_type in ["coding", "writing", "analysis", "research", "teaching", "design"]:
            assert work_type in WORK_TYPE_INFO
            assert "name" in WORK_TYPE_INFO[work_type]
            assert "description" in WORK_TYPE_INFO[work_type]

    def test_get_work_type_name(self):
        assert get_work_type_name("coding") == "Software Development"
        assert get_work_type_name("writing") == "Writing & Documentation"
        assert get_work_type_name("unknown") == "Unknown"  # Fallback
```

---

## CLI Examples

After implementation, users can run:

```bash
# Show work type distribution (default chart view)
claude-history worktype

# Output:
# Work Type Distribution
# =======================================================
#
# Software Development     ████████████████████  156.3h (78.2%)
# Writing & Documentation  ████░░░░░░░░░░░░░░░░   28.4h (14.2%)
# Data Analysis            ██░░░░░░░░░░░░░░░░░░   12.1h ( 6.1%)
# Research & Literature    █░░░░░░░░░░░░░░░░░░░    3.0h ( 1.5%)
#
# Total: 199.8 hours across 23 projects


# Show as table
claude-history worktype --format table

# Show as JSON
claude-history worktype --format json

# Show for specific project
claude-history worktype --project thesis

# Show stats grouped by work type
claude-history stats --by-worktype
```

---

## What We Salvage from PR #4

| Component | Action | Lines Saved |
|-----------|--------|-------------|
| File patterns | Extract & consolidate (9→5 categories) | ~30 |
| Category names & descriptions | Keep verbatim | ~15 |
| Bar chart format | Adapt for Rich console | ~15 |
| Test patterns | Rewrite for path-based tests | ~0 (rewritten) |

| Component | Action | Lines Removed |
|-----------|--------|---------------|
| Keyword lists | Discard | -85 |
| `classify_text()` | Discard | -20 |
| `score_session()` | Discard | -25 |
| `classify_session()` | Discard | -30 |
| `classify_session_proportional()` | Discard | -20 |
| `WorkBreakdown` class | Discard | -50 |
| Keyword-based tests | Discard | -300 |

**Net change: Remove 762 lines, add ~190 lines = -572 lines (75% reduction)**

---

## Implementation Order

1. **Delete orphaned files**
   - Remove `work_classifier.py`
   - Remove `test_work_classifier.py`

2. **Add classification to history.py**
   - Add `WORK_TYPE_PATTERNS` dict
   - Add `WORK_TYPE_INFO` dict
   - Add `classify_project()` function
   - Add `get_work_type_name()` function
   - Add `work_type` field to `ProjectStats`
   - Update `calculate_project_stats()` to set `work_type`

3. **Add CLI command**
   - Add `worktype` command to cli.py
   - Add `--by-worktype` flag to `stats` command

4. **Add tests**
   - Create `test_work_type.py` with path-based tests

5. **Update documentation**
   - Add examples to FAQ or README

---

## Extensibility: Adding or Removing Work Types

The design makes work types easy to modify. All definitions live in two adjacent dicts
in `history.py`:

### To Add a New Work Type

1. **Add patterns to `WORK_TYPE_PATTERNS`:**
```python
WORK_TYPE_PATTERNS = {
    # ... existing types ...
    "design": [
        r"\.fig$", r"\.sketch$", r"\.xd$",  # Design file extensions
        r"/design/", r"/ui/", r"/ux/",       # Directory patterns
        r"/mockups?(?:/|$)", r"/wireframes?(?:/|$)",
    ],
}
```

2. **Add metadata to `WORK_TYPE_INFO`:**
```python
WORK_TYPE_INFO = {
    # ... existing types ...
    "design": {
        "name": "Design & UX",
        "description": "UI/UX design, mockups, wireframes",
    },
}
```

3. **No other changes needed.** The CLI command and stats integration automatically
   pick up new types because they iterate over `WORK_TYPE_INFO.keys()`.

### To Remove a Work Type

1. **Delete the entry from `WORK_TYPE_PATTERNS`**
2. **Delete the entry from `WORK_TYPE_INFO`**
3. **Projects that matched the removed type will now classify as `coding` (default)**

No migration needed - classification is computed on-the-fly, not stored.

### To Rename a Work Type

1. **Change the key in both dicts** (e.g., `"writing"` → `"docs"`)
2. **Update the `name` in `WORK_TYPE_INFO`** for display

### Future: User-Defined Work Types

If users want custom types, we could later add:

```python
# ~/.claude/work_types.json (future feature)
{
    "custom_types": {
        "client_work": {
            "name": "Client Projects",
            "description": "Billable client work",
            "patterns": ["/clients?/", "/billable/"]
        }
    },
    "overrides": {
        "/Users/me/secret-project": "research"  # Force classification
    }
}
```

This would be loaded and merged with built-in types. **Not in scope for this plan**
but the architecture supports it.

### Pattern Guidelines for New Types

| Pattern Type | Format | Example | Matches |
|--------------|--------|---------|---------|
| File extension | `r"\.ext$"` | `r"\.tex$"` | `/foo/paper.tex` |
| Mid-path directory | `r"/dirname/"` | `r"/data/"` | `/foo/data/bar` |
| Terminal directory | `r"/dirname(?:/\|$)"` | `r"/thesis(?:/\|$)"` | `/foo/thesis` or `/foo/thesis/` |
| Optional plural | `r"/names?/"` | `r"/papers?/"` | `/paper/` or `/papers/` |
| Variant spellings | `r"/visuali[sz]e/"` | - | US and UK spelling |

### Testing New Patterns

Add tests to `test_work_type.py`:

```python
def test_new_design_type(self):
    assert classify_project("/Users/me/design/app-mockups") == "design"
    assert classify_project("/project/wireframes") == "design"
    assert classify_project("/ui/components.fig") == "design"
```

---

## What We DON'T Do

- ❌ Modify Wrapped
- ❌ Session-level classification
- ❌ Keyword matching on message content
- ❌ Proportional classification
- ❌ Create separate dataclasses
- ❌ Create standalone module

---

## Summary

| Metric | Before (PR #4) | After (This Plan) |
|--------|---------------|-------------------|
| Lines of code | 762 | ~190 |
| Categories | 9 (overlapping) | 6 (distinct) |
| Classification level | Session | Project |
| Primary signal | Keywords (unreliable) | Path patterns (reliable) |
| Integration | Orphaned | Integrated into history.py + CLI |
| User trigger | None (not integrated) | `worktype` command |
| Wrapped changes | N/A | None |
