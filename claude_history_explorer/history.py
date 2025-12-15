"""Core module for reading and parsing Claude Code history files.

This module provides the data models and functions for accessing Claude Code
conversation history stored in ~/.claude/projects/. It is read-only and never
modifies any files.

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

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from bisect import bisect_right
from typing import Any, Callable, Iterator, Optional, Dict, List, Set, Tuple

from .constants import (
    MESSAGE_RATE_HIGH,
    MESSAGE_RATE_MEDIUM,
    MESSAGE_RATE_LOW,
    SESSION_LENGTH_LONG,
    SESSION_LENGTH_EXTENDED,
    SESSION_LENGTH_STANDARD,
    AGENT_RATIO_HIGH,
    AGENT_RATIO_BALANCED,
    ACTIVITY_INTENSITY_HIGH,
    ACTIVITY_INTENSITY_MEDIUM,
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
    "WrappedStoryV3",
    "ThreadNode",
    "ThreadMap",
    "ThreadMapStats",
    # Path functions
    "get_claude_dir",
    "get_projects_dir",
    # Helper functions
    "format_duration",
    "duration_minutes",
    "format_timestamp",
    "classify",
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
    # V3 Encoding
    "rle_encode",
    "rle_decode",
    "rle_encode_if_smaller",
    # Thread map functions
    "build_thread_map",
    "encode_thread_map",
    "decode_thread_map",
    "THREAD_MAP_PATTERNS",
]


def format_duration(minutes: int) -> str:
    """Format a duration in minutes as a human-readable string.

    Args:
        minutes: Duration in minutes

    Returns:
        Formatted string like "45m" or "2h 30m"

    Example:
        >>> format_duration(90)
        '1h 30m'
        >>> format_duration(45)
        '45m'
    """
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def duration_minutes(start: datetime, end: datetime) -> int:
    """Calculate duration in minutes between two datetimes.

    Args:
        start: Start datetime
        end: End datetime

    Returns:
        Duration in minutes

    Example:
        >>> from datetime import datetime, timedelta
        >>> start = datetime.now()
        >>> end = start + timedelta(hours=2, minutes=30)
        >>> duration_minutes(start, end)
        150
    """
    return int((end - start).total_seconds() / 60)


def format_timestamp(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format a datetime with a default pattern.

    Args:
        dt: Datetime to format (None returns "unknown")
        fmt: Format string (default: "%Y-%m-%d %H:%M")

    Returns:
        Formatted string or "unknown" if dt is None

    Example:
        >>> from datetime import datetime
        >>> dt = datetime(2024, 1, 15, 14, 30)
        >>> format_timestamp(dt)
        '2024-01-15 14:30'
    """
    return dt.strftime(fmt) if dt else "unknown"


def classify(value: float, thresholds: list[tuple[float, str]], default: str) -> str:
    """Classify a value into a category based on thresholds.

    Thresholds are checked in order; the first threshold exceeded returns
    the corresponding label.

    Args:
        value: The value to classify
        thresholds: List of (threshold, label) tuples, checked in order
        default: Label to return if no threshold is exceeded

    Returns:
        The label for the matching threshold, or default

    Example:
        >>> classify(25, [(30, "high"), (20, "medium"), (10, "low")], "minimal")
        'medium'
    """
    for threshold, label in thresholds:
        if value > threshold:
            return label
    return default


def get_claude_dir() -> Path:
    """Get the Claude Code data directory.

    Returns:
        Path to ~/.claude directory
    """
    return Path.home() / ".claude"


def get_projects_dir() -> Path:
    """Get the projects directory where conversation history is stored.

    Returns:
        Path to ~/.claude/projects directory
    """
    return get_claude_dir() / "projects"


@dataclass
class TokenUsage:
    """Token usage statistics for an assistant message.

    Attributes:
        input_tokens: Tokens in the input/prompt
        output_tokens: Tokens in the response
        cache_creation_tokens: Tokens used to create cache
        cache_read_tokens: Tokens read from cache
        model: Model identifier (e.g., "claude-opus-4-5-20251101")
    """
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        """Total tokens (input + output)."""
        return self.input_tokens + self.output_tokens

    @classmethod
    def from_message_data(cls, message_data: dict) -> Optional["TokenUsage"]:
        """Extract token usage from assistant message data."""
        usage = message_data.get("usage", {})
        if not usage:
            return None

        return cls(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            model=message_data.get("model", ""),
        )


@dataclass
class Message:
    """A single message in a conversation.

    Attributes:
        role: Either 'user' or 'assistant'
        content: The text content of the message
        timestamp: When the message was sent (may be None)
        tool_uses: List of tools used by assistant (name and input)
        token_usage: Token usage stats (assistant messages only)

    Example:
        >>> msg = Message(role="user", content="Hello")
        >>> msg.role
        'user'
    """

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[datetime] = None
    tool_uses: list = field(default_factory=list)
    token_usage: Optional[TokenUsage] = None

    @classmethod
    def from_json(cls, data: dict) -> Optional["Message"]:
        """Parse a message from JSONL data.

        Args:
            data: Dictionary from a JSONL line

        Returns:
            Message object or None if the data is not a valid message
        """
        msg_type = data.get("type")

        if msg_type not in ("user", "assistant"):
            return None

        role = msg_type
        content_parts = []
        tool_uses = []

        message_data = data.get("message", {})
        content_list = message_data.get("content", [])

        if isinstance(content_list, str):
            content_parts.append(content_list)
        elif isinstance(content_list, list):
            for item in content_list:
                if isinstance(item, str):
                    content_parts.append(item)
                elif isinstance(item, dict):
                    if item.get("type") == "text":
                        content_parts.append(item.get("text", ""))
                    elif item.get("type") == "tool_use":
                        tool_uses.append(
                            {
                                "name": item.get("name", "unknown"),
                                "input": item.get("input", {}),
                            }
                        )
                    # tool_result types are intentionally skipped

        # Handle direct user messages
        if role == "user" and not content_parts:
            direct_content = message_data.get("content")
            if isinstance(direct_content, str):
                content_parts.append(direct_content)

        timestamp = None
        if "timestamp" in data:
            try:
                timestamp = datetime.fromisoformat(
                    data["timestamp"].replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                pass

        content = "\n".join(content_parts).strip()

        # Skip empty messages and tool result messages
        if not content and not tool_uses:
            return None

        # Extract token usage for assistant messages
        token_usage = None
        if role == "assistant":
            token_usage = TokenUsage.from_message_data(message_data)

        return cls(role=role, content=content, timestamp=timestamp, tool_uses=tool_uses, token_usage=token_usage)


@dataclass
class Session:
    """A conversation session containing messages and metadata.

    Attributes:
        session_id: Unique identifier (filename without .jsonl)
        project_path: Decoded path to the project
        file_path: Path to the JSONL file
        messages: List of Message objects
        start_time: Timestamp of first message
        end_time: Timestamp of last message
        slug: Optional session slug/title

    Properties:
        message_count: Total number of messages
        user_message_count: Number of user messages
        duration_str: Human-readable duration (e.g., "2h 30m")
    """

    session_id: str
    project_path: str
    file_path: Path
    messages: list[Message] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    slug: Optional[str] = None

    @property
    def message_count(self) -> int:
        """Total number of messages in the session."""
        return len(self.messages)

    @property
    def user_message_count(self) -> int:
        """Number of messages from the user."""
        return len([m for m in self.messages if m.role == "user"])

    @property
    def duration_str(self) -> str:
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            minutes = int(delta.total_seconds() / 60)
            return format_duration(minutes)
        return "unknown"


@dataclass
class Project:
    """A Claude Code project with its session files.

    Attributes:
        name: Encoded directory name (e.g., "-Users-foo-myproject")
        path: Decoded project path (e.g., "/Users/foo/myproject")
        dir_path: Path to the project directory in ~/.claude/projects/
        session_files: List of JSONL files, sorted by modification time

    Properties:
        session_count: Number of sessions in this project
        last_modified: Timestamp of most recent session

    Example:
        >>> project = Project.from_dir(Path("~/.claude/projects/-Users-foo-bar"))
        >>> project.path
        '/Users/foo/bar'
    """

    name: str
    path: str
    dir_path: Path
    session_files: list[Path] = field(default_factory=list)

    @classmethod
    def from_dir(cls, dir_path: Path) -> "Project":
        """Create a Project from a directory path.

        Args:
            dir_path: Path to a project directory in ~/.claude/projects/

        Returns:
            Project instance with decoded path and session files
        """
        name = dir_path.name
        decoded_path = cls._decode_project_path(name)

        session_files = sorted(
            dir_path.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
        )

        return cls(
            name=name, path=decoded_path, dir_path=dir_path, session_files=session_files
        )

    @staticmethod
    def _decode_project_path(encoded_name: str) -> str:
        """Decode a Claude project directory name to the actual filesystem path.

        Claude Code encodes paths by replacing '/' with '-', but also converts
        '_' and '-' in folder names to '-'. This creates ambiguity that we
        resolve by checking which path actually exists on disk.

        Args:
            encoded_name: Directory name like '-Users-ade-projects-block-browser'

        Returns:
            Decoded path like '/Users/ade/projects/block_browser'
        """
        # Split into components: '-Users-ade-foo-bar' -> ['', 'Users', 'ade', 'foo', 'bar']
        components = encoded_name.split("-")

        # Start with root
        current_path = Path("/")
        i = 1  # Skip empty first component from leading '-'

        while i < len(components):
            component = components[i]
            candidate = current_path / component

            if candidate.exists():
                # This component exists as-is, use it
                current_path = candidate
                i += 1
            else:
                # Try combining with subsequent components using '_' or '-'
                found = False
                # Try combining up to 4 components (reasonable limit for folder names)
                for j in range(i + 1, min(i + 5, len(components) + 1)):
                    combined_parts = components[i:j]

                    # Try underscore separator
                    underscore_name = "_".join(combined_parts)
                    underscore_candidate = current_path / underscore_name
                    if underscore_candidate.exists():
                        current_path = underscore_candidate
                        i = j
                        found = True
                        break

                    # Try hyphen separator
                    hyphen_name = "-".join(combined_parts)
                    hyphen_candidate = current_path / hyphen_name
                    if hyphen_candidate.exists():
                        current_path = hyphen_candidate
                        i = j
                        found = True
                        break

                if not found:
                    # Path doesn't exist on disk, fall back to simple slash replacement
                    # for the remaining components
                    remaining = "/".join(components[i:])
                    return str(current_path / remaining)

        return str(current_path)

    @property
    def session_count(self) -> int:
        return len(self.session_files)

    @property
    def short_name(self) -> str:
        """Get the short name (last path component) of the project, prettified.

        Converts folder names like 'block_browser' or 'my-project' to
        'Block Browser' or 'My Project' for display.
        """
        raw_name = self.path.split("/")[-1]
        # Replace underscores and hyphens with spaces, then title case
        prettified = raw_name.replace("_", " ").replace("-", " ")
        return prettified.title()

    @property
    def last_modified(self) -> Optional[datetime]:
        if self.session_files:
            mtime = self.session_files[0].stat().st_mtime
            return datetime.fromtimestamp(mtime)
        return None


def list_projects() -> list[Project]:
    """List all Claude Code projects, sorted by last modified.

    Returns:
        List of Project objects, most recently modified first.
        Returns empty list if ~/.claude/projects/ doesn't exist.

    Example:
        >>> projects = list_projects()
        >>> for p in projects[:3]:
        ...     print(f"{p.path}: {p.session_count} sessions")
    """
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []

    projects = []
    for item in projects_dir.iterdir():
        if item.is_dir() and item.name.startswith("-"):
            projects.append(Project.from_dir(item))

    # Sort by last modified
    projects.sort(key=lambda p: p.last_modified or datetime.min, reverse=True)
    return projects


def find_project(search: str) -> Optional[Project]:
    """Find a project by name or path substring (case-insensitive).

    Args:
        search: Partial match for project path or name

    Returns:
        First matching Project, or None if not found

    Example:
        >>> project = find_project("myproject")
        >>> project.path
        '/Users/foo/Documents/myproject'
    """
    projects = list_projects()
    search_lower = search.lower()

    for project in projects:
        if search_lower in project.path.lower() or search_lower in project.name.lower():
            return project
    return None


def parse_session(file_path: Path, project_path: str = "") -> Session:
    """Parse a JSONL session file into a Session object.

    Reads the file line by line, extracting messages and metadata.
    Handles malformed lines gracefully by skipping them.

    Args:
        file_path: Path to the .jsonl session file
        project_path: Optional project path for context

    Returns:
        Session object with messages, timestamps, and metadata

    Example:
        >>> session = parse_session(Path("~/.claude/projects/-foo/abc123.jsonl"))
        >>> print(f"{session.message_count} messages")
    """
    session_id = file_path.stem
    messages = []
    start_time = None
    end_time = None
    slug = None

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)

                # Extract metadata
                if slug is None and "slug" in data:
                    slug = data["slug"]

                # Parse message
                msg = Message.from_json(data)
                if msg:
                    messages.append(msg)
                    if msg.timestamp:
                        if start_time is None:
                            start_time = msg.timestamp
                        end_time = msg.timestamp

            except json.JSONDecodeError:
                continue

    return Session(
        session_id=session_id,
        project_path=project_path,
        file_path=file_path,
        messages=messages,
        start_time=start_time,
        end_time=end_time,
        slug=slug,
    )


def search_sessions(
    pattern: str, project: Optional[Project] = None, case_sensitive: bool = False
) -> Iterator[tuple[Session, list[Message]]]:
    """Search for a regex pattern across all sessions.

    Searches message content and tool inputs. Yields results as they're found
    to support streaming large result sets.

    Args:
        pattern: Regular expression pattern to search for
        project: Optional project to limit search scope
        case_sensitive: If True, search is case-sensitive (default: False)

    Yields:
        Tuples of (Session, list of matching Messages)

    Example:
        >>> for session, matches in search_sessions("TODO"):
        ...     print(f"{session.session_id}: {len(matches)} matches")
    """

    if project:
        projects = [project]
    else:
        projects = list_projects()

    flags = 0 if case_sensitive else re.IGNORECASE
    regex = re.compile(pattern, flags)

    for proj in projects:
        for session_file in proj.session_files:
            session = parse_session(session_file, proj.path)
            matching_messages = []

            for msg in session.messages:
                if regex.search(msg.content):
                    matching_messages.append(msg)
                # Also search tool inputs
                for tool_use in msg.tool_uses:
                    tool_input = json.dumps(tool_use.get("input", {}))
                    if regex.search(tool_input):
                        matching_messages.append(msg)
                        break

            if matching_messages:
                yield session, matching_messages


def get_session_by_id(
    session_id: str, project: Optional[Project] = None
) -> Optional[Session]:
    """Get a specific session by ID (supports partial matches).

    Args:
        session_id: Full or partial session ID to match
        project: Optional project to limit search scope

    Returns:
        Session object if found, None otherwise

    Example:
        >>> session = get_session_by_id("abc123")
        >>> session.message_count
        42
    """
    if project:
        projects = [project]
    else:
        projects = list_projects()

    for proj in projects:
        for session_file in proj.session_files:
            if session_file.stem == session_id or session_id in session_file.stem:
                return parse_session(session_file, proj.path)

    return None


@dataclass
class ProjectStats:
    """Statistics for a single project.

    Attributes:
        project: The Project object
        total_sessions: Number of session files
        total_messages: Sum of all messages
        total_user_messages: Sum of user messages only
        total_duration_minutes: Sum of all session durations
        agent_sessions: Count of agent-* sessions
        main_sessions: Count of non-agent sessions
        total_size_bytes: Total file size on disk
        avg_messages_per_session: Mean messages per session
        longest_session_duration: Human-readable longest session
        most_recent_session: Timestamp of most recent activity

    Properties:
        total_size_mb: Size in megabytes
        total_duration_str: Human-readable total duration
    """

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

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    @property
    def total_duration_str(self) -> str:
        """Format total duration as readable string."""
        return format_duration(self.total_duration_minutes)


@dataclass
class GlobalStats:
    """Aggregated statistics across all projects.

    Attributes:
        projects: List of ProjectStats for each project
        total_projects: Number of projects
        total_sessions: Sum of all sessions
        total_messages: Sum of all messages
        total_user_messages: Sum of user messages
        total_duration_minutes: Sum of all durations
        total_size_bytes: Total storage used
        avg_sessions_per_project: Mean sessions per project
        avg_messages_per_session: Mean messages per session
        most_active_project: Path of project with most messages
        largest_project: Path of project with most storage
        most_recent_activity: Most recent session timestamp
    """

    projects: List[ProjectStats]
    total_projects: int
    total_sessions: int
    total_messages: int
    total_user_messages: int
    total_duration_minutes: int
    total_size_bytes: int
    avg_sessions_per_project: float
    avg_messages_per_session: float
    most_active_project: str
    largest_project: str
    most_recent_activity: Optional[datetime]

    @property
    def total_size_mb(self) -> float:
        """Total storage in megabytes."""
        return self.total_size_bytes / (1024 * 1024)

    @property
    def total_duration_str(self) -> str:
        """Format total duration as readable string (e.g., '24h 30m')."""
        return format_duration(self.total_duration_minutes)


def calculate_project_stats(project: Project) -> ProjectStats:
    """Calculate detailed statistics for a single project.

    Parses all session files to compute message counts, durations,
    agent usage, and storage metrics.

    Args:
        project: Project to analyze

    Returns:
        ProjectStats with all computed metrics

    Example:
        >>> project = find_project("myproject")
        >>> stats = calculate_project_stats(project)
        >>> print(f"{stats.total_messages} messages in {stats.total_duration_str}")
    """
    total_messages = 0
    total_user_messages = 0
    total_duration_minutes = 0
    agent_sessions = 0
    main_sessions = 0
    total_size_bytes = 0
    longest_duration_minutes = 0
    most_recent_session = None

    for session_file in project.session_files:
        # File size
        total_size_bytes += session_file.stat().st_size

        # Parse session
        session = parse_session(session_file, project.path)

        # Count agent vs main sessions
        if session_file.name.startswith("agent-"):
            agent_sessions += 1
        else:
            main_sessions += 1

        # Message counts
        total_messages += session.message_count
        total_user_messages += session.user_message_count

        # Duration
        if session.start_time and session.end_time:
            duration = duration_minutes(session.start_time, session.end_time)
            total_duration_minutes += duration
            if duration > longest_duration_minutes:
                longest_duration_minutes = duration

        # Most recent session
        if session.start_time:
            if most_recent_session is None or session.start_time > most_recent_session:
                most_recent_session = session.start_time

    avg_messages = (
        total_messages / project.session_count if project.session_count > 0 else 0
    )

    return ProjectStats(
        project=project,
        total_sessions=project.session_count,
        total_messages=total_messages,
        total_user_messages=total_user_messages,
        total_duration_minutes=total_duration_minutes,
        agent_sessions=agent_sessions,
        main_sessions=main_sessions,
        total_size_bytes=total_size_bytes,
        avg_messages_per_session=avg_messages,
        longest_session_duration=format_duration(longest_duration_minutes),
        most_recent_session=most_recent_session,
    )


def calculate_global_stats(project_filter: Optional[str] = None) -> GlobalStats:
    """Calculate aggregated statistics across all projects.

    Computes per-project stats and aggregates them into global metrics.

    Args:
        project_filter: Optional project name to filter (not typically used)

    Returns:
        GlobalStats with aggregated metrics and per-project breakdown

    Raises:
        ValueError: If no projects are found

    Example:
        >>> stats = calculate_global_stats()
        >>> print(f"{stats.total_projects} projects, {stats.total_messages} messages")
    """
    if project_filter:
        project = find_project(project_filter)
        if not project:
            raise ValueError(f"No project found matching '{project_filter}'")
        projects = [calculate_project_stats(project)]
    else:
        all_projects = list_projects()
        projects = [calculate_project_stats(p) for p in all_projects]

    if not projects:
        raise ValueError("No projects found")

    # Aggregate totals
    total_sessions = sum(p.total_sessions for p in projects)
    total_messages = sum(p.total_messages for p in projects)
    total_user_messages = sum(p.total_user_messages for p in projects)
    total_duration_minutes = sum(p.total_duration_minutes for p in projects)
    total_size_bytes = sum(p.total_size_bytes for p in projects)

    # Find most active and largest projects
    most_active_project = max(projects, key=lambda p: p.total_messages).project.path
    largest_project = max(projects, key=lambda p: p.total_size_bytes).project.path

    # Find most recent activity
    most_recent_activity = None
    for p in projects:
        if p.most_recent_session:
            if (
                most_recent_activity is None
                or p.most_recent_session > most_recent_activity
            ):
                most_recent_activity = p.most_recent_session

    # Calculate averages
    avg_sessions_per_project = total_sessions / len(projects)
    avg_messages_per_session = (
        total_messages / total_sessions if total_sessions > 0 else 0
    )

    return GlobalStats(
        projects=projects,
        total_projects=len(projects),
        total_sessions=total_sessions,
        total_messages=total_messages,
        total_user_messages=total_user_messages,
        total_duration_minutes=total_duration_minutes,
        total_size_bytes=total_size_bytes,
        avg_sessions_per_project=avg_sessions_per_project,
        avg_messages_per_session=avg_messages_per_session,
        most_active_project=most_active_project,
        largest_project=largest_project,
        most_recent_activity=most_recent_activity,
    )


@dataclass
class SessionInfo:
    """Summary information about a parsed session.

    Used internally for story generation to avoid repeated parsing
    and to provide structured access to session metrics.

    Attributes:
        session_id: Unique identifier for the session
        start_time: When the session started
        end_time: When the session ended (may be None)
        duration_minutes: Length of session in minutes
        message_count: Total messages in session
        user_message_count: Messages from user
        is_agent: Whether this is an agent session
        slug: Optional session title/slug
    """

    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_minutes: int
    message_count: int
    user_message_count: int
    is_agent: bool
    slug: Optional[str]

    @classmethod
    def from_session(cls, session: Session, is_agent: bool) -> Optional["SessionInfo"]:
        """Create SessionInfo from a Session object.

        Args:
            session: The parsed Session
            is_agent: Whether this is an agent session

        Returns:
            SessionInfo with computed metrics, or None if session has no start_time
        """
        start_time = session.start_time
        if start_time is None:
            return None

        duration = 0
        if session.end_time:
            duration = duration_minutes(start_time, session.end_time)

        return cls(
            session_id=session.session_id,
            start_time=start_time,
            end_time=session.end_time,
            duration_minutes=duration,
            message_count=session.message_count,
            user_message_count=session.user_message_count,
            is_agent=is_agent,
            slug=session.slug,
        )


def collect_sessions(project: Project) -> List[SessionInfo]:
    """Collect and parse all sessions from a project into SessionInfo objects.

    This is a common operation used by multiple analysis functions. It parses
    each session file and converts it to a SessionInfo, filtering out sessions
    that have no start_time.

    Args:
        project: Project to collect sessions from

    Returns:
        List of SessionInfo objects (may be empty if no valid sessions)
    """
    sessions: List[SessionInfo] = []
    for session_file in project.session_files:
        session = parse_session(session_file, project.path)
        is_agent = session_file.name.startswith("agent-")
        info = SessionInfo.from_session(session, is_agent)
        if info is not None:
            sessions.append(info)
    return sessions


@dataclass
class ProjectStory:
    """Narrative analysis of a project's development journey.

    Contains insights about work patterns, collaboration style,
    and development personality derived from session analysis.

    Attributes:
        project_name: Short name (last path component)
        project_path: Full decoded path
        lifecycle_days: Days from first to last session
        birth_date: First session timestamp
        last_active: Most recent session timestamp
        peak_day: (date, message_count) of highest activity day
        break_periods: List of (start, end, days) gaps
        agent_sessions: Count of agent-* sessions
        main_sessions: Count of non-agent sessions
        collaboration_style: Description (e.g., "Heavy delegation")
        total_messages: Sum of all messages
        dev_time_hours: Total development time
        message_rate: Messages per hour
        work_pace: Description (e.g., "Steady, productive flow")
        avg_session_hours: Mean session length
        longest_session_hours: Maximum session length
        session_style: Description (e.g., "Marathon sessions")
        personality_traits: List of traits (e.g., ["Agent-driven", "Deep-work focused"])
        most_productive_session: SessionInfo
        daily_engagement: Description of engagement pattern
        insights: List of key insight strings
        daily_activity: Dict mapping dates to message counts (for sparklines)
        concurrent_claude_instances: Maximum number of Claude instances used simultaneously
        concurrent_insights: List of insights about concurrent usage patterns
    """

    project_name: str
    project_path: str
    lifecycle_days: int
    birth_date: datetime
    last_active: datetime
    peak_day: Optional[tuple[datetime, int]]
    break_periods: List[tuple[datetime, datetime, int]]
    agent_sessions: int
    main_sessions: int
    collaboration_style: str
    total_messages: int
    dev_time_hours: float
    message_rate: float
    work_pace: str
    avg_session_hours: float
    longest_session_hours: float
    session_style: str
    personality_traits: List[str]
    most_productive_session: SessionInfo
    daily_engagement: str
    insights: List[str]
    daily_activity: Dict[datetime, int] = field(default_factory=dict)
    concurrent_claude_instances: int = 0
    concurrent_insights: List[str] = field(default_factory=list)


def generate_project_story(project: Project) -> ProjectStory:
    """Generate narrative insights about a project's development journey.

    Analyzes session patterns to determine work style, collaboration patterns,
    and development personality traits.

    Args:
        project: Project to analyze

    Returns:
        ProjectStory with narrative insights and metrics

    Raises:
        ValueError: If project has no sessions with timestamps

    Example:
        >>> project = find_project("myproject")
        >>> story = generate_project_story(project)
        >>> print(f"Personality: {', '.join(story.personality_traits)}")
    """
    sessions = collect_sessions(project)

    if not sessions:
        raise ValueError(f"No sessions found for project {project.path}")

    sessions.sort(key=lambda x: x.start_time)

    # Basic lifecycle data
    first_session = sessions[0]
    last_session = sessions[-1]
    lifecycle_days = (last_session.start_time - first_session.start_time).days + 1

    # Daily activity analysis
    daily_activity = defaultdict(int)
    for session in sessions:
        day = session.start_time.date()
        daily_activity[day] += session.message_count

    # Find peak day and break periods
    peak_day = None
    break_periods = []

    if daily_activity:
        peak_day = max(daily_activity.items(), key=lambda x: x[1])

        # Find gaps
        sorted_days = sorted(daily_activity.keys())
        for i in range(1, len(sorted_days)):
            gap_days = (sorted_days[i] - sorted_days[i - 1]).days
            if gap_days > 1:
                break_periods.append((sorted_days[i - 1], sorted_days[i], gap_days))

    # Detect concurrent Claude instances
    # Look for sessions with overlapping timestamps
    concurrent_claude_instances = 0

    for i, session1 in enumerate(sessions):
        overlapping_sessions = 0
        for j, session2 in enumerate(sessions):
            if i != j and session1.start_time and session2.start_time:
                # Check if sessions overlap (within 30 minutes suggests concurrent use)
                time_diff = abs(
                    (session1.start_time - session2.start_time).total_seconds() / 60
                )
                if (
                    time_diff < 30
                ):  # Sessions starting within 30 minutes likely concurrent
                    overlapping_sessions += 1

        if overlapping_sessions > 2:  # Session overlaps with 2+ others
            concurrent_claude_instances = max(
                concurrent_claude_instances, overlapping_sessions
            )

    # Generate insights about concurrent usage
    concurrent_insights = []
    if concurrent_claude_instances > 3:
        concurrent_insights.append(
            f"Highly parallel workflow - used up to {concurrent_claude_instances} Claude instances simultaneously"
        )
    elif concurrent_claude_instances > 2:
        concurrent_insights.append(
            f"Parallel development patterns - often used {concurrent_claude_instances} Claude instances at once"
        )
    elif concurrent_claude_instances > 1:
        concurrent_insights.append(
            "Occasional multi-instance workflow for complex tasks"
        )

    if concurrent_claude_instances == 0:
        concurrent_insights.append(
            "Sequential workflow - used one Claude instance at a time"
        )

    # Agent collaboration analysis
    agent_sessions = len([s for s in sessions if s.is_agent])
    main_sessions = len([s for s in sessions if not s.is_agent])

    if main_sessions > 0:
        agent_ratio = agent_sessions / main_sessions
        if agent_ratio > 2:
            collaboration_style = "Heavy delegation"
        elif agent_ratio > 1:
            collaboration_style = "Balanced collaboration"
        else:
            collaboration_style = "Primarily direct work"
    else:
        collaboration_style = "Agent-only work"

    # Work intensity analysis
    total_messages = sum(s.message_count for s in sessions)
    total_dev_time = sum(s.duration_minutes for s in sessions) / 60
    message_rate = total_messages / total_dev_time if total_dev_time > 0 else 0

    work_pace = classify(
        message_rate,
        [
            (MESSAGE_RATE_HIGH, "Rapid-fire development"),
            (MESSAGE_RATE_MEDIUM, "Steady, productive flow"),
            (MESSAGE_RATE_LOW, "Deliberate, thoughtful work"),
        ],
        "Careful, methodical development",
    )

    # Session patterns
    session_lengths = [s.duration_minutes for s in sessions if s.duration_minutes > 0]
    avg_session_hours = (
        sum(session_lengths) / len(session_lengths) / 60 if session_lengths else 0
    )
    longest_session_hours = max(session_lengths) / 60 if session_lengths else 0

    session_style = classify(
        avg_session_hours,
        [
            (SESSION_LENGTH_LONG, "Marathon sessions (deep, focused work)"),
            (SESSION_LENGTH_EXTENDED, "Extended sessions (sustained effort)"),
            (SESSION_LENGTH_STANDARD, "Standard sessions (balanced approach)"),
        ],
        "Quick sprints (iterative development)",
    )

    # Personality traits
    personality_traits = []

    # Agent ratio trait
    agent_ratio = agent_sessions / len(sessions)
    personality_traits.append(
        classify(
            agent_ratio,
            [
                (AGENT_RATIO_HIGH, "Agent-driven"),
                (AGENT_RATIO_BALANCED, "Collaborative"),
            ],
            "Hands-on",
        )
    )

    # Session length trait
    personality_traits.append(
        classify(
            avg_session_hours,
            [
                (SESSION_LENGTH_LONG, "Deep-work focused"),
                (SESSION_LENGTH_EXTENDED, "Steady-paced"),
            ],
            "Quick-iterative",
        )
    )

    # Intensity trait
    personality_traits.append(
        classify(
            total_messages / lifecycle_days,
            [
                (ACTIVITY_INTENSITY_HIGH, "High-intensity"),
                (ACTIVITY_INTENSITY_MEDIUM, "Moderately active"),
            ],
            "Deliberate",
        )
    )

    # Most productive session
    most_productive = max(sessions, key=lambda x: x.message_count)

    # Daily engagement pattern
    if len(break_periods) == 0 and lifecycle_days > 1:
        daily_engagement = "Consistent daily engagement - no breaks"
    elif len(break_periods) > 2:
        daily_engagement = "Intermittent work pattern with regular breaks"
    else:
        daily_engagement = "Focused work with occasional breaks"

    # Generate insights
    insights = []
    insights.append(
        f"Most productive session: {most_productive.message_count} messages"
    )

    if agent_sessions and main_sessions:
        agent_efficiency = (
            sum(s.message_count for s in sessions if s.is_agent) / agent_sessions
        )
        main_efficiency = (
            sum(s.message_count for s in sessions if not s.is_agent) / main_sessions
        )

        if agent_efficiency > main_efficiency:
            insights.append("Agent sessions are more efficient than main sessions")
        else:
            insights.append("Main sessions drive most of the progress")

    insights.append(daily_engagement)

    return ProjectStory(
        project_name=project.short_name,
        project_path=project.path,
        lifecycle_days=lifecycle_days,
        birth_date=first_session.start_time,
        last_active=last_session.start_time,
        peak_day=peak_day,
        break_periods=break_periods,
        agent_sessions=agent_sessions,
        main_sessions=main_sessions,
        collaboration_style=collaboration_style,
        total_messages=total_messages,
        dev_time_hours=total_dev_time,
        message_rate=message_rate,
        work_pace=work_pace,
        avg_session_hours=avg_session_hours,
        longest_session_hours=longest_session_hours,
        session_style=session_style,
        personality_traits=personality_traits,
        most_productive_session=most_productive,
        daily_engagement=daily_engagement,
        insights=insights + concurrent_insights,
        daily_activity=dict(daily_activity),
        concurrent_claude_instances=concurrent_claude_instances,
        concurrent_insights=concurrent_insights,
    )


@dataclass
class GlobalStory:
    """Narrative analysis across all projects.

    Aggregates insights from individual project stories to provide
    a holistic view of development patterns and personality.

    Attributes:
        total_projects: Number of projects analyzed
        total_messages: Sum of all messages across projects
        total_dev_time: Total development hours
        avg_agent_ratio: Average agent collaboration ratio
        avg_session_length: Average session length in hours
        common_traits: List of (trait, count) tuples for most common traits
        project_stories: List of individual ProjectStory objects
        recent_activity: List of (timestamp, project_name) for recent work
    """

    total_projects: int
    total_messages: int
    total_dev_time: float
    avg_agent_ratio: float
    avg_session_length: float
    common_traits: List[tuple[str, int]]
    project_stories: List[ProjectStory]
    recent_activity: List[tuple[datetime, str]]


def generate_global_story() -> GlobalStory:
    """Generate a narrative story across all projects.

    Aggregates project stories and identifies common patterns
    and personality traits across the entire development history.

    Returns:
        GlobalStory with aggregated insights

    Raises:
        ValueError: If no projects with sessions are found

    Example:
        >>> story = generate_global_story()
        >>> print(f"{story.total_projects} projects analyzed")
    """
    all_projects = list_projects()
    project_stories = []

    for project in all_projects:
        try:
            story = generate_project_story(project)
            project_stories.append(story)
        except ValueError:
            continue

    if not project_stories:
        raise ValueError("No projects with sessions found")

    # Global patterns
    total_projects = len(project_stories)
    total_messages = sum(s.total_messages for s in project_stories)
    total_dev_time = sum(s.dev_time_hours for s in project_stories)

    # Work personality analysis
    avg_agent_ratio = sum(s.agent_sessions for s in project_stories) / sum(
        s.agent_sessions + s.main_sessions for s in project_stories
    )
    avg_session_length = (
        sum(s.avg_session_hours for s in project_stories) / total_projects
    )

    # Most common traits
    all_traits = []
    for story in project_stories:
        all_traits.extend(story.personality_traits)

    common_traits = Counter(all_traits).most_common(3)

    # Project switching patterns
    recent_activity = []
    if project_stories:
        now = datetime.now(project_stories[0].birth_date.tzinfo)
        for story in project_stories:
            # Make both times comparable
            story_time = story.last_active
            if story_time.tzinfo != now.tzinfo:
                if story_time.tzinfo is None:
                    story_time = story_time.replace(tzinfo=now.tzinfo)
                else:
                    now = now.replace(tzinfo=story_time.tzinfo)

            if story_time >= now - timedelta(days=7):
                recent_activity.append((story.last_active, story.project_name))

    recent_activity.sort()

    return GlobalStory(
        total_projects=total_projects,
        total_messages=total_messages,
        total_dev_time=total_dev_time,
        avg_agent_ratio=avg_agent_ratio,
        avg_session_length=avg_session_length,
        common_traits=common_traits,
        project_stories=project_stories,
        recent_activity=recent_activity,
    )


# =============================================================================
# Wrapped Story V3 - Tufte Edition
# =============================================================================

# V3 encoding constants
WRAPPED_VERSION_V3 = 3

# Distribution bucket boundaries
SESSION_DURATION_BUCKETS = [15, 30, 60, 120, 240, 480, 720, 1440, 2880]  # minutes
AGENT_RATIO_BUCKETS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]  # 0-1
MESSAGE_LENGTH_BUCKETS = [50, 100, 200, 500, 1000, 2000, 5000]  # chars

# Event type indices
EVENT_TYPE_INDICES = {
    'peak_day': 0,
    'streak_start': 1,
    'streak_end': 2,
    'new_project': 3,
    'milestone': 4,
    'gap_start': 5,
    'gap_end': 6,
}

# Hard limits
MAX_PROJECTS = 12
MAX_COOCCURRENCE_EDGES = 20
MAX_TIMELINE_EVENTS = 25  # Increased to use URL headroom
MAX_SESSION_FINGERPRINTS = 20  # Increased to use URL headroom
MAX_PROJECT_NAME_LENGTH = 50
MAX_DISPLAY_NAME_LENGTH = 30

# Heatmap quantization scale (0-15 for compact encoding)
HEATMAP_QUANT_SCALE = 15


@dataclass
class SessionInfoV3(SessionInfo):
    """Extended SessionInfo with project tracking for V3 wrapped."""
    project_name: str = ""
    project_path: str = ""

    @classmethod
    def from_session_with_project(
        cls, session: Session, is_agent: bool, project_name: str, project_path: str
    ) -> Optional["SessionInfoV3"]:
        """Create SessionInfoV3 from a Session object with project info.

        Args:
            session: The parsed Session
            is_agent: Whether this is an agent session
            project_name: Short project name
            project_path: Full project path

        Returns:
            SessionInfoV3 with computed metrics, or None if session has no start_time
        """
        start_time = session.start_time
        if start_time is None:
            return None

        duration = 0
        if session.end_time:
            duration = duration_minutes(start_time, session.end_time)

        return cls(
            session_id=session.session_id,
            start_time=start_time,
            end_time=session.end_time,
            duration_minutes=duration,
            message_count=session.message_count,
            user_message_count=session.user_message_count,
            is_agent=is_agent,
            slug=session.slug,
            project_name=project_name,
            project_path=project_path,
        )


@dataclass
class ProjectStatsV3:
    """Statistics for a single project in V3 wrapped."""
    name: str
    path: str
    message_count: int
    agent_sessions: int
    main_sessions: int
    hours: int  # Integer hours for compact encoding
    days_active: int
    first_day: int  # Day of year (1-366)
    last_day: int   # Day of year (1-366)

    @property
    def session_count(self) -> int:
        """Total sessions (agent + main)."""
        return self.agent_sessions + self.main_sessions

    @property
    def agent_ratio(self) -> float:
        """Ratio of agent sessions to total sessions."""
        if self.session_count == 0:
            return 0.0
        return self.agent_sessions / self.session_count


# =============================================================================
# V3 Compute Functions
# =============================================================================


def compute_activity_heatmap(sessions: List[SessionInfoV3]) -> List[int]:
    """Compute 7×24 activity heatmap from sessions.

    Returns:
        List of 168 integers: heatmap[day * 24 + hour] = message_count
        day: 0=Monday, 6=Sunday
        hour: 0-23
    """
    heatmap = [0] * 168

    for session in sessions:
        if not session.start_time:
            continue

        # Attribute all messages to start hour (simplification)
        day = session.start_time.weekday()  # 0=Monday
        hour = session.start_time.hour
        idx = day * 24 + hour
        heatmap[idx] += session.message_count

    return heatmap


def compute_distribution(values: List[float], buckets: List[float]) -> List[int]:
    """Bucket values into a histogram distribution.

    Uses bisect_right for bucket assignment:
    - Bucket 0: value < buckets[0] (strictly less than first boundary)
    - Bucket i: buckets[i-1] <= value < buckets[i]
    - Bucket n: value >= buckets[n-1] (includes last boundary and above)

    Note: Values exactly equal to a boundary go to the NEXT bucket.
    Example: with buckets=[10,20,30], value 10 goes to bucket 1, not bucket 0.

    Returns:
        List of len(buckets)+1 counts
    """
    dist = [0] * (len(buckets) + 1)
    for v in values:
        bucket_idx = bisect_right(buckets, v)
        dist[bucket_idx] += 1
    return dist


def compute_session_duration_distribution(sessions: List[SessionInfoV3]) -> List[int]:
    """Compute session duration histogram."""
    durations = [s.duration_minutes for s in sessions if s.duration_minutes > 0]
    return compute_distribution(durations, SESSION_DURATION_BUCKETS)


def compute_agent_ratio_distribution(projects: List[ProjectStatsV3]) -> List[int]:
    """Compute agent ratio histogram across projects."""
    ratios = [p.agent_ratio for p in projects if p.session_count > 0]
    return compute_distribution(ratios, AGENT_RATIO_BUCKETS)


def compute_message_length_distribution(message_lengths: List[int]) -> List[int]:
    """Compute message length histogram.

    Args:
        message_lengths: List of message content lengths in characters

    Returns:
        List of 8 bucket counts for message length distribution
    """
    return compute_distribution(message_lengths, MESSAGE_LENGTH_BUCKETS)


def compute_trait_scores(
    sessions: List[SessionInfoV3],
    projects: List[ProjectStatsV3],
    heatmap: List[int],
    unique_tools_count: int = 0
) -> Dict[str, int]:
    """Compute quantized 0-100 scores for behavioral dimensions.

    These are self-relative normalized scores, NOT population percentiles.
    Each score is scaled to [0, 100] based on reasonable thresholds.
    Using integers for compact msgpack encoding (1 byte vs 9 bytes for floats).

    Args:
        sessions: List of session info objects
        projects: List of project stats objects
        heatmap: 168-value activity heatmap
        unique_tools_count: Number of unique tools used across all sessions

    Returns:
        Dict mapping trait code to integer score in [0, 100]
    """
    scores = {}

    # === AGENT DELEGATION (ad) ===
    # 0 = all hands-on, 1 = all agent
    total_sessions = len(sessions)
    agent_sessions = len([s for s in sessions if s.is_agent])
    scores['ad'] = agent_sessions / total_sessions if total_sessions > 0 else 0.5

    # === SESSION DEPTH PREFERENCE (sp) ===
    # 0 = median <15min, 1 = median >4 hours
    durations = sorted([s.duration_minutes for s in sessions if s.duration_minutes > 0])
    if durations:
        median_duration = durations[len(durations) // 2]
        scores['sp'] = min(1.0, median_duration / 240)  # 4 hours = 1.0
    else:
        scores['sp'] = 0.5

    # === FOCUS CONCENTRATION (fc) ===
    # Herfindahl-Hirschman Index: 1/n (even) to 1.0 (all in one project)
    if projects:
        total_messages = sum(p.message_count for p in projects)
        if total_messages > 0:
            hhi = sum((p.message_count / total_messages) ** 2 for p in projects)
            scores['fc'] = hhi
        else:
            scores['fc'] = 0.5
    else:
        scores['fc'] = 0.5

    # === CIRCADIAN CONSISTENCY (cc) ===
    # Low variance in start hours = high consistency
    start_hours = [s.start_time.hour for s in sessions if s.start_time]
    if len(start_hours) > 1:
        mean_hour = sum(start_hours) / len(start_hours)
        variance = sum((h - mean_hour) ** 2 for h in start_hours) / len(start_hours)
        # Variance of 36 (std=6 hours) = inconsistent
        scores['cc'] = max(0.0, 1 - variance / 36)
    else:
        scores['cc'] = 0.5

    # === WEEKEND RATIO (wr) ===
    # 0 = no weekend activity, 1 = 40%+ weekend (vs expected 28.6%)
    weekend_messages = sum(heatmap[5*24:7*24])  # Sat (5) + Sun (6)
    weekday_messages = sum(heatmap[0:5*24])      # Mon-Fri (0-4)
    total = weekend_messages + weekday_messages
    if total > 0:
        raw_ratio = weekend_messages / total
        scores['wr'] = min(1.0, raw_ratio / 0.4)  # 40% weekend = 1.0
    else:
        scores['wr'] = 0.0

    # === BURST VS STEADY (bs) ===
    # Coefficient of variation of daily message counts
    daily_messages: Dict[datetime, int] = defaultdict(int)
    for s in sessions:
        if s.start_time:
            day_key = s.start_time.date()
            daily_messages[day_key] += s.message_count

    if len(daily_messages) > 1:
        values = list(daily_messages.values())
        mean_daily = sum(values) / len(values)
        if mean_daily > 0:
            std_daily = (sum((v - mean_daily) ** 2 for v in values) / len(values)) ** 0.5
            cv = std_daily / mean_daily
            scores['bs'] = min(1.0, cv)  # CV > 1 = very bursty
        else:
            scores['bs'] = 0.5
    else:
        scores['bs'] = 0.5

    # === CONTEXT SWITCHING (cs) ===
    # Average unique projects per active day
    projects_per_day: Dict[datetime, Set[str]] = defaultdict(set)
    for s in sessions:
        if s.start_time and s.project_name:
            day_key = s.start_time.date()
            projects_per_day[day_key].add(s.project_name)

    if projects_per_day:
        avg_projects = sum(len(p) for p in projects_per_day.values()) / len(projects_per_day)
        # 1 project/day = 0, 4+ projects/day = 1
        scores['cs'] = min(1.0, max(0.0, (avg_projects - 1) / 3))
    else:
        scores['cs'] = 0.0

    # === MESSAGE RATE METRICS (shared for mv and ri) ===
    messages_per_hour = [
        s.message_count / max(0.1, s.duration_minutes / 60)
        for s in sessions if s.duration_minutes > 0
    ]
    if messages_per_hour:
        sorted_rates = sorted(messages_per_hour)
        median_rate = sorted_rates[len(sorted_rates) // 2]
    else:
        median_rate = 15.0  # Default middle value

    # === MESSAGE VERBOSITY (mv) ===
    # Inverse of message rate (high rate = short messages = low verbosity)
    # 30 msg/hr = terse (0), 5 msg/hr = verbose (1)
    scores['mv'] = max(0.0, min(1.0, 1 - median_rate / 30))

    # === TOOL DIVERSITY (td) ===
    # 0 = minimal tools (1-2), 1 = many tools (10+)
    # Claude Code has ~15-20 common tools, so 10+ indicates diverse usage
    if unique_tools_count > 0:
        scores['td'] = min(1.0, (unique_tools_count - 1) / 9)  # 1 tool = 0, 10+ tools = 1
    else:
        scores['td'] = 0.5  # Default when no data available

    # === RESPONSE INTENSITY (ri) ===
    # Median messages per hour during sessions
    # 20 msg/hr = intense (1.0)
    scores['ri'] = min(1.0, median_rate / 20)

    # Quantize all scores to integers 0-100
    return {k: round(v * 100) for k, v in scores.items()}


def compute_project_cooccurrence(
    sessions: List[SessionInfoV3],
    project_names: List[str],
    max_edges: int = MAX_COOCCURRENCE_EDGES
) -> List[Tuple[int, int, int]]:
    """Compute project co-occurrence: which projects were worked on the same day.

    Args:
        sessions: List of sessions with project_name set
        project_names: Ordered list of project names (indices into tp array)
        max_edges: Maximum edges to return (keeps highest weights)

    Returns:
        List of (project_a_idx, project_b_idx, days_co_occurred)
        Sorted by weight descending, limited to max_edges
    """
    proj_to_idx = {name: i for i, name in enumerate(project_names)}

    # Group sessions by day
    sessions_by_day: Dict[datetime, Set[str]] = defaultdict(set)
    for s in sessions:
        if s.start_time and s.project_name:
            day = s.start_time.date()
            sessions_by_day[day].add(s.project_name)

    # Count co-occurrences
    cooccurrence: Dict[Tuple[int, int], int] = defaultdict(int)
    for day_projects in sessions_by_day.values():
        project_list = [p for p in day_projects if p in proj_to_idx]
        for i in range(len(project_list)):
            for j in range(i + 1, len(project_list)):
                idx_a = proj_to_idx[project_list[i]]
                idx_b = proj_to_idx[project_list[j]]
                # Always store smaller index first for consistency
                key = (min(idx_a, idx_b), max(idx_a, idx_b))
                cooccurrence[key] += 1

    # Sort by weight and limit
    edges = [(a, b, count) for (a, b), count in cooccurrence.items()]
    edges.sort(key=lambda x: x[2], reverse=True)
    return edges[:max_edges]


def detect_timeline_events(
    sessions: List[SessionInfoV3],
    project_names: List[str],
    year: int,
    max_events: int = MAX_TIMELINE_EVENTS
) -> List[List]:
    """Detect significant events throughout the year.

    Events are prioritized: peak > milestones > streaks > gaps > new_project

    Returns:
        List of event arrays: [day, type, value, project_idx]
        (4 elements per event, -1 for missing optional values)
    """
    proj_to_idx = {name: i for i, name in enumerate(project_names)}
    events = []

    # Group by day of year
    messages_by_day: Dict[int, int] = defaultdict(int)
    projects_first_day: Dict[str, int] = {}

    for s in sessions:
        if not s.start_time or s.start_time.year != year:
            continue

        day_of_year = s.start_time.timetuple().tm_yday
        messages_by_day[day_of_year] += s.message_count

        if s.project_name and s.project_name not in projects_first_day:
            projects_first_day[s.project_name] = day_of_year

    if not messages_by_day:
        return []

    # === PEAK DAY (highest priority) ===
    peak_day = max(messages_by_day.keys(), key=lambda d: messages_by_day[d])
    # Array format: [day, type, value, project_idx]
    events.append([peak_day, EVENT_TYPE_INDICES['peak_day'], messages_by_day[peak_day], -1])

    # === MILESTONES ===
    cumulative = 0
    milestones = [100, 500, 1000, 2000, 5000, 10000]
    milestone_idx = 0
    for day in sorted(messages_by_day.keys()):
        cumulative += messages_by_day[day]
        while milestone_idx < len(milestones) and cumulative >= milestones[milestone_idx]:
            events.append([day, EVENT_TYPE_INDICES['milestone'], milestones[milestone_idx], -1])
            milestone_idx += 1

    # === STREAKS AND GAPS ===
    active_days = sorted(messages_by_day.keys())
    if len(active_days) > 0:
        streak_start = active_days[0]
        streak_length = 1

        for i in range(1, len(active_days)):
            gap = active_days[i] - active_days[i-1]

            if gap == 1:
                streak_length += 1
            else:
                # End of streak
                if streak_length >= 5:
                    events.append([streak_start, EVENT_TYPE_INDICES['streak_start'], -1, -1])
                    events.append([active_days[i-1], EVENT_TYPE_INDICES['streak_end'], streak_length, -1])

                # Gap detection
                if gap >= 7:
                    events.append([active_days[i-1], EVENT_TYPE_INDICES['gap_start'], -1, -1])
                    events.append([active_days[i], EVENT_TYPE_INDICES['gap_end'], gap, -1])

                streak_start = active_days[i]
                streak_length = 1

        # Final streak check
        if streak_length >= 5:
            events.append([streak_start, EVENT_TYPE_INDICES['streak_start'], -1, -1])
            events.append([active_days[-1], EVENT_TYPE_INDICES['streak_end'], streak_length, -1])

    # === NEW PROJECT EVENTS (lowest priority) ===
    for project, day in projects_first_day.items():
        if project in proj_to_idx:
            events.append([day, EVENT_TYPE_INDICES['new_project'], -1, proj_to_idx[project]])

    # Sort by day, then by priority (lower type index = higher priority)
    # Array format: [day, type, value, project_idx]
    events.sort(key=lambda e: (e[0], e[1]))

    # Limit to max_events, keeping highest priority
    if len(events) > max_events:
        # Re-sort by priority, take top N, then re-sort by day
        events.sort(key=lambda e: e[1])
        events = events[:max_events]
        events.sort(key=lambda e: e[0])

    return events


def compute_session_fingerprint(session: Session) -> List[int]:
    """Compute an 8-value fingerprint encoding session "shape".

    Fingerprint encodes (quantized to integers 0-100):
    [0-3]: Message distribution across session quarters (normalized)
    [4]: Tool invocation density (tools per message)
    [5]: Error/retry rate (error patterns in content)
    [6]: Edit operation ratio (Edit tools vs total tools)
    [7]: Long message ratio (proxy for deliberative thinking)

    Returns:
        List of 8 integers in [0, 100] (quantized from 0.0-1.0)
    """
    fingerprint = [0.0] * 8

    if not session.messages or len(session.messages) < 2:
        return [0] * 8  # Return integers

    # Divide session into 4 quarters by message index
    total_messages = len(session.messages)
    quarter_size = max(1, total_messages // 4)

    quarter_counts = [0, 0, 0, 0]
    for i, msg in enumerate(session.messages):
        quarter = min(3, i // quarter_size)
        quarter_counts[quarter] += 1

    # Normalize quarters to 0-1
    max_quarter = max(quarter_counts) or 1
    for i in range(4):
        fingerprint[i] = quarter_counts[i] / max_quarter

    # [4] Tool density - count tool uses per message
    tool_count = 0
    edit_tool_count = 0
    for msg in session.messages:
        for tool_use in msg.tool_uses:
            tool_count += 1
            tool_name = tool_use.get("name", "").lower()
            if "edit" in tool_name or "write" in tool_name:
                edit_tool_count += 1
    fingerprint[4] = min(1.0, tool_count / (total_messages * 2))  # Normalize

    # [5] Error/retry rate - count error patterns in content
    error_patterns = ["error", "failed", "retry", "fix", "bug", "issue", "problem"]
    error_count = 0
    for msg in session.messages:
        content_lower = msg.content.lower()
        if any(pattern in content_lower for pattern in error_patterns):
            error_count += 1
    fingerprint[5] = min(1.0, error_count / total_messages)

    # [6] Edit operation ratio - Edit/Write tools vs total tools
    if tool_count > 0:
        fingerprint[6] = edit_tool_count / tool_count
    else:
        fingerprint[6] = 0.0

    # [7] Long message ratio - messages with substantial content (proxy for deliberation)
    # Messages over 500 chars suggest more thoughtful/detailed responses
    long_messages = sum(1 for msg in session.messages if len(msg.content) > 500)
    fingerprint[7] = min(1.0, long_messages / total_messages)

    # Quantize to integers 0-100 for compact encoding
    return [round(v * 100) for v in fingerprint]


def get_top_session_fingerprints(
    sessions: List[SessionInfoV3],
    session_file_map: Dict[str, Path],
    project_names: List[str],
    limit: int = MAX_SESSION_FINGERPRINTS
) -> List[List]:
    """Get fingerprints for the most significant sessions.

    Args:
        sessions: List of SessionInfoV3 with project_name set
        session_file_map: Mapping of session_id to file path for loading
        project_names: Ordered list of project names for indexing
        limit: Max fingerprints to return

    Returns:
        List of fingerprint arrays: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
        (14 elements per fingerprint for compact encoding)
    """
    proj_to_idx = {name: i for i, name in enumerate(project_names)}

    # Score sessions by significance (messages × sqrt(duration))
    scored = []
    for s in sessions:
        if s.project_name in proj_to_idx:
            score = s.message_count * (s.duration_minutes ** 0.5 if s.duration_minutes > 0 else 1)
            scored.append((score, s))

    scored.sort(reverse=True, key=lambda x: x[0])

    fingerprints = []
    for _, info in scored[:limit]:
        # Load full session if file path available
        fp = [25, 50, 75, 100, 50, 10, 30, 20]  # Default fallback (quantized 0-100)

        if info.session_id in session_file_map:
            try:
                full_session = parse_session(session_file_map[info.session_id], info.project_path)
                fp = compute_session_fingerprint(full_session)
            except Exception:
                pass  # Use default on error

        # Compact array format: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
        fingerprints.append([
            info.duration_minutes,
            info.message_count,
            1 if info.is_agent else 0,  # Boolean as int for compact encoding
            info.start_time.hour if info.start_time else 0,
            info.start_time.weekday() if info.start_time else 0,
            proj_to_idx.get(info.project_name, 0),
        ] + fp)  # Flatten fp array into the main array

    return fingerprints


# =============================================================================
# V3 RLE Encoding
# =============================================================================


def rle_encode(values: List[int]) -> List[int]:
    """Run-length encode a list of integers.

    Format: [value, count, value, count, ...]
    Only beneficial for sequences with repeated values.

    Example: [0, 0, 0, 5, 5, 0] -> [0, 3, 5, 2, 0, 1]
    """
    if not values:
        return []

    result = []
    current_value = values[0]
    count = 1

    for v in values[1:]:
        if v == current_value:
            count += 1
        else:
            result.extend([current_value, count])
            current_value = v
            count = 1

    result.extend([current_value, count])
    return result


def rle_decode(encoded: List[int]) -> List[int]:
    """Decode run-length encoded data."""
    result = []
    for i in range(0, len(encoded), 2):
        value = encoded[i]
        count = encoded[i + 1] if i + 1 < len(encoded) else 1
        result.extend([value] * count)
    return result


def rle_encode_if_smaller(values: List[int]) -> Tuple[bool, List[int]]:
    """RLE encode only if it reduces size.

    Returns:
        Tuple of (is_rle_encoded, data)
    """
    encoded = rle_encode(values)
    if len(encoded) < len(values):
        return (True, encoded)
    return (False, values)


# =============================================================================
# V3 WrappedStory Dataclass
# =============================================================================


@dataclass
class WrappedStoryV3:
    """V3 Wrapped Story with rich visualization data.

    This dataclass is designed for Tufte-inspired data visualizations,
    including heatmaps, distributions, and continuous trait scores.
    """

    # Version and basic info
    v: int = WRAPPED_VERSION_V3
    y: int = 0  # Year
    n: Optional[str] = None  # Display name

    # Core counts
    p: int = 0  # Total projects
    s: int = 0  # Total sessions
    m: int = 0  # Total messages
    h: int = 0  # Total hours (integer for compact encoding)
    d: int = 0  # Days active

    # Temporal data
    hm: List[int] = field(default_factory=list)  # 7×24 heatmap (168 values)
    ma: List[int] = field(default_factory=list)  # Monthly activity (12 values)
    mh: List[int] = field(default_factory=list)  # Monthly hours (12 values, integers)
    ms: List[int] = field(default_factory=list)  # Monthly sessions (12 values)

    # Distributions
    sd: List[int] = field(default_factory=list)  # Session duration distribution
    ar: List[int] = field(default_factory=list)  # Agent ratio distribution
    ml: List[int] = field(default_factory=list)  # Message length distribution

    # Trait scores (0-100 integers, quantized from 0.0-1.0)
    ts: Dict[str, int] = field(default_factory=dict)

    # Project data (compact arrays: [name, messages, hours, days, sessions, agent_ratio])
    tp: List[List] = field(default_factory=list)

    # Co-occurrence graph
    pc: List[Tuple[int, int, int]] = field(default_factory=list)

    # Timeline events (compact arrays: [day, type, value, project_idx])
    te: List[List] = field(default_factory=list)

    # Session fingerprints (compact arrays: [duration, messages, is_agent, hour, weekday, pi, fp0..7])
    sf: List[List] = field(default_factory=list)

    # Longest session (hours, float for precision)
    ls: float = 0.0

    # Streak stats: [count, longest_days, current_days, avg_days]
    sk: List[int] = field(default_factory=list)

    # Token stats: {total, input, output, cache_read, cache_create, models: {model: tokens}}
    tk: Dict[str, Any] = field(default_factory=dict)

    # Year-over-year comparison
    yoy: Optional[Dict[str, int]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            'v': self.v,
            'y': self.y,
            'p': self.p,
            's': self.s,
            'm': self.m,
            'h': self.h,  # Already integer
            'd': self.d,
            'hm': self.hm,
            'ma': self.ma,
            'mh': self.mh,  # Already integers
            'ms': self.ms,
            'sd': self.sd,
            'ar': self.ar,
            'ml': self.ml,
            'ts': self.ts,
            'tp': self.tp,
            'pc': self.pc,
            'te': self.te,
            'sf': self.sf,
            'ls': round(self.ls, 1),  # Round to 1 decimal for compactness
            'sk': self.sk,
            'tk': self.tk,
        }
        if self.n:
            result['n'] = self.n
        if self.yoy:
            result['yoy'] = self.yoy
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "WrappedStoryV3":
        """Create from dictionary."""
        return cls(
            v=d.get('v', WRAPPED_VERSION_V3),
            y=d.get('y', 0),
            n=d.get('n'),
            p=d.get('p', 0),
            s=d.get('s', 0),
            m=d.get('m', 0),
            h=d.get('h', 0),
            d=d.get('d', 0),
            hm=d.get('hm', []),
            ma=d.get('ma', []),
            mh=d.get('mh', []),
            ms=d.get('ms', []),
            sd=d.get('sd', []),
            ar=d.get('ar', []),
            ml=d.get('ml', []),
            ts=d.get('ts', {}),
            tp=d.get('tp', []),
            pc=[tuple(x) for x in d.get('pc', [])],
            te=d.get('te', []),
            sf=d.get('sf', []),
            ls=d.get('ls', 0.0),
            sk=d.get('sk', []),
            tk=d.get('tk', {}),
            yoy=d.get('yoy'),
        )


def quantize_heatmap(heatmap: List[int], scale: int = HEATMAP_QUANT_SCALE) -> List[int]:
    """Quantize heatmap values to 0-scale for compact encoding.

    Args:
        heatmap: Raw message counts per hour slot
        scale: Max quantized value (default 15)

    Returns:
        Quantized heatmap with values in [0, scale]
    """
    if not heatmap:
        return heatmap
    max_val = max(heatmap) or 1
    return [min(scale, round(v * scale / max_val)) for v in heatmap]


def encode_wrapped_story_v3(story: WrappedStoryV3) -> str:
    """Encode V3 story with quantization and RLE compression."""
    import base64
    import msgpack

    data = story.to_dict()

    # Quantize and RLE encode heatmap
    if 'hm' in data and data['hm']:
        # Quantize to 0-15 scale for compact encoding
        quantized = quantize_heatmap(data['hm'])
        # RLE encode if beneficial
        is_rle, encoded_hm = rle_encode_if_smaller(quantized)
        if is_rle:
            data['hm'] = encoded_hm
            data['hm_rle'] = True  # Flag for decoder
        else:
            data['hm'] = quantized

    packed = msgpack.packb(data, use_bin_type=True)
    return base64.urlsafe_b64encode(packed).rstrip(b'=').decode('ascii')


def decode_wrapped_story_v3(encoded: str) -> WrappedStoryV3:
    """Decode V3 story."""
    import base64
    import msgpack

    # Add padding if needed
    padding = (4 - len(encoded) % 4) % 4
    padded = encoded + '=' * padding

    packed = base64.urlsafe_b64decode(padded)
    data = msgpack.unpackb(packed, raw=False, strict_map_key=False)

    # RLE decode heatmap if flagged
    if data.get('hm_rle') and 'hm' in data:
        data['hm'] = rle_decode(data['hm'])
        del data['hm_rle']

    return WrappedStoryV3.from_dict(data)


def compute_streak_stats(active_dates: Set[date], year: int) -> List[int]:
    """Compute streak statistics from active dates.

    A streak is 2+ consecutive days of activity.

    Args:
        active_dates: Set of dates with activity
        year: The year being analyzed

    Returns:
        List of [streak_count, longest_streak, current_streak, avg_streak_days]
        All values are integers for compact encoding.
    """
    if not active_dates:
        return [0, 0, 0, 0]

    # Sort dates
    sorted_dates = sorted(active_dates)

    # Find all streaks
    streaks: List[int] = []
    current_streak_length = 1

    for i in range(1, len(sorted_dates)):
        diff = (sorted_dates[i] - sorted_dates[i-1]).days
        if diff == 1:
            # Consecutive day
            current_streak_length += 1
        else:
            # Gap - save streak if >= 2 days
            if current_streak_length >= 2:
                streaks.append(current_streak_length)
            current_streak_length = 1

    # Don't forget the last streak
    if current_streak_length >= 2:
        streaks.append(current_streak_length)

    # Compute stats
    streak_count = len(streaks)
    longest_streak = max(streaks) if streaks else 0
    avg_streak = round(sum(streaks) / len(streaks)) if streaks else 0

    # Check if there's a current active streak (streak that includes today or end of year)
    current_streak = 0
    today = date.today()
    year_end = date(year, 12, 31)
    reference_date = min(today, year_end)

    if sorted_dates:
        # Count backwards from most recent date
        streak_end = sorted_dates[-1]
        if (reference_date - streak_end).days <= 1:  # Active recently
            current_streak = 1
            for i in range(len(sorted_dates) - 2, -1, -1):
                if (sorted_dates[i+1] - sorted_dates[i]).days == 1:
                    current_streak += 1
                else:
                    break

    return [streak_count, longest_streak, current_streak, avg_streak]


def generate_wrapped_story_v3(
    year: int,
    name: Optional[str] = None,
    previous_year_data: Optional[Dict] = None
) -> WrappedStoryV3:
    """Generate a V3 WrappedStory with rich visualization data.

    Args:
        year: Year to generate wrapped for
        name: Optional display name
        previous_year_data: Optional dict with previous year stats for YoY comparison

    Returns:
        WrappedStoryV3 with all visualization data
    """
    current_year = datetime.now().year
    if year > current_year:
        raise ValueError(f"Cannot generate wrapped for future year {year}")
    if year < 2024:
        raise ValueError(f"Claude Code didn't exist in {year}")

    # Collect all sessions with project info
    all_sessions: List[SessionInfoV3] = []
    project_sessions: Dict[str, List[SessionInfoV3]] = defaultdict(list)
    session_file_map: Dict[str, Path] = {}  # For fingerprint computation

    # Also collect message lengths, tools, and token usage for the target year
    all_message_lengths: List[int] = []
    all_unique_tools: Set[str] = set()

    # Token tracking
    token_stats: Dict[str, Any] = {
        'total': 0,
        'input': 0,
        'output': 0,
        'cache_read': 0,
        'cache_create': 0,
        'models': defaultdict(int),  # model -> total tokens
    }

    for project in list_projects():
        for session_file in project.session_files:
            session = parse_session(session_file, project.path)
            is_agent = session_file.name.startswith("agent-")
            info = SessionInfoV3.from_session_with_project(
                session, is_agent, project.short_name, project.path
            )
            if info is not None:
                all_sessions.append(info)
                project_sessions[project.short_name].append(info)
                session_file_map[session.session_id] = session_file

                # Collect message lengths, tools, and tokens if in target year
                if info.start_time and info.start_time.year == year:
                    for msg in session.messages:
                        if msg.content:
                            all_message_lengths.append(len(msg.content))
                        for tool_use in msg.tool_uses:
                            tool_name = tool_use.get("name", "")
                            if tool_name:
                                all_unique_tools.add(tool_name)
                        # Aggregate token usage from assistant messages
                        if msg.token_usage:
                            tu = msg.token_usage
                            token_stats['input'] += tu.input_tokens
                            token_stats['output'] += tu.output_tokens
                            token_stats['cache_read'] += tu.cache_read_tokens
                            token_stats['cache_create'] += tu.cache_creation_tokens
                            token_stats['total'] += tu.total_tokens
                            if tu.model:
                                # Simplify model name for display
                                model_short = tu.model.split('-')[1] if '-' in tu.model else tu.model
                                token_stats['models'][model_short] += tu.total_tokens

    # Filter to requested year
    year_sessions = [s for s in all_sessions if s.start_time and s.start_time.year == year]

    if not year_sessions:
        raise ValueError(f"No Claude Code activity found for {year}")

    # Group by project for the year
    year_project_sessions: Dict[str, List[SessionInfoV3]] = defaultdict(list)
    for s in year_sessions:
        year_project_sessions[s.project_name].append(s)

    # Calculate project stats
    project_stats: List[ProjectStatsV3] = []
    for proj_name, sessions in year_project_sessions.items():
        messages = sum(s.message_count for s in sessions)
        hours = round(sum(s.duration_minutes for s in sessions) / 60)  # Integer hours
        agent_count = len([s for s in sessions if s.is_agent])
        main_count = len([s for s in sessions if not s.is_agent])
        dates = sorted([s.start_time.date() for s in sessions if s.start_time])
        days_active = len(set(dates))
        first_day = dates[0].timetuple().tm_yday if dates else 1
        last_day = dates[-1].timetuple().tm_yday if dates else 1

        project_stats.append(ProjectStatsV3(
            name=proj_name[:MAX_PROJECT_NAME_LENGTH],
            path=sessions[0].project_path if sessions else "",
            message_count=messages,
            agent_sessions=agent_count,
            main_sessions=main_count,
            hours=hours,
            days_active=days_active,
            first_day=first_day,
            last_day=last_day,
        ))

    # Sort by messages and limit
    project_stats.sort(key=lambda p: p.message_count, reverse=True)
    top_projects = project_stats[:MAX_PROJECTS]
    project_names = [p.name for p in top_projects]

    # Core counts
    total_sessions = len(year_sessions)
    total_messages = sum(s.message_count for s in year_sessions)
    total_hours = round(sum(s.duration_minutes for s in year_sessions) / 60)  # Integer hours
    active_dates = {s.start_time.date() for s in year_sessions if s.start_time}
    days_active = len(active_dates)

    # Compute heatmap
    heatmap = compute_activity_heatmap(year_sessions)

    # Monthly arrays
    monthly_activity = [0] * 12
    monthly_hours_float = [0.0] * 12  # Accumulate as floats first
    monthly_sessions = [0] * 12
    for s in year_sessions:
        if s.start_time:
            month_idx = s.start_time.month - 1
            monthly_activity[month_idx] += s.message_count
            monthly_hours_float[month_idx] += s.duration_minutes / 60
            monthly_sessions[month_idx] += 1
    monthly_hours = [round(h) for h in monthly_hours_float]  # Convert to integers

    # Distributions
    session_duration_dist = compute_session_duration_distribution(year_sessions)
    agent_ratio_dist = compute_agent_ratio_distribution(top_projects)
    message_length_dist = compute_message_length_distribution(all_message_lengths)

    # Trait scores (with tool diversity from actual tool usage)
    trait_scores = compute_trait_scores(
        year_sessions, top_projects, heatmap, len(all_unique_tools)
    )

    # Project data for tp array (compact format: [name, messages, hours, days, sessions, agent_ratio])
    tp_data = []
    for p in top_projects:
        tp_data.append([
            p.name,
            p.message_count,
            p.hours,  # Already integer
            p.days_active,
            p.session_count,
            round(p.agent_ratio * 100),
        ])

    # Co-occurrence
    cooccurrence = compute_project_cooccurrence(year_sessions, project_names)

    # Timeline events
    events = detect_timeline_events(year_sessions, project_names, year)

    # Session fingerprints
    fingerprints = get_top_session_fingerprints(
        year_sessions,
        session_file_map,
        project_names
    )

    # Longest session
    session_durations = [s.duration_minutes / 60 for s in year_sessions if s.duration_minutes > 0]
    longest_session = max(session_durations) if session_durations else 0.0

    # Streak stats: [count, longest_days, current_days, avg_days]
    streak_stats = compute_streak_stats(active_dates, year)

    # Convert token models dict to regular dict for serialization
    token_stats['models'] = dict(token_stats['models'])

    # Year-over-year
    yoy = None
    if previous_year_data:
        yoy = {
            'pm': previous_year_data.get('messages', 0),
            'ph': previous_year_data.get('hours', 0),
            'ps': previous_year_data.get('sessions', 0),
            'pp': previous_year_data.get('projects', 0),
            'pd': previous_year_data.get('days', 0),
        }

    return WrappedStoryV3(
        v=WRAPPED_VERSION_V3,
        y=year,
        n=name[:MAX_DISPLAY_NAME_LENGTH] if name else None,
        p=len(year_project_sessions),
        s=total_sessions,
        m=total_messages,
        h=total_hours,
        d=days_active,
        hm=heatmap,
        ma=monthly_activity,
        mh=monthly_hours,
        ms=monthly_sessions,
        sd=session_duration_dist,
        ar=agent_ratio_dist,
        ml=message_length_dist,
        ts=trait_scores,
        tp=tp_data,
        pc=cooccurrence,
        te=events,
        sf=fingerprints,
        ls=longest_session,
        sk=streak_stats,
        tk=token_stats,
        yoy=yoy,
    )


# =============================================================================
# Thread Map - Visualization of session relationships
# =============================================================================

# Pattern names for compact encoding - MUST stay in sync with wrapped-website/src/decoder.ts
THREAD_MAP_PATTERNS = [
    "hub-and-spoke",  # 0: Main with 3+ agents
    "chain",          # 1: Sequential mains <30min apart
    "parallel",       # 2: Overlapping main sessions
    "deep",           # 3: Nested agents (depth 2+)
]

THREAD_MAP_VERSION = 1


@dataclass
class ThreadNode:
    """A node in the thread map representing a session.

    Attributes:
        id: Session ID (full or truncated)
        type: "main" or "agent"
        start: Session start timestamp
        end: Session end timestamp (may be None)
        messages: Total message count
        slug: Optional session title
        children: List of agent sessions spawned by this session
        depth: Nesting level (0 for main sessions)
    """
    id: str
    type: str  # "main" or "agent"
    start: datetime
    end: Optional[datetime]
    messages: int
    slug: Optional[str]
    children: List["ThreadNode"] = field(default_factory=list)
    depth: int = 0

    @property
    def duration_minutes(self) -> int:
        """Duration in minutes."""
        if self.start and self.end:
            return int((self.end - self.start).total_seconds() / 60)
        return 0

    @property
    def short_id(self) -> str:
        """Truncated ID for display."""
        return self.id[:8] if len(self.id) > 8 else self.id

    def to_compact(self) -> list:
        """Convert to compact list format for URL encoding.

        Format: [id, type, start_ts, end_ts, msgs, slug, [children]]
        """
        return [
            self.id[:8],  # Truncated ID
            0 if self.type == "main" else 1,
            int(self.start.timestamp()) if self.start else 0,
            int(self.end.timestamp()) if self.end else 0,
            self.messages,
            self.slug or "",
            [c.to_compact() for c in self.children],
        ]

    @classmethod
    def from_compact(cls, data: list, depth: int = 0) -> "ThreadNode":
        """Create from compact list format."""
        children = [cls.from_compact(c, depth + 1) for c in data[6]] if data[6] else []
        return cls(
            id=data[0],
            type="main" if data[1] == 0 else "agent",
            start=datetime.fromtimestamp(data[2]) if data[2] else None,
            end=datetime.fromtimestamp(data[3]) if data[3] else None,
            messages=data[4],
            slug=data[5] if data[5] else None,
            children=children,
            depth=depth,
        )


@dataclass
class ThreadMapStats:
    """Aggregate statistics for a thread map.

    Attributes:
        total_sessions: Total number of sessions
        main_sessions: Number of main sessions
        agent_sessions: Number of agent sessions
        max_depth: Deepest nesting level
        max_concurrent: Peak parallel sessions
        avg_agents_per_main: Average agents spawned per main session
        total_messages: Sum of all messages
        total_hours: Total development time
    """
    total_sessions: int
    main_sessions: int
    agent_sessions: int
    max_depth: int
    max_concurrent: int
    avg_agents_per_main: float
    total_messages: int
    total_hours: float

    def to_compact(self) -> dict:
        """Convert to compact dict for URL encoding."""
        return {
            "ts": self.total_sessions,
            "ms": self.main_sessions,
            "as": self.agent_sessions,
            "md": self.max_depth,
            "mc": self.max_concurrent,
            "aa": round(self.avg_agents_per_main, 1),
            "tm": self.total_messages,
            "th": round(self.total_hours, 1),
        }

    @classmethod
    def from_compact(cls, data: dict) -> "ThreadMapStats":
        """Create from compact dict."""
        return cls(
            total_sessions=data.get("ts", 0),
            main_sessions=data.get("ms", 0),
            agent_sessions=data.get("as", 0),
            max_depth=data.get("md", 0),
            max_concurrent=data.get("mc", 0),
            avg_agents_per_main=data.get("aa", 0),
            total_messages=data.get("tm", 0),
            total_hours=data.get("th", 0),
        )


@dataclass
class ThreadMap:
    """Complete thread map for a project.

    Attributes:
        project: Project short name
        path: Full project path
        roots: Main sessions (tree roots)
        orphans: Agent sessions without identified parent
        patterns: Detected patterns (e.g., "hub-and-spoke")
        stats: Aggregate statistics
        timespan: (start, end) datetime tuple
    """
    project: str
    path: str
    roots: List[ThreadNode]
    orphans: List[ThreadNode]
    patterns: List[str]
    stats: ThreadMapStats
    timespan: Tuple[datetime, datetime]

    def to_dict(self) -> dict:
        """Convert to dictionary for URL encoding.

        Note: Full path is intentionally excluded for privacy.
        Only the project short name is included.
        """
        return {
            "v": THREAD_MAP_VERSION,
            "p": self.project,
            # "pa" (path) intentionally excluded for privacy
            "r": [r.to_compact() for r in self.roots],
            "o": [o.to_compact() for o in self.orphans],
            "pt": [THREAD_MAP_PATTERNS.index(p) for p in self.patterns if p in THREAD_MAP_PATTERNS],
            "st": self.stats.to_compact(),
            "ts": [
                int(self.timespan[0].timestamp()) if self.timespan[0] else 0,
                int(self.timespan[1].timestamp()) if self.timespan[1] else 0,
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ThreadMap":
        """Create from dictionary.

        Raises:
            ValueError: If the version is unsupported
        """
        # Check version compatibility
        version = data.get("v", 1)
        if version > THREAD_MAP_VERSION:
            raise ValueError(
                f"Unsupported thread map version {version}. "
                f"Please update claude-history-explorer to decode this data."
            )

        roots = [ThreadNode.from_compact(r) for r in data.get("r", [])]
        orphans = [ThreadNode.from_compact(o) for o in data.get("o", [])]
        pattern_indices = data.get("pt", [])
        patterns = [THREAD_MAP_PATTERNS[i] for i in pattern_indices if 0 <= i < len(THREAD_MAP_PATTERNS)]
        ts = data.get("ts", [0, 0])

        return cls(
            project=data.get("p", ""),
            path=data.get("pa", ""),  # May be empty for privacy
            roots=roots,
            orphans=orphans,
            patterns=patterns,
            stats=ThreadMapStats.from_compact(data.get("st", {})),
            timespan=(
                datetime.fromtimestamp(ts[0]) if ts[0] else datetime.now(),
                datetime.fromtimestamp(ts[1]) if ts[1] else datetime.now(),
            ),
        )


def _find_parent_session(
    agent: SessionInfo,
    main_sessions: List[SessionInfo],
    buffer_minutes: int = 5
) -> Optional[SessionInfo]:
    """Find the most likely parent main session for an agent.

    Uses temporal overlap: agent must start during main session's duration
    (with a small buffer for timing variations).

    Args:
        agent: The agent session to find a parent for
        main_sessions: List of main sessions to search
        buffer_minutes: Grace period after main session ends

    Returns:
        The most likely parent session, or None if not found
    """
    # Agent must have a start time to find a parent
    if not agent.start_time:
        return None

    candidates = []

    for main in main_sessions:
        if not main.start_time:
            continue

        main_end = main.end_time or main.start_time + timedelta(hours=24)
        buffered_end = main_end + timedelta(minutes=buffer_minutes)

        # Agent must start after main starts and before main ends (with buffer)
        if main.start_time <= agent.start_time <= buffered_end:
            # Score by how close the start times are
            time_diff = abs((agent.start_time - main.start_time).total_seconds())
            candidates.append((main, time_diff))

    if not candidates:
        return None

    # Return the candidate with the closest start time
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


def _detect_patterns(
    roots: List[ThreadNode],
    main_sessions: List[SessionInfo]
) -> List[str]:
    """Detect thread patterns in the session data.

    Patterns detected:
    - hub-and-spoke: Main session with 3+ agents
    - chain: Sequential main sessions <30min apart
    - parallel: Overlapping main sessions
    - deep: Nested agents (depth 2+)

    Args:
        roots: List of root ThreadNodes
        main_sessions: List of main SessionInfo objects

    Returns:
        List of detected pattern names

    Performance:
        - Hub-and-spoke: O(r) where r = number of roots
        - Chain: O(n log n) for sort + O(n) scan = O(n log n)
        - Parallel: O(n) using max end time tracking (improved from O(n²))
        - Deep: O(total nodes) tree traversal
    """
    patterns = []

    # Hub-and-spoke: main with 3+ agents - O(r)
    for root in roots:
        if len(root.children) >= 3:
            patterns.append("hub-and-spoke")
            break

    # Sort once for both chain and parallel detection - O(n log n)
    if len(main_sessions) >= 2:
        sorted_mains = sorted(main_sessions, key=lambda x: x.start_time)

        # Chain: sequential mains <30min apart - O(n)
        for i in range(1, len(sorted_mains)):
            prev = sorted_mains[i - 1]
            curr = sorted_mains[i]
            if prev.end_time and curr.start_time:
                gap = (curr.start_time - prev.end_time).total_seconds() / 60
                if 0 < gap < 30:
                    patterns.append("chain")
                    break

        # Parallel: overlapping mains - O(n) using sweep line approach
        # Track the maximum end time seen so far; if any session starts
        # before this max end time, we have an overlap
        max_end_time = None
        for session in sorted_mains:
            if max_end_time and session.start_time and session.start_time < max_end_time:
                patterns.append("parallel")
                break
            if session.end_time:
                if max_end_time is None or session.end_time > max_end_time:
                    max_end_time = session.end_time

    # Deep: nested agents - O(total nodes)
    def check_depth(node: ThreadNode) -> int:
        if not node.children:
            return node.depth
        return max(check_depth(c) for c in node.children)

    for root in roots:
        if check_depth(root) >= 2:
            patterns.append("deep")
            break

    return list(set(patterns))  # Deduplicate


def _calculate_max_concurrent(sessions: List[SessionInfo]) -> int:
    """Calculate maximum number of concurrent sessions.

    Args:
        sessions: List of all sessions

    Returns:
        Maximum number of sessions active at the same time
    """
    if not sessions:
        return 0

    events = []
    for s in sessions:
        if s.start_time:
            events.append((s.start_time, 1))  # Session start
            if s.end_time:
                events.append((s.end_time, -1))  # Session end
            else:
                # Assume 1 hour if no end time
                events.append((s.start_time + timedelta(hours=1), -1))

    events.sort(key=lambda x: (x[0], -x[1]))  # Sort by time, ends before starts

    max_concurrent = 0
    current = 0
    for _, delta in events:
        current += delta
        max_concurrent = max(max_concurrent, current)

    return max_concurrent


def build_thread_map(project: Project, days: Optional[int] = None) -> ThreadMap:
    """Build a thread map for a project.

    Parses all sessions, identifies parent-child relationships between
    main and agent sessions, and detects patterns.

    Args:
        project: Project to analyze
        days: Optional limit to last N days (default: all sessions)

    Returns:
        ThreadMap with session hierarchy and patterns

    Raises:
        ValueError: If no sessions found
    """
    all_sessions = collect_sessions(project)

    if not all_sessions:
        raise ValueError(f"No sessions found for project {project.path}")

    # Filter by days if specified
    if days:
        cutoff = datetime.now(all_sessions[0].start_time.tzinfo) - timedelta(days=days)
        all_sessions = [s for s in all_sessions if s.start_time and s.start_time >= cutoff]

    if not all_sessions:
        raise ValueError(f"No sessions in the last {days} days for project {project.path}")

    # Separate main and agent sessions
    main_sessions = [s for s in all_sessions if not s.is_agent]
    agent_sessions = [s for s in all_sessions if s.is_agent]

    # Sort by start time
    main_sessions.sort(key=lambda x: x.start_time)
    agent_sessions.sort(key=lambda x: x.start_time)

    # Build parent-child relationships
    session_to_node: Dict[str, ThreadNode] = {}
    orphans: List[ThreadNode] = []

    # Create nodes for main sessions
    roots: List[ThreadNode] = []
    for main in main_sessions:
        node = ThreadNode(
            id=main.session_id,
            type="main",
            start=main.start_time,
            end=main.end_time,
            messages=main.message_count,
            slug=main.slug,
            depth=0,
        )
        roots.append(node)
        session_to_node[main.session_id] = node

    # Assign agents to parents
    for agent in agent_sessions:
        parent = _find_parent_session(agent, main_sessions)
        agent_node = ThreadNode(
            id=agent.session_id,
            type="agent",
            start=agent.start_time,
            end=agent.end_time,
            messages=agent.message_count,
            slug=agent.slug,
            depth=1,
        )

        if parent and parent.session_id in session_to_node:
            parent_node = session_to_node[parent.session_id]
            parent_node.children.append(agent_node)
            agent_node.depth = parent_node.depth + 1
        else:
            orphans.append(agent_node)

    # Sort children by start time
    for root in roots:
        root.children.sort(key=lambda x: x.start if x.start else datetime.min)

    # Detect patterns
    patterns = _detect_patterns(roots, main_sessions)

    # Calculate stats
    def count_depth(node: ThreadNode) -> int:
        if not node.children:
            return node.depth
        return max(count_depth(c) for c in node.children)

    max_depth = max((count_depth(r) for r in roots), default=0)

    total_agents = len(agent_sessions)
    avg_agents = total_agents / len(main_sessions) if main_sessions else 0

    total_messages = sum(s.message_count for s in all_sessions)
    total_hours = sum(s.duration_minutes for s in all_sessions) / 60

    stats = ThreadMapStats(
        total_sessions=len(all_sessions),
        main_sessions=len(main_sessions),
        agent_sessions=total_agents,
        max_depth=max_depth,
        max_concurrent=_calculate_max_concurrent(all_sessions),
        avg_agents_per_main=avg_agents,
        total_messages=total_messages,
        total_hours=total_hours,
    )

    # Calculate timespan
    all_starts = [s.start_time for s in all_sessions if s.start_time]
    all_ends = [s.end_time for s in all_sessions if s.end_time]
    timespan = (
        min(all_starts) if all_starts else datetime.now(),
        max(all_ends) if all_ends else datetime.now(),
    )

    return ThreadMap(
        project=project.short_name,
        path=project.path,
        roots=roots,
        orphans=orphans,
        patterns=patterns,
        stats=stats,
        timespan=timespan,
    )


def encode_thread_map(thread_map: ThreadMap) -> str:
    """Encode a ThreadMap to a URL-safe string.

    Uses MessagePack for compact binary representation, then Base64URL encoding.

    Args:
        thread_map: ThreadMap to encode

    Returns:
        URL-safe encoded string
    """
    import base64
    import msgpack

    data = thread_map.to_dict()
    packed = msgpack.packb(data, use_bin_type=True)
    encoded = base64.urlsafe_b64encode(packed).rstrip(b"=").decode("ascii")
    return encoded


def decode_thread_map(encoded: str) -> ThreadMap:
    """Decode a URL-safe string to a ThreadMap.

    Args:
        encoded: URL-safe encoded string

    Returns:
        ThreadMap object

    Raises:
        ValueError: If decoding fails
    """
    import base64
    import msgpack

    try:
        padding_needed = (4 - len(encoded) % 4) % 4
        padded = encoded + "=" * padding_needed
        packed = base64.urlsafe_b64decode(padded)
        data = msgpack.unpackb(packed, raw=False, strict_map_key=False)
        return ThreadMap.from_dict(data)
    except Exception as e:
        raise ValueError(f"Failed to decode thread map: {e}")
