"""Statistics calculation functions for Claude Code History Explorer.

This module provides functions to calculate usage statistics:
- calculate_project_stats(): Calculate detailed stats for a single project
- calculate_global_stats(): Calculate aggregated stats across all projects
"""

from typing import List, Optional

from .models import GlobalStats, Project, ProjectStats
from .parser import parse_session
from .projects import find_project, list_projects
from .utils import format_duration


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

        # Duration - use active duration (gaps capped)
        duration = session.active_duration_minutes
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
        projects: List[ProjectStats] = [calculate_project_stats(project)]
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
