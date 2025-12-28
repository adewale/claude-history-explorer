"""V3 Wrapped format for Claude Code History Explorer.

This module provides functions for generating and encoding wrapped stories:
- generate_wrapped_story_v3(): Generate rich visualization data
- encode_wrapped_story_v3(): Encode story to URL-safe string
- decode_wrapped_story_v3(): Decode story from URL-safe string
- Various compute_* functions for metrics and distributions
"""

import json
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .constants import MILESTONE_VALUES
from .models import (
    MAX_DISPLAY_NAME_LENGTH,
    MAX_PROJECT_NAME_LENGTH,
    WRAPPED_VERSION_V3,
    ProjectStatsV3,
    Session,
    SessionInfoV3,
    WrappedStoryV3,
)
from .parser import parse_session
from .projects import list_projects

# Distribution bucket boundaries
SESSION_DURATION_BUCKETS = [15, 30, 60, 120, 240, 480, 720, 1440, 2880]  # minutes
AGENT_RATIO_BUCKETS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]  # 0-1
MESSAGE_LENGTH_BUCKETS = [50, 100, 200, 500, 1000, 2000, 5000]  # chars

# Event type indices
EVENT_TYPE_INDICES = {
    "peak_day": 0,
    "streak_start": 1,
    "streak_end": 2,
    "new_project": 3,
    "milestone": 4,
    "gap_start": 5,
    "gap_end": 6,
}

# Hard limits
MAX_PROJECTS = 12
MAX_COOCCURRENCE_EDGES = 20
MAX_TIMELINE_EVENTS = 25
MAX_SESSION_FINGERPRINTS = 20

# Heatmap quantization scale (0-15 for compact encoding)
HEATMAP_QUANT_SCALE = 15


def compute_activity_heatmap(sessions: List[SessionInfoV3]) -> List[int]:
    """Compute 7x24 activity heatmap from sessions.

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
    unique_tools_count: int = 0,
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
    scores: Dict[str, float] = {}

    # === AGENT DELEGATION (ad) ===
    # 0 = all hands-on, 1 = all agent
    total_sessions = len(sessions)
    agent_sessions = len([s for s in sessions if s.is_agent])
    scores["ad"] = agent_sessions / total_sessions if total_sessions > 0 else 0.5

    # === SESSION DEPTH PREFERENCE (sp) ===
    # 0 = median <15min, 1 = median >4 hours
    durations = sorted([s.duration_minutes for s in sessions if s.duration_minutes > 0])
    if durations:
        median_duration = durations[len(durations) // 2]
        scores["sp"] = min(1.0, median_duration / 240)  # 4 hours = 1.0
    else:
        scores["sp"] = 0.5

    # === FOCUS CONCENTRATION (fc) ===
    # Herfindahl-Hirschman Index: 1/n (even) to 1.0 (all in one project)
    if projects:
        total_messages = sum(p.message_count for p in projects)
        if total_messages > 0:
            hhi = sum((p.message_count / total_messages) ** 2 for p in projects)
            scores["fc"] = hhi
        else:
            scores["fc"] = 0.5
    else:
        scores["fc"] = 0.5

    # === CIRCADIAN CONSISTENCY (cc) ===
    # Low variance in start hours = high consistency
    start_hours = [s.start_time.hour for s in sessions if s.start_time]
    if len(start_hours) > 1:
        mean_hour = sum(start_hours) / len(start_hours)
        variance = sum((h - mean_hour) ** 2 for h in start_hours) / len(start_hours)
        # Variance of 36 (std=6 hours) = inconsistent
        scores["cc"] = max(0.0, 1 - variance / 36)
    else:
        scores["cc"] = 0.5

    # === WEEKEND RATIO (wr) ===
    # 0 = no weekend activity, 1 = 40%+ weekend (vs expected 28.6%)
    weekend_messages = sum(heatmap[5 * 24 : 7 * 24])  # Sat (5) + Sun (6)
    weekday_messages = sum(heatmap[0 : 5 * 24])  # Mon-Fri (0-4)
    total = weekend_messages + weekday_messages
    if total > 0:
        raw_ratio = weekend_messages / total
        scores["wr"] = min(1.0, raw_ratio / 0.4)  # 40% weekend = 1.0
    else:
        scores["wr"] = 0.0

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
            scores["bs"] = min(1.0, cv)  # CV > 1 = very bursty
        else:
            scores["bs"] = 0.5
    else:
        scores["bs"] = 0.5

    # === CONTEXT SWITCHING (cs) ===
    # Average unique projects per active day
    projects_per_day: Dict[datetime, Set[str]] = defaultdict(set)
    for s in sessions:
        if s.start_time and s.project_name:
            day_key = s.start_time.date()
            projects_per_day[day_key].add(s.project_name)

    if projects_per_day:
        avg_projects = sum(len(p) for p in projects_per_day.values()) / len(
            projects_per_day
        )
        # 1 project/day = 0, 4+ projects/day = 1
        scores["cs"] = min(1.0, max(0.0, (avg_projects - 1) / 3))
    else:
        scores["cs"] = 0.0

    # === MESSAGE RATE METRICS (shared for mv and ri) ===
    messages_per_hour = [
        s.message_count / max(0.1, s.duration_minutes / 60)
        for s in sessions
        if s.duration_minutes > 0
    ]
    if messages_per_hour:
        sorted_rates = sorted(messages_per_hour)
        median_rate = sorted_rates[len(sorted_rates) // 2]
    else:
        median_rate = 15.0  # Default middle value

    # === MESSAGE VERBOSITY (mv) ===
    # Inverse of message rate (high rate = short messages = low verbosity)
    # 30 msg/hr = terse (0), 5 msg/hr = verbose (1)
    scores["mv"] = max(0.0, min(1.0, 1 - median_rate / 30))

    # === TOOL DIVERSITY (td) ===
    # 0 = minimal tools (1-2), 1 = many tools (10+)
    # Claude Code has ~15-20 common tools, so 10+ indicates diverse usage
    if unique_tools_count > 0:
        scores["td"] = min(1.0, (unique_tools_count - 1) / 9)  # 1 tool = 0, 10+ = 1
    else:
        scores["td"] = 0.5  # Default when no data available

    # === RESPONSE INTENSITY (ri) ===
    # Median messages per hour during sessions
    # 20 msg/hr = intense (1.0)
    scores["ri"] = min(1.0, median_rate / 20)

    # Quantize all scores to integers 0-100
    return {k: round(v * 100) for k, v in scores.items()}


def compute_project_cooccurrence(
    sessions: List[SessionInfoV3],
    project_names: List[str],
    max_edges: int = MAX_COOCCURRENCE_EDGES,
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
    max_events: int = MAX_TIMELINE_EVENTS,
) -> List[List]:
    """Detect significant events throughout the year.

    Events are prioritized: peak > milestones > streaks > gaps > new_project

    Returns:
        List of event arrays: [day, type, value, project_idx]
        (4 elements per event, -1 for missing optional values)
    """
    proj_to_idx = {name: i for i, name in enumerate(project_names)}
    events: List[List] = []

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
    events.append([peak_day, EVENT_TYPE_INDICES["peak_day"], messages_by_day[peak_day], -1])

    # === MILESTONES ===
    cumulative = 0
    milestone_idx = 0
    for day in sorted(messages_by_day.keys()):
        cumulative += messages_by_day[day]
        while (
            milestone_idx < len(MILESTONE_VALUES)
            and cumulative >= MILESTONE_VALUES[milestone_idx]
        ):
            events.append(
                [day, EVENT_TYPE_INDICES["milestone"], MILESTONE_VALUES[milestone_idx], -1]
            )
            milestone_idx += 1

    # === STREAKS AND GAPS ===
    active_days = sorted(messages_by_day.keys())
    if len(active_days) > 0:
        streak_start = active_days[0]
        streak_length = 1

        for i in range(1, len(active_days)):
            gap = active_days[i] - active_days[i - 1]

            if gap == 1:
                streak_length += 1
            else:
                # End of streak
                if streak_length >= 5:
                    events.append([streak_start, EVENT_TYPE_INDICES["streak_start"], -1, -1])
                    events.append(
                        [active_days[i - 1], EVENT_TYPE_INDICES["streak_end"], streak_length, -1]
                    )

                # Gap detection
                if gap >= 7:
                    events.append([active_days[i - 1], EVENT_TYPE_INDICES["gap_start"], -1, -1])
                    events.append([active_days[i], EVENT_TYPE_INDICES["gap_end"], gap, -1])

                streak_start = active_days[i]
                streak_length = 1

        # Final streak check
        if streak_length >= 5:
            events.append([streak_start, EVENT_TYPE_INDICES["streak_start"], -1, -1])
            events.append([active_days[-1], EVENT_TYPE_INDICES["streak_end"], streak_length, -1])

    # === NEW PROJECT EVENTS (lowest priority) ===
    for project, day in projects_first_day.items():
        if project in proj_to_idx:
            events.append([day, EVENT_TYPE_INDICES["new_project"], -1, proj_to_idx[project]])

    # Sort by day, then by priority (lower type index = higher priority)
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
    limit: int = MAX_SESSION_FINGERPRINTS,
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

    # Score sessions by significance (messages * sqrt(duration))
    scored = []
    for s in sessions:
        if s.project_name in proj_to_idx:
            score = s.message_count * (
                s.duration_minutes**0.5 if s.duration_minutes > 0 else 1
            )
            scored.append((score, s))

    scored.sort(reverse=True, key=lambda x: x[0])

    fingerprints = []
    for _, info in scored[:limit]:
        # Load full session if file path available
        fp = [25, 50, 75, 100, 50, 10, 30, 20]  # Default fallback (quantized 0-100)

        if info.session_id in session_file_map:
            try:
                full_session = parse_session(
                    session_file_map[info.session_id], info.project_path
                )
                fp = compute_session_fingerprint(full_session)
            except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError, KeyError):
                pass  # Use default fingerprint on parse/compute error

        # Compact array format: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
        fingerprints.append(
            [
                info.duration_minutes,
                info.message_count,
                1 if info.is_agent else 0,  # Boolean as int for compact encoding
                info.start_time.hour if info.start_time else 0,
                info.start_time.weekday() if info.start_time else 0,
                proj_to_idx.get(info.project_name, 0),
            ]
            + fp
        )  # Flatten fp array into the main array

    return fingerprints


# =============================================================================
# RLE Encoding
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
    if "hm" in data and data["hm"]:
        # Quantize to 0-15 scale for compact encoding
        quantized = quantize_heatmap(data["hm"])
        # RLE encode if beneficial
        is_rle, encoded_hm = rle_encode_if_smaller(quantized)
        if is_rle:
            data["hm"] = encoded_hm
            data["hm_rle"] = True  # Flag for decoder
        else:
            data["hm"] = quantized

    packed = msgpack.packb(data, use_bin_type=True)
    return base64.urlsafe_b64encode(packed).rstrip(b"=").decode("ascii")


def decode_wrapped_story_v3(encoded: str) -> WrappedStoryV3:
    """Decode V3 story."""
    import base64

    import msgpack

    # Add padding if needed
    padding = (4 - len(encoded) % 4) % 4
    padded = encoded + "=" * padding

    packed = base64.urlsafe_b64decode(padded)
    data = msgpack.unpackb(packed, raw=False, strict_map_key=False)

    # RLE decode heatmap if flagged
    if data.get("hm_rle") and "hm" in data:
        data["hm"] = rle_decode(data["hm"])
        del data["hm_rle"]

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
        diff = (sorted_dates[i] - sorted_dates[i - 1]).days
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
                if (sorted_dates[i + 1] - sorted_dates[i]).days == 1:
                    current_streak += 1
                else:
                    break

    return [streak_count, longest_streak, current_streak, avg_streak]


def generate_wrapped_story_v3(
    year: int, name: Optional[str] = None, previous_year_data: Optional[Dict] = None
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
        "total": 0,
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_create": 0,
        "models": defaultdict(int),  # model -> total tokens
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
                            token_stats["input"] += tu.input_tokens
                            token_stats["output"] += tu.output_tokens
                            token_stats["cache_read"] += tu.cache_read_tokens
                            token_stats["cache_create"] += tu.cache_creation_tokens
                            token_stats["total"] += tu.total_tokens
                            if tu.model:
                                # Simplify model name for display
                                model_short = (
                                    tu.model.split("-")[1] if "-" in tu.model else tu.model
                                )
                                token_stats["models"][model_short] += tu.total_tokens

    # Filter to requested year
    year_sessions = [
        s for s in all_sessions if s.start_time and s.start_time.year == year
    ]

    if not year_sessions:
        raise ValueError(f"No Claude Code activity found for {year}")

    # Group by project for the year
    year_project_sessions: Dict[str, List[SessionInfoV3]] = defaultdict(list)
    for s in year_sessions:
        if s.project_name:  # Skip sessions with empty project names
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

        project_stats.append(
            ProjectStatsV3(
                name=proj_name[:MAX_PROJECT_NAME_LENGTH],
                path=sessions[0].project_path if sessions else "",
                message_count=messages,
                agent_sessions=agent_count,
                main_sessions=main_count,
                hours=hours,
                days_active=days_active,
                first_day=first_day,
                last_day=last_day,
            )
        )

    # Sort by messages and limit
    project_stats.sort(key=lambda p: p.message_count, reverse=True)
    top_projects = project_stats[:MAX_PROJECTS]
    project_names = [p.name for p in top_projects]

    # Core counts
    total_sessions = len(year_sessions)
    total_messages = sum(s.message_count for s in year_sessions)
    total_hours = round(
        sum(s.duration_minutes for s in year_sessions) / 60
    )  # Integer hours
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
        tp_data.append(
            [
                p.name,
                p.message_count,
                p.hours,  # Already integer
                p.days_active,
                p.session_count,
                round(p.agent_ratio * 100),
            ]
        )

    # Co-occurrence
    cooccurrence = compute_project_cooccurrence(year_sessions, project_names)

    # Timeline events
    events = detect_timeline_events(year_sessions, project_names, year)

    # Session fingerprints
    fingerprints = get_top_session_fingerprints(
        year_sessions, session_file_map, project_names
    )

    # Longest session
    session_durations = [
        s.duration_minutes / 60 for s in year_sessions if s.duration_minutes > 0
    ]
    longest_session = max(session_durations) if session_durations else 0.0

    # Streak stats: [count, longest_days, current_days, avg_days]
    streak_stats = compute_streak_stats(active_dates, year)

    # Convert token models dict to regular dict for serialization
    token_stats["models"] = dict(token_stats["models"])

    # Year-over-year
    yoy = None
    if previous_year_data:
        yoy = {
            "pm": previous_year_data.get("messages", 0),
            "ph": previous_year_data.get("hours", 0),
            "ps": previous_year_data.get("sessions", 0),
            "pp": previous_year_data.get("projects", 0),
            "pd": previous_year_data.get("days", 0),
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
