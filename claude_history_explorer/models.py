"""Data models for Claude Code History Explorer.

This module contains all dataclasses used throughout the package:
- Message, TokenUsage: Individual message representations
- Session, Project: Core data structures
- SessionInfo, SessionInfoV3: Session metadata for analysis
- ProjectStats, ProjectStatsV3, GlobalStats: Statistics containers
- ProjectStory, GlobalStory: Narrative analysis structures
- WrappedStoryV3: Rich visualization data for wrapped feature
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import ACTIVITY_GAP_CAP_MINUTES

# V3 encoding constants (used by WrappedStoryV3)
WRAPPED_VERSION_V3 = 3
MAX_PROJECT_NAME_LENGTH = 50
MAX_DISPLAY_NAME_LENGTH = 30


def _format_duration(minutes: int) -> str:
    """Format a duration in minutes as a human-readable string.

    This is a local helper to avoid circular imports with utils.py.

    Args:
        minutes: Duration in minutes

    Returns:
        Formatted string like "45m" or "2h 30m"
    """
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def _active_duration_minutes(
    messages: List["Message"], max_gap_minutes: int = ACTIVITY_GAP_CAP_MINUTES
) -> int:
    """Calculate active duration by summing gaps between messages, capping each gap.

    This is a local helper to avoid circular imports with utils.py.

    Args:
        messages: List of Message objects with timestamps
        max_gap_minutes: Maximum minutes to count for any single gap

    Returns:
        Active duration in minutes
    """
    timestamps = [m.timestamp for m in messages if m.timestamp is not None]
    if len(timestamps) < 2:
        return 0

    timestamps.sort()
    total_minutes = 0

    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i - 1]).total_seconds() / 60
        total_minutes += min(gap, max_gap_minutes)

    return int(total_minutes)


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

        message_data = data.get("message") or {}
        if not isinstance(message_data, dict):
            return None
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

        return cls(
            role=role,
            content=content,
            timestamp=timestamp,
            tool_uses=tool_uses,
            token_usage=token_usage,
        )


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
    def active_duration_minutes(self) -> int:
        """Active duration in minutes with gaps capped at ACTIVITY_GAP_CAP_MINUTES.

        Calculates duration by summing gaps between consecutive messages,
        capping each gap to avoid inflated durations from idle sessions.

        Returns:
            Duration in minutes, or 0 if insufficient timestamp data.
        """
        return _active_duration_minutes(self.messages)

    @property
    def duration_str(self) -> str:
        """Human-readable active duration (e.g., '2h 30m')."""
        minutes = self.active_duration_minutes
        if minutes > 0:
            return _format_duration(minutes)
        # Fallback for sessions without message timestamps
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return _format_duration(int(delta.total_seconds() / 60))
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

        # Use active duration (gaps capped) instead of raw duration
        duration = session.active_duration_minutes

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

        # Use active duration from Session property
        duration = session.active_duration_minutes

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
        work_type: Classified work type (coding, writing, analysis, research, teaching, design)

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
    work_type: str = "coding"

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    @property
    def total_duration_str(self) -> str:
        """Format total duration as readable string."""
        return _format_duration(self.total_duration_minutes)


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
    last_day: int  # Day of year (1-366)

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

    projects: List["ProjectStats"]
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
        return _format_duration(self.total_duration_minutes)


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
        concurrent_claude_instances: Maximum Claude instances used simultaneously
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
            "v": self.v,
            "y": self.y,
            "p": self.p,
            "s": self.s,
            "m": self.m,
            "h": self.h,  # Already integer
            "d": self.d,
            "hm": self.hm,
            "ma": self.ma,
            "mh": self.mh,  # Already integers
            "ms": self.ms,
            "sd": self.sd,
            "ar": self.ar,
            "ml": self.ml,
            "ts": self.ts,
            "tp": self.tp,
            "pc": self.pc,
            "te": self.te,
            "sf": self.sf,
            "ls": round(self.ls, 1),  # Round to 1 decimal for compactness
            "sk": self.sk,
            "tk": self.tk,
        }
        if self.n:
            result["n"] = self.n
        if self.yoy:
            result["yoy"] = self.yoy
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "WrappedStoryV3":
        """Create from dictionary."""
        return cls(
            v=d.get("v", WRAPPED_VERSION_V3),
            y=d.get("y", 0),
            n=d.get("n"),
            p=d.get("p", 0),
            s=d.get("s", 0),
            m=d.get("m", 0),
            h=d.get("h", 0),
            d=d.get("d", 0),
            hm=d.get("hm", []),
            ma=d.get("ma", []),
            mh=d.get("mh", []),
            ms=d.get("ms", []),
            sd=d.get("sd", []),
            ar=d.get("ar", []),
            ml=d.get("ml", []),
            ts=d.get("ts", {}),
            tp=d.get("tp", []),
            pc=[tuple(x) for x in d.get("pc", [])],
            te=d.get("te", []),
            sf=d.get("sf", []),
            ls=d.get("ls", 0.0),
            sk=d.get("sk", []),
            tk=d.get("tk", {}),
            yoy=d.get("yoy"),
        )
