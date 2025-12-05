"""Core module for reading and parsing Claude Code history files."""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional


def get_claude_dir() -> Path:
    """Get the Claude Code data directory."""
    return Path.home() / ".claude"


def get_projects_dir() -> Path:
    """Get the projects directory where conversation history is stored."""
    return get_claude_dir() / "projects"


@dataclass
class Message:
    """A single message in a conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[datetime] = None
    tool_uses: list = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict) -> Optional["Message"]:
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
                        tool_uses.append({
                            "name": item.get("name", "unknown"),
                            "input": item.get("input", {})
                        })
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
                timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        content = "\n".join(content_parts).strip()

        # Skip empty messages and tool result messages
        if not content and not tool_uses:
            return None

        return cls(role=role, content=content, timestamp=timestamp, tool_uses=tool_uses)


@dataclass
class Session:
    """A conversation session."""
    session_id: str
    project_path: str
    file_path: Path
    messages: list[Message] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    slug: Optional[str] = None

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def user_message_count(self) -> int:
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
    """A Claude Code project."""
    name: str
    path: str
    dir_path: Path
    session_files: list[Path] = field(default_factory=list)

    @classmethod
    def from_dir(cls, dir_path: Path) -> "Project":
        """Create a Project from a directory path."""
        name = dir_path.name
        # Decode the path: -Users-foo-bar -> /Users/foo/bar
        decoded_path = "/" + name.lstrip("-").replace("-", "/")

        session_files = sorted(
            dir_path.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        return cls(
            name=name,
            path=decoded_path,
            dir_path=dir_path,
            session_files=session_files
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
    """List all Claude Code projects."""
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
    """Find a project by name or path substring."""
    projects = list_projects()
    search_lower = search.lower()

    for project in projects:
        if search_lower in project.path.lower() or search_lower in project.name.lower():
            return project
    return None


def parse_session(file_path: Path, project_path: str = "") -> Session:
    """Parse a session file into a Session object."""
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
        slug=slug
    )


def search_sessions(
    pattern: str,
    project: Optional[Project] = None,
    case_sensitive: bool = False
) -> Iterator[tuple[Session, list[Message]]]:
    """Search for a pattern across sessions."""

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


def get_session_by_id(session_id: str, project: Optional[Project] = None) -> Optional[Session]:
    """Get a specific session by ID."""
    if project:
        projects = [project]
    else:
        projects = list_projects()

    for proj in projects:
        for session_file in proj.session_files:
            if session_file.stem == session_id or session_id in session_file.stem:
                return parse_session(session_file, proj.path)

    return None
