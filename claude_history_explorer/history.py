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
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional, Dict, List


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
        """Parse a message from JSONL data."""
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
                    elif item.get("type") == "tool_result":
                        # Skip tool results in content display
                        pass

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
            if minutes < 60:
                return f"{minutes}m"
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h {mins}m"
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
        total_minutes = self.total_duration_minutes
        if total_minutes < 60:
            return f"{total_minutes}m"
        hours = total_minutes // 60
        mins = total_minutes % 60
        return f"{hours}h {mins}m"


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
        total_minutes = self.total_duration_minutes
        if total_minutes < 60:
            return f"{total_minutes}m"
        hours = total_minutes // 60
        mins = total_minutes % 60
        return f"{hours}h {mins}m"


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
    longest_session_id = ""
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
            duration_minutes = int(
                (session.end_time - session.start_time).total_seconds() / 60
            )
            total_duration_minutes += duration_minutes
            if duration_minutes > longest_duration_minutes:
                longest_duration_minutes = duration_minutes
                longest_session_id = session.session_id

        # Most recent session
        if session.start_time:
            if most_recent_session is None or session.start_time > most_recent_session:
                most_recent_session = session.start_time

    avg_messages = (
        total_messages / project.session_count if project.session_count > 0 else 0
    )

    # Format longest duration
    if longest_duration_minutes < 60:
        longest_duration_str = f"{longest_duration_minutes}m"
    else:
        hours = longest_duration_minutes // 60
        mins = longest_duration_minutes % 60
        longest_duration_str = f"{hours}h {mins}m"

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
        longest_session_duration=longest_duration_str,
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
        most_productive_session: Dict with session details
        daily_engagement: Description of engagement pattern
        insights: List of key insight strings
        daily_activity: Dict mapping dates to message counts (for sparklines)
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
    most_productive_session: dict
    daily_engagement: str
    insights: List[str]
    daily_activity: Dict[datetime, int] = field(default_factory=dict)


def generate_project_story(
    project: Project, format_type: str = "detailed"
) -> ProjectStory:
    """Generate narrative insights about a project's development journey.

    Analyzes session patterns to determine work style, collaboration patterns,
    and development personality traits.

    Args:
        project: Project to analyze
        format_type: Output format hint (doesn't affect data, just for context)

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
    sessions = []
    for session_file in project.session_files:
        session = parse_session(session_file, project.path)
        if session.start_time:
            sessions.append(
                {
                    "session_id": session.session_id,
                    "start_time": session.start_time,
                    "end_time": session.end_time,
                    "duration_minutes": int(
                        (session.end_time - session.start_time).total_seconds() / 60
                    )
                    if session.end_time
                    else 0,
                    "message_count": session.message_count,
                    "user_message_count": session.user_message_count,
                    "is_agent": session_file.name.startswith("agent-"),
                    "slug": session.slug,
                }
            )

    if not sessions:
        raise ValueError(f"No sessions found for project {project.path}")

    sessions.sort(key=lambda x: x["start_time"])

    # Basic lifecycle data
    first_session = sessions[0]
    last_session = sessions[-1]
    lifecycle_days = (last_session["start_time"] - first_session["start_time"]).days + 1

    # Daily activity analysis
    daily_activity = defaultdict(int)
    for session in sessions:
        day = session["start_time"].date()
        daily_activity[day] += session["message_count"]

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

    # Agent collaboration analysis
    agent_sessions = len([s for s in sessions if s["is_agent"]])
    main_sessions = len([s for s in sessions if not s["is_agent"]])

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
    total_messages = sum(s["message_count"] for s in sessions)
    total_dev_time = sum(s["duration_minutes"] for s in sessions) / 60
    message_rate = total_messages / total_dev_time if total_dev_time > 0 else 0

    if message_rate > 30:
        work_pace = "Rapid-fire development"
    elif message_rate > 20:
        work_pace = "Steady, productive flow"
    elif message_rate > 10:
        work_pace = "Deliberate, thoughtful work"
    else:
        work_pace = "Careful, methodical development"

    # Session patterns
    session_lengths = [
        s["duration_minutes"] for s in sessions if s["duration_minutes"] > 0
    ]
    avg_session_hours = (
        sum(session_lengths) / len(session_lengths) / 60 if session_lengths else 0
    )
    longest_session_hours = max(session_lengths) / 60 if session_lengths else 0

    if avg_session_hours > 2:
        session_style = "Marathon sessions (deep, focused work)"
    elif avg_session_hours > 1:
        session_style = "Extended sessions (sustained effort)"
    elif avg_session_hours > 0.5:
        session_style = "Standard sessions (balanced approach)"
    else:
        session_style = "Quick sprints (iterative development)"

    # Personality traits
    personality_traits = []

    if agent_sessions / len(sessions) > 0.8:
        personality_traits.append("Agent-driven")
    elif agent_sessions / len(sessions) > 0.5:
        personality_traits.append("Collaborative")
    else:
        personality_traits.append("Hands-on")

    if avg_session_hours > 2:
        personality_traits.append("Deep-work focused")
    elif avg_session_hours > 1:
        personality_traits.append("Steady-paced")
    else:
        personality_traits.append("Quick-iterative")

    if total_messages / lifecycle_days > 300:
        personality_traits.append("High-intensity")
    elif total_messages / lifecycle_days > 100:
        personality_traits.append("Moderately active")
    else:
        personality_traits.append("Deliberate")

    # Most productive session
    most_productive = max(sessions, key=lambda x: x["message_count"])

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
        f"Most productive session: {most_productive['message_count']} messages"
    )

    if agent_sessions and main_sessions:
        agent_efficiency = (
            sum(s["message_count"] for s in sessions if s["is_agent"]) / agent_sessions
        )
        main_efficiency = (
            sum(s["message_count"] for s in sessions if not s["is_agent"])
            / main_sessions
        )

        if agent_efficiency > main_efficiency:
            insights.append("Agent sessions are more efficient than main sessions")
        else:
            insights.append("Main sessions drive most of the progress")

    insights.append(daily_engagement)

    return ProjectStory(
        project_name=project.path.split("/")[-1],
        project_path=project.path,
        lifecycle_days=lifecycle_days,
        birth_date=first_session["start_time"],
        last_active=last_session["start_time"],
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
        insights=insights,
        daily_activity=dict(daily_activity),
    )


def generate_global_story() -> dict:
    """Generate a narrative story across all projects.

    Aggregates project stories and identifies common patterns
    and personality traits across the entire development history.

    Returns:
        Dictionary containing:
            - total_projects: Number of projects
            - total_messages: Sum of all messages
            - total_dev_time: Total hours of development
            - avg_agent_ratio: Average agent collaboration ratio
            - avg_session_length: Average session length in hours
            - common_traits: List of (trait, count) tuples
            - project_stories: List of ProjectStory objects
            - recent_activity: List of (timestamp, project_name) tuples

    Raises:
        ValueError: If no projects with sessions are found

    Example:
        >>> story = generate_global_story()
        >>> print(f"{story['total_projects']} projects analyzed")
    """
    all_projects = list_projects()
    project_stories = []

    for project in all_projects:
        try:
            story = generate_project_story(project, "brief")
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

    from collections import Counter

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

    return {
        "total_projects": total_projects,
        "total_messages": total_messages,
        "total_dev_time": total_dev_time,
        "avg_agent_ratio": avg_agent_ratio,
        "avg_session_length": avg_session_length,
        "common_traits": common_traits,
        "project_stories": project_stories,
        "recent_activity": recent_activity,
    }
