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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional, Dict, List

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
    "Project",
    "ProjectStats",
    "GlobalStats",
    "ProjectStory",
    "GlobalStory",
    "WrappedStory",
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
    # Wrapped functions
    "generate_wrapped_story",
    "encode_wrapped_story",
    "decode_wrapped_story",
    "filter_sessions_by_year",
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
class Message:
    """A single message in a conversation.

    Attributes:
        role: Either 'user' or 'assistant'
        content: The text content of the message
        timestamp: When the message was sent (may be None)
        tool_uses: List of tools used by assistant (name and input)

    Example:
        >>> msg = Message(role="user", content="Hello")
        >>> msg.role
        'user'
    """

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[datetime] = None
    tool_uses: list = field(default_factory=list)

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

        return cls(role=role, content=content, timestamp=timestamp, tool_uses=tool_uses)


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
        # Decode the path: -Users-foo-bar -> /Users/foo/bar
        decoded_path = "/" + name.lstrip("-").replace("-", "/")

        session_files = sorted(
            dir_path.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
        )

        return cls(
            name=name, path=decoded_path, dir_path=dir_path, session_files=session_files
        )

    @property
    def session_count(self) -> int:
        return len(self.session_files)

    @property
    def short_name(self) -> str:
        """Get the short name (last path component) of the project."""
        return self.path.split("/")[-1]

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
    # Collect all sessions
    sessions: list[SessionInfo] = []
    for session_file in project.session_files:
        session = parse_session(session_file, project.path)
        is_agent = session_file.name.startswith("agent-")
        info = SessionInfo.from_session(session, is_agent)
        if info is not None:
            sessions.append(info)

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
# Wrapped Story - Shareable year-in-review feature
# =============================================================================


# Wrapped URL encoding dictionaries - indices are used in URLs for compactness
# These MUST stay in sync with wrapped-website/src/decoder.ts
WRAPPED_TRAITS = [
    "Agent-driven",      # 0
    "Collaborative",     # 1
    "Hands-on",          # 2
    "Deep-work focused", # 3
    "Steady-paced",      # 4
    "Quick-iterative",   # 5
    "High-intensity",    # 6
    "Moderately active", # 7
    "Deliberate",        # 8
]

WRAPPED_COLLAB_STYLES = [
    "Heavy delegation",  # 0
    "Balanced",          # 1
    "Hands-on",          # 2
    "Agent-only",        # 3
]

WRAPPED_WORK_PACES = [
    "Rapid-fire",        # 0
    "Steady",            # 1
    "Deliberate",        # 2
    "Methodical",        # 3
]

# Current encoding version - increment when format changes
WRAPPED_VERSION = 2


@dataclass
class WrappedStory:
    """Compact, shareable summary of Claude Code usage for a year.

    This dataclass is designed to be serialized to a compact format (MessagePack)
    and encoded in a URL. All field names are single characters to minimize size.

    Version 2 encoding uses indices for traits/styles/paces to save ~50 bytes.

    Attributes:
        y: Year (e.g., 2025)
        n: Display name (optional)
        p: Total projects with activity
        s: Total sessions
        m: Total messages
        h: Total hours of development
        t: Personality traits (max 3) - stored as indices in v2
        c: Collaboration style - stored as index in v2
        w: Work pace - stored as index in v2
        pp: Peak project name
        pm: Peak project messages
        ci: Max concurrent Claude instances
        ls: Longest session (hours)
        a: Monthly activity (12 values, Jan-Dec)
        tp: Top 3 projects [{n: name, m: messages, d: days}]
    """

    y: int  # year
    p: int = 0  # projects
    s: int = 0  # sessions
    m: int = 0  # messages
    h: float = 0  # hours
    t: List[str] = field(default_factory=list)  # traits
    c: str = ""  # collaboration style
    w: str = ""  # work pace
    pp: str = ""  # peak project name
    pm: int = 0  # peak project messages
    ci: int = 0  # max concurrent instances
    ls: float = 0  # longest session hours
    a: List[int] = field(default_factory=list)  # monthly activity (12 values)
    tp: List[Dict[str, any]] = field(default_factory=list)  # top 3 projects
    n: Optional[str] = None  # display name

    def to_dict(self, use_indices: bool = True) -> dict:
        """Convert to dictionary for serialization.

        Args:
            use_indices: If True (default), encode traits/styles/paces as indices
                        for v2 compact format. If False, use full strings (v1).
        """
        # Encode traits as indices for compactness
        if use_indices:
            trait_indices = []
            for t in self.t:
                try:
                    trait_indices.append(WRAPPED_TRAITS.index(t))
                except ValueError:
                    trait_indices.append(t)  # Keep as string if not in dict

            try:
                collab_idx = WRAPPED_COLLAB_STYLES.index(self.c)
            except ValueError:
                collab_idx = self.c  # Keep as string if not in dict

            try:
                pace_idx = WRAPPED_WORK_PACES.index(self.w)
            except ValueError:
                pace_idx = self.w  # Keep as string if not in dict

            d = {
                "v": WRAPPED_VERSION,  # Version for forward compatibility
                "y": self.y,
                "p": self.p,
                "s": self.s,
                "m": self.m,
                "h": round(self.h, 1),
                "t": trait_indices,
                "c": collab_idx,
                "w": pace_idx,
                "pp": self.pp,
                "pm": self.pm,
                "ci": self.ci,
                "ls": round(self.ls, 1),
                "a": self.a,
                "tp": self.tp,
            }
        else:
            # V1 format with full strings
            d = {
                "y": self.y,
                "p": self.p,
                "s": self.s,
                "m": self.m,
                "h": round(self.h, 1),
                "t": self.t,
                "c": self.c,
                "w": self.w,
                "pp": self.pp,
                "pm": self.pm,
                "ci": self.ci,
                "ls": round(self.ls, 1),
                "a": self.a,
                "tp": self.tp,
            }
        if self.n:
            d["n"] = self.n
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WrappedStory":
        """Create from dictionary, handling both v1 (strings) and v2 (indices) formats."""
        version = d.get("v", 1)  # Default to v1 if no version

        # Decode traits
        raw_traits = d.get("t", [])
        if version >= 2:
            # V2: decode indices to strings
            traits = []
            for t in raw_traits:
                if isinstance(t, int) and 0 <= t < len(WRAPPED_TRAITS):
                    traits.append(WRAPPED_TRAITS[t])
                else:
                    traits.append(str(t))  # Keep as-is if not valid index
        else:
            traits = raw_traits

        # Decode collaboration style
        raw_collab = d.get("c", "")
        if version >= 2 and isinstance(raw_collab, int):
            if 0 <= raw_collab < len(WRAPPED_COLLAB_STYLES):
                collab = WRAPPED_COLLAB_STYLES[raw_collab]
            else:
                collab = str(raw_collab)
        else:
            collab = raw_collab

        # Decode work pace
        raw_pace = d.get("w", "")
        if version >= 2 and isinstance(raw_pace, int):
            if 0 <= raw_pace < len(WRAPPED_WORK_PACES):
                pace = WRAPPED_WORK_PACES[raw_pace]
            else:
                pace = str(raw_pace)
        else:
            pace = raw_pace

        return cls(
            y=d.get("y", 0),
            n=d.get("n"),
            p=d.get("p", 0),
            s=d.get("s", 0),
            m=d.get("m", 0),
            h=d.get("h", 0),
            t=traits,
            c=collab,
            w=pace,
            pp=d.get("pp", ""),
            pm=d.get("pm", 0),
            ci=d.get("ci", 0),
            ls=d.get("ls", 0),
            a=d.get("a", []),
            tp=d.get("tp", []),
        )


def filter_sessions_by_year(
    sessions: List[SessionInfo], year: int
) -> List[SessionInfo]:
    """Filter sessions to only those that started in the given year.

    Sessions spanning year boundaries (e.g., Dec 31 -> Jan 1) are
    assigned to their START year.

    Args:
        sessions: List of SessionInfo objects
        year: Year to filter for (e.g., 2025)

    Returns:
        List of sessions that started in the given year
    """
    return [s for s in sessions if s.start_time and s.start_time.year == year]


def encode_wrapped_story(story: WrappedStory) -> str:
    """Encode a WrappedStory to a URL-safe string.

    Uses MessagePack for compact binary representation, then Base64URL encoding.

    Args:
        story: WrappedStory to encode

    Returns:
        URL-safe encoded string
    """
    import base64
    import msgpack

    data = story.to_dict()
    packed = msgpack.packb(data, use_bin_type=True)
    # Use URL-safe base64 without padding
    encoded = base64.urlsafe_b64encode(packed).rstrip(b"=").decode("ascii")
    return encoded


def decode_wrapped_story(encoded: str) -> WrappedStory:
    """Decode a URL-safe string to a WrappedStory.

    Args:
        encoded: URL-safe encoded string

    Returns:
        WrappedStory object

    Raises:
        ValueError: If decoding fails
    """
    import base64
    import msgpack

    try:
        # Add padding if needed
        padding_needed = (4 - len(encoded) % 4) % 4
        padded = encoded + "=" * padding_needed
        packed = base64.urlsafe_b64decode(padded)
        data = msgpack.unpackb(packed, raw=False, strict_map_key=False)
        return WrappedStory.from_dict(data)
    except Exception as e:
        raise ValueError(f"Failed to decode wrapped story: {e}")


def generate_wrapped_story(year: int, name: Optional[str] = None) -> WrappedStory:
    """Generate a WrappedStory for a specific year.

    Analyzes all sessions from the given year and generates a compact
    summary suitable for sharing.

    Args:
        year: Year to generate wrapped for (e.g., 2025)
        name: Optional display name to include

    Returns:
        WrappedStory with aggregated stats for the year

    Raises:
        ValueError: If year is in the future or before Claude Code existed
    """
    current_year = datetime.now().year
    if year > current_year:
        raise ValueError(f"Cannot generate wrapped for future year {year}")
    if year < 2024:
        raise ValueError(f"Claude Code didn't exist in {year}")

    # Collect all sessions from all projects
    all_sessions: List[SessionInfo] = []
    project_sessions: Dict[str, List[SessionInfo]] = defaultdict(list)

    for project in list_projects():
        for session_file in project.session_files:
            session = parse_session(session_file, project.path)
            is_agent = session_file.name.startswith("agent-")
            info = SessionInfo.from_session(session, is_agent)
            if info is not None:
                all_sessions.append(info)
                project_sessions[project.short_name].append(info)

    # Filter to the requested year
    year_sessions = filter_sessions_by_year(all_sessions, year)

    if not year_sessions:
        raise ValueError(f"No Claude Code activity found for {year}")

    # Calculate stats
    total_sessions = len(year_sessions)
    total_messages = sum(s.message_count for s in year_sessions)
    total_hours = sum(s.duration_minutes for s in year_sessions) / 60

    # Monthly activity (12 values)
    monthly_activity = [0] * 12
    for s in year_sessions:
        if s.start_time:
            month_idx = s.start_time.month - 1
            monthly_activity[month_idx] += s.message_count

    # Projects with activity this year
    year_project_sessions: Dict[str, List[SessionInfo]] = defaultdict(list)
    for s in year_sessions:
        # Find which project this session belongs to
        for proj_name, proj_sessions in project_sessions.items():
            if any(ps.session_id == s.session_id for ps in proj_sessions):
                year_project_sessions[proj_name].append(s)
                break

    projects_with_activity = len(year_project_sessions)

    # Top 3 projects by message count
    project_stats = []
    for proj_name, sessions in year_project_sessions.items():
        proj_messages = sum(s.message_count for s in sessions)
        # Calculate days active
        if sessions:
            dates = {s.start_time.date() for s in sessions if s.start_time}
            days_active = len(dates)
        else:
            days_active = 0
        project_stats.append(
            {"n": proj_name, "m": proj_messages, "d": days_active}
        )

    project_stats.sort(key=lambda x: x["m"], reverse=True)
    top_projects = project_stats[:3]

    # Peak project
    peak_project = top_projects[0] if top_projects else {"n": "", "m": 0}

    # Longest session
    session_hours = [s.duration_minutes / 60 for s in year_sessions if s.duration_minutes > 0]
    longest_session = max(session_hours) if session_hours else 0

    # Concurrent instances detection
    concurrent_instances = 0
    for i, s1 in enumerate(year_sessions):
        overlapping = 0
        for j, s2 in enumerate(year_sessions):
            if i != j and s1.start_time and s2.start_time:
                time_diff = abs((s1.start_time - s2.start_time).total_seconds() / 60)
                if time_diff < 30:
                    overlapping += 1
        concurrent_instances = max(concurrent_instances, overlapping + 1)

    # Personality traits
    agent_sessions = len([s for s in year_sessions if s.is_agent])
    main_sessions = len([s for s in year_sessions if not s.is_agent])

    # Agent ratio trait
    agent_ratio = agent_sessions / len(year_sessions) if year_sessions else 0
    trait1 = classify(
        agent_ratio,
        [(AGENT_RATIO_HIGH, "Agent-driven"), (AGENT_RATIO_BALANCED, "Collaborative")],
        "Hands-on",
    )

    # Session length trait
    avg_session_hours = total_hours / total_sessions if total_sessions else 0
    trait2 = classify(
        avg_session_hours,
        [(SESSION_LENGTH_LONG, "Deep-work focused"), (SESSION_LENGTH_EXTENDED, "Steady-paced")],
        "Quick-iterative",
    )

    # Intensity trait
    # Calculate days active this year
    active_dates = {s.start_time.date() for s in year_sessions if s.start_time}
    days_active = len(active_dates) if active_dates else 1
    intensity = total_messages / days_active
    trait3 = classify(
        intensity,
        [(ACTIVITY_INTENSITY_HIGH, "High-intensity"), (ACTIVITY_INTENSITY_MEDIUM, "Moderately active")],
        "Deliberate",
    )

    traits = [trait1, trait2, trait3]

    # Collaboration style
    if main_sessions > 0:
        agent_ratio_val = agent_sessions / main_sessions
        if agent_ratio_val > 2:
            collab_style = "Heavy delegation"
        elif agent_ratio_val > 1:
            collab_style = "Balanced"
        else:
            collab_style = "Hands-on"
    else:
        collab_style = "Agent-only"

    # Work pace
    message_rate = total_messages / total_hours if total_hours > 0 else 0
    work_pace = classify(
        message_rate,
        [
            (MESSAGE_RATE_HIGH, "Rapid-fire"),
            (MESSAGE_RATE_MEDIUM, "Steady"),
            (MESSAGE_RATE_LOW, "Deliberate"),
        ],
        "Methodical",
    )

    return WrappedStory(
        y=year,
        n=name,
        p=projects_with_activity,
        s=total_sessions,
        m=total_messages,
        h=total_hours,
        t=traits,
        c=collab_style,
        w=work_pace,
        pp=peak_project["n"],
        pm=peak_project["m"],
        ci=concurrent_instances,
        ls=longest_session,
        a=monthly_activity,
        tp=top_projects,
    )
