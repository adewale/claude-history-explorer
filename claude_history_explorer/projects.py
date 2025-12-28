"""Project discovery functions for Claude Code History Explorer.

This module provides functions to locate and list Claude Code projects:
- get_claude_dir(): Get the ~/.claude directory path
- get_projects_dir(): Get the ~/.claude/projects directory path
- list_projects(): Discover all projects sorted by last modified
- find_project(): Find a specific project by name/path search
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Project


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


def list_projects() -> List[Project]:
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
