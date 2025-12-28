"""Utility functions for Claude Code History Explorer.

This module provides shared helper functions used across the package:
- format_duration(): Human-readable duration formatting
- format_timestamp(): Safe datetime formatting with fallback
- classify(): Threshold-based classification
- _active_duration_minutes(): Gap-capped duration calculation
- _compile_regex_safe(): ReDoS-protected regex compilation
"""

import re
from datetime import datetime
from typing import List, Optional

from .constants import ACTIVITY_GAP_CAP_MINUTES

# Import Message type for type hints (avoiding circular import at runtime)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Message


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


# ReDoS-vulnerable patterns: nested quantifiers like (a+)+, (a*)*
_REDOS_PATTERN = re.compile(r"\([^)]*[+*][^)]*\)[+*]")


def _compile_regex_safe(pattern: str, flags: int = 0) -> re.Pattern:
    """Compile a regex pattern with basic ReDoS protection.

    Checks for patterns that could cause catastrophic backtracking and
    raises a descriptive error if found.

    Args:
        pattern: Regular expression pattern to compile
        flags: Regex flags (e.g., re.IGNORECASE)

    Returns:
        Compiled regex pattern

    Raises:
        ValueError: If pattern contains ReDoS-vulnerable constructs
        re.error: If pattern is not a valid regex
    """
    # Check for nested quantifiers that can cause catastrophic backtracking
    if _REDOS_PATTERN.search(pattern):
        raise ValueError(
            f"Pattern may cause slow matching (nested quantifiers): {pattern}"
        )
    return re.compile(pattern, flags)


def _active_duration_minutes(
    messages: List["Message"], max_gap_minutes: int = ACTIVITY_GAP_CAP_MINUTES
) -> int:
    """Calculate active duration by summing gaps between messages, capping each gap.

    This prevents inflated durations from sessions left open overnight or for days.
    Each gap between consecutive messages is capped at max_gap_minutes.

    Note: This is a helper function. Session.active_duration_minutes uses this.

    Args:
        messages: List of Message objects with timestamps
        max_gap_minutes: Maximum minutes to count for any single gap
            (default: ACTIVITY_GAP_CAP_MINUTES)

    Returns:
        Active duration in minutes

    Example:
        If messages are at 10:00, 10:05, 10:10, then 14:00 (4 hour gap):
        - Raw duration: 240 minutes
        - Active duration: 5 + 5 + 30 = 40 minutes (gap capped at 30)
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
