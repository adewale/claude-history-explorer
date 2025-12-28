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

Example:
    >>> from claude_history_explorer.history import list_projects, parse_session
    >>> projects = list_projects()
    >>> for project in projects:
    ...     print(f"{project.path}: {project.session_count} sessions")
"""

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
