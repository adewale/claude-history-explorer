"""Core module for reading and parsing Claude Code history files.

This module provides the data models and functions for accessing Claude Code
conversation history stored in ~/.claude/projects/. It is read-only and never
modifies any files.

This module re-exports all public symbols from the split modules for backward
compatibility. New code should import directly from the specific modules.

Data Models:
    Message: A single message (user or assistant) in a conversation
    Session: A complete conversation session with metadata
    Project: A Claude Code project with its sessions
    ProjectStats: Statistics for a single project
    GlobalStats: Aggregated statistics across all projects
    ProjectStory: Narrative analysis of a project's development

Key Functions:
    list_projects(): Discover all projects
    find_project(search): Find a project by partial path match
    parse_session(file_path): Parse a JSONL session file
    get_session_by_id(session_id): Retrieve a specific session
    search_sessions(pattern): Search across all conversations
    calculate_project_stats(project): Generate project statistics
    calculate_global_stats(): Generate global statistics
    generate_project_story(project): Generate narrative insights
    classify_project(path): Classify a project by work type

Example:
    >>> from claude_history_explorer.history import list_projects, parse_session
    >>> projects = list_projects()
    >>> for project in projects:
    ...     print(f"{project.path}: {project.session_count} sessions")
"""

import re

# Re-export all public symbols for backward compatibility

# Models
from .models import (
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

# Parser functions
from .parser import get_session_by_id, parse_session, search_sessions

# Project discovery
from .projects import find_project, get_claude_dir, get_projects_dir, list_projects

# Statistics
from .stats import calculate_global_stats, calculate_project_stats

# Stories
from .stories import generate_global_story, generate_project_story

# Utilities
from .utils import (
    _active_duration_minutes,
    _compile_regex_safe,
    classify,
    format_duration,
    format_timestamp,
)

# Wrapped V3
from .wrapped import (
    # Constants
    AGENT_RATIO_BUCKETS,
    EVENT_TYPE_INDICES,
    HEATMAP_QUANT_SCALE,
    MAX_COOCCURRENCE_EDGES,
    MAX_PROJECTS,
    MAX_SESSION_FINGERPRINTS,
    MAX_TIMELINE_EVENTS,
    MESSAGE_LENGTH_BUCKETS,
    SESSION_DURATION_BUCKETS,
    # Functions
    compute_activity_heatmap,
    compute_agent_ratio_distribution,
    compute_distribution,
    compute_message_length_distribution,
    compute_project_cooccurrence,
    compute_session_duration_distribution,
    compute_session_fingerprint,
    compute_streak_stats,
    compute_trait_scores,
    decode_wrapped_story_v3,
    detect_timeline_events,
    encode_wrapped_story_v3,
    generate_wrapped_story_v3,
    get_top_session_fingerprints,
    quantize_heatmap,
    rle_decode,
    rle_encode,
    rle_encode_if_smaller,
)


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
        Work type ID: 'coding', 'writing', 'analysis', 'research', 'teaching', or 'design'
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

__all__ = [
    # Data models
    "Message",
    "Session",
    "SessionInfo",
    "SessionInfoV3",
    "Project",
    "ProjectStats",
    "ProjectStatsV3",
    "GlobalStats",
    "ProjectStory",
    "GlobalStory",
    "TokenUsage",
    "WrappedStoryV3",
    # Path functions
    "get_claude_dir",
    "get_projects_dir",
    # Helper functions
    "format_duration",
    "format_timestamp",
    "classify",
    "_active_duration_minutes",
    "_compile_regex_safe",
    # Core functions
    "list_projects",
    "find_project",
    "parse_session",
    "search_sessions",
    "get_session_by_id",
    # Statistics functions
    "calculate_project_stats",
    "calculate_global_stats",
    # Story functions
    "generate_project_story",
    "generate_global_story",
    # Work type classification
    "classify_project",
    "get_work_type_name",
    "WORK_TYPE_PATTERNS",
    "WORK_TYPE_INFO",
    # V3 Wrapped functions
    "generate_wrapped_story_v3",
    "encode_wrapped_story_v3",
    "decode_wrapped_story_v3",
    # V3 Compute functions
    "compute_activity_heatmap",
    "compute_distribution",
    "compute_session_duration_distribution",
    "compute_agent_ratio_distribution",
    "compute_message_length_distribution",
    "compute_trait_scores",
    "compute_project_cooccurrence",
    "detect_timeline_events",
    "compute_session_fingerprint",
    "get_top_session_fingerprints",
    "compute_streak_stats",
    "quantize_heatmap",
    # V3 Encoding
    "rle_encode",
    "rle_decode",
    "rle_encode_if_smaller",
    # V3 Constants
    "AGENT_RATIO_BUCKETS",
    "EVENT_TYPE_INDICES",
    "HEATMAP_QUANT_SCALE",
    "MAX_COOCCURRENCE_EDGES",
    "MAX_PROJECTS",
    "MAX_SESSION_FINGERPRINTS",
    "MAX_TIMELINE_EVENTS",
    "MESSAGE_LENGTH_BUCKETS",
    "SESSION_DURATION_BUCKETS",
]
