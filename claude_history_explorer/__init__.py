"""Claude Code History Explorer - Explore your Claude Code conversation history.

This package provides tools to analyze and explore Claude Code conversation
history stored in ~/.claude/projects/.

Modules:
    models: Data classes for messages, sessions, projects, and statistics
    utils: Utility functions for formatting and classification
    projects: Project discovery and listing
    parser: JSONL session file parsing
    stats: Statistics calculation
    stories: Narrative generation
    wrapped: V3 wrapped format for visualizations
    cli: Command-line interface

Example:
    >>> from claude_history_explorer import list_projects, parse_session
    >>> projects = list_projects()
    >>> for p in projects[:5]:
    ...     print(f"{p.short_name}: {p.session_count} sessions")
"""

__version__ = "0.2.1"

# Re-export commonly used symbols for convenience
from .history import (
    # Data models
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
    calculate_global_stats,
    # Statistics functions
    calculate_project_stats,
    classify,
    decode_wrapped_story_v3,
    encode_wrapped_story_v3,
    find_project,
    # Helper functions
    format_duration,
    format_timestamp,
    generate_global_story,
    # Story functions
    generate_project_story,
    # V3 Wrapped functions
    generate_wrapped_story_v3,
    # Path functions
    get_claude_dir,
    get_projects_dir,
    get_session_by_id,
    # Core functions
    list_projects,
    parse_session,
    search_sessions,
)

__all__ = [
    "GlobalStats",
    "GlobalStory",
    # Data models
    "Message",
    "Project",
    "ProjectStats",
    "ProjectStatsV3",
    "ProjectStory",
    "Session",
    "SessionInfo",
    "SessionInfoV3",
    "TokenUsage",
    "WrappedStoryV3",
    # Version
    "__version__",
    "calculate_global_stats",
    # Statistics functions
    "calculate_project_stats",
    "classify",
    "decode_wrapped_story_v3",
    "encode_wrapped_story_v3",
    "find_project",
    # Helper functions
    "format_duration",
    "format_timestamp",
    "generate_global_story",
    # Story functions
    "generate_project_story",
    # V3 Wrapped functions
    "generate_wrapped_story_v3",
    # Path functions
    "get_claude_dir",
    "get_projects_dir",
    "get_session_by_id",
    # Core functions
    "list_projects",
    "parse_session",
    "search_sessions",
]
