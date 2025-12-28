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

# CLI display constants
MESSAGE_DISPLAY_LIMIT = 2000  # Max chars before truncating message content
TOOL_INPUT_PREVIEW_LIMIT = 500  # Max chars for tool input preview
SEARCH_TRUNCATION_LIMIT = 200  # Max chars for search result snippets
SLUG_DISPLAY_LIMIT = 20  # Max chars for session slug display

# CLI default limits
DEFAULT_PROJECTS_LIMIT = 20
DEFAULT_SESSIONS_LIMIT = 20
DEFAULT_SHOW_LIMIT = 50
DEFAULT_SEARCH_LIMIT = 20

# Concurrent session detection window (in minutes)
CONCURRENT_WINDOW_MINUTES = 30

# Milestone thresholds for achievements
MILESTONE_VALUES = [100, 500, 1000, 2000, 5000, 10000]

# Wrapped URL domain
WRAPPED_URL_DOMAIN = "wrapped-claude-codes.adewale-883.workers.dev"

# Date format for display
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
DATETIME_FORMAT_FULL = "%Y-%m-%d %H:%M:%S"
