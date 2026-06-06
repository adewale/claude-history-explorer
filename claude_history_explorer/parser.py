"""JSONL parsing functions for Claude Code History Explorer.

This module provides functions to parse Claude Code session files:
- parse_session(): Parse a JSONL file into a Session object
- get_session_by_id(): Retrieve a specific session by ID
- search_sessions(): Search across all conversations with regex
"""

import json
import logging
import re
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

from .models import Message, Project, Session
from .projects import list_projects
from .utils import _compile_regex_safe

MAX_LINE_BYTES = 10 * 1024 * 1024  # 10 MB


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
    messages: List[Message] = []
    start_time = None
    end_time = None
    slug = None

    lines_seen = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines_seen += 1
            if len(line) > MAX_LINE_BYTES:
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

    if lines_seen > 0 and not messages:
        logger.debug("No valid messages in %s (%d lines skipped)", file_path, lines_seen)

    return Session(
        session_id=session_id,
        project_path=project_path,
        file_path=file_path,
        messages=messages,
        start_time=start_time,
        end_time=end_time,
        slug=slug,
    )


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

    exact_match = None
    prefix_match = None
    for proj in projects:
        for session_file in proj.session_files:
            stem = session_file.stem
            if stem == session_id:
                exact_match = (session_file, proj)
                break
            if stem.startswith(session_id) and prefix_match is None:
                prefix_match = (session_file, proj)
        if exact_match:
            break

    hit = exact_match or prefix_match
    if hit:
        return parse_session(hit[0], hit[1].path)
    return None


def search_sessions(
    pattern: str, project: Optional[Project] = None, case_sensitive: bool = False
) -> Iterator[Tuple[Session, List[Message], "re.Pattern"]]:
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
    regex = _compile_regex_safe(pattern, flags)

    for proj in projects:
        for session_file in proj.session_files:
            session = parse_session(session_file, proj.path)
            matching_messages: List[Message] = []

            for msg in session.messages:
                matched = bool(regex.search(msg.content))
                # Also search tool inputs, but append each message at most once.
                if not matched:
                    for tool_use in msg.tool_uses:
                        tool_input = json.dumps(tool_use.get("input", {}))
                        if regex.search(tool_input):
                            matched = True
                            break
                if matched:
                    matching_messages.append(msg)

            if matching_messages:
                yield session, matching_messages, regex
