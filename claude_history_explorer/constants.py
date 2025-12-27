"""Constants for Claude Code History Explorer.

Centralizes thresholds used for story generation and personality analysis.
"""

# Message rate thresholds (messages per hour)
MESSAGE_RATE_HIGH = 30
MESSAGE_RATE_MEDIUM = 20
MESSAGE_RATE_LOW = 10

# Session duration thresholds (in hours)
SESSION_LENGTH_LONG = 2.0
SESSION_LENGTH_EXTENDED = 1.0
SESSION_LENGTH_STANDARD = 0.5

# Agent collaboration ratios
AGENT_RATIO_HIGH = 0.8
AGENT_RATIO_BALANCED = 0.5

# Activity intensity thresholds (messages per day)
ACTIVITY_INTENSITY_HIGH = 300
ACTIVITY_INTENSITY_MEDIUM = 100

# Active duration calculation
# Maximum gap between messages counted as active time (in minutes)
ACTIVITY_GAP_CAP_MINUTES = 30
