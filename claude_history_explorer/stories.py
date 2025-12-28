"""Narrative generation functions for Claude Code History Explorer.

This module provides functions to generate development narratives:
- generate_project_story(): Generate insights about a project's journey
- generate_global_story(): Generate aggregated insights across all projects
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

from .constants import (
    ACTIVITY_INTENSITY_HIGH,
    ACTIVITY_INTENSITY_MEDIUM,
    AGENT_RATIO_BALANCED,
    AGENT_RATIO_HIGH,
    CONCURRENT_WINDOW_MINUTES,
    MESSAGE_RATE_HIGH,
    MESSAGE_RATE_LOW,
    MESSAGE_RATE_MEDIUM,
    SESSION_LENGTH_EXTENDED,
    SESSION_LENGTH_LONG,
    SESSION_LENGTH_STANDARD,
)
from .models import GlobalStory, Project, ProjectStory, SessionInfo
from .parser import parse_session
from .projects import list_projects
from .utils import classify


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
    sessions: List[SessionInfo] = []
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
    daily_activity: Dict[datetime, int] = defaultdict(int)
    for session in sessions:
        day = session.start_time.date()
        daily_activity[day] += session.message_count

    # Find peak day and break periods
    peak_day = None
    break_periods: List[tuple] = []

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
                # Check if sessions overlap (suggests concurrent use)
                time_diff = abs(
                    (session1.start_time - session2.start_time).total_seconds() / 60
                )
                if time_diff < CONCURRENT_WINDOW_MINUTES:
                    overlapping_sessions += 1

        if overlapping_sessions > 2:  # Session overlaps with 2+ others
            concurrent_claude_instances = max(
                concurrent_claude_instances, overlapping_sessions
            )

    # Generate insights about concurrent usage
    concurrent_insights: List[str] = []
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
    personality_traits: List[str] = []

    # Agent ratio trait
    agent_ratio_value = agent_sessions / len(sessions) if sessions else 0.0
    personality_traits.append(
        classify(
            agent_ratio_value,
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
    insights: List[str] = []
    insights.append(f"Most productive session: {most_productive.message_count} messages")

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
    project_stories: List[ProjectStory] = []

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
    total_sessions_all = sum(
        s.agent_sessions + s.main_sessions for s in project_stories
    )
    avg_agent_ratio = (
        sum(s.agent_sessions for s in project_stories) / total_sessions_all
        if total_sessions_all > 0
        else 0.0
    )
    avg_session_length = (
        sum(s.avg_session_hours for s in project_stories) / total_projects
        if total_projects > 0
        else 0.0
    )

    # Most common traits
    all_traits: List[str] = []
    for story in project_stories:
        all_traits.extend(story.personality_traits)

    common_traits = Counter(all_traits).most_common(3)

    # Project switching patterns
    recent_activity: List[tuple] = []
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
