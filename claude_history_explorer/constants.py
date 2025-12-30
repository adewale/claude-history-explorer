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


# =============================================================================
# Work Type Classification
# =============================================================================

# Pattern Design Principles:
# 1. Extensions use $ anchor: r"\.tex$" (matches end of path)
# 2. Directories use enclosing slashes: r"/papers?/" (avoids partial matches)
# 3. Terminal directories use (?:/|$): r"/thesis(?:/|$)" (matches /thesis or /thesis/)
# 4. All patterns are matched case-insensitively

WORK_TYPE_PATTERNS = {
    "writing": [
        # File extensions (anchored at end)
        r"\.tex$", r"\.md$", r"\.docx?$", r"\.rst$", r"\.txt$",
        # Directory patterns (enclosed or terminal)
        r"/papers?/", r"/docs?/", r"/documentation/",
        r"/thesis(?:/|$)", r"/dissertation(?:/|$)",
        r"/manuscripts?(?:/|$)", r"/proposals?(?:/|$)", r"/drafts?(?:/|$)",
        r"/writing(?:/|$)", r"/book(?:/|$)", r"/chapter(?:/|$)",
    ],
    "analysis": [
        # File extensions
        r"\.csv$", r"\.xlsx?$", r"\.ipynb$", r"\.r$", r"\.rmd$",
        r"\.parquet$", r"\.feather$", r"\.sav$",  # Data formats
        # Directory patterns
        r"/data/", r"/datasets?/", r"/analysis/", r"/analytics/",
        r"/results?/", r"/notebooks?/", r"/jupyter/",
        r"/statistics?(?:/|$)", r"/viz(?:/|$)", r"/visuali[sz]ations?(?:/|$)",
    ],
    "research": [
        # File extensions
        r"\.bib$", r"\.ris$", r"\.enw$",  # Bibliography formats
        # Directory patterns
        r"/research/", r"/literature/", r"/lit[-_]?review/",
        r"/bibliography(?:/|$)", r"/references(?:/|$)", r"/sources(?:/|$)",
        r"/reading(?:/|$)", r"/papers[-_]to[-_]read(?:/|$)",
    ],
    "teaching": [
        # Directory patterns (no common file extensions)
        r"/courses?/", r"/class(?:es)?/", r"/teaching/",
        r"/grading(?:/|$)", r"/assignments?(?:/|$)", r"/homework(?:/|$)",
        r"/syllabus(?:/|$)", r"/syllabi(?:/|$)",
        r"/students?(?:/|$)", r"/rubrics?(?:/|$)", r"/lectures?(?:/|$)",
        r"/exams?(?:/|$)", r"/quizzes?(?:/|$)",
    ],
    "design": [
        # File extensions
        r"\.fig$", r"\.sketch$", r"\.xd$", r"\.psd$", r"\.ai$",
        r"\.svg$", r"\.figma$",
        # Directory patterns
        r"/design/", r"/designs/", r"/ui/", r"/ux/",
        r"/mockups?(?:/|$)", r"/wireframes?(?:/|$)", r"/prototypes?(?:/|$)",
        r"/assets(?:/|$)", r"/icons(?:/|$)", r"/illustrations?(?:/|$)",
    ],
    # Note: "coding" has no patterns - it's the default for Claude Code
}

WORK_TYPE_INFO = {
    "coding": {
        "name": "Software Development",
        "description": "Coding, debugging, infrastructure",
    },
    "writing": {
        "name": "Writing & Documentation",
        "description": "Papers, proposals, documentation",
    },
    "analysis": {
        "name": "Data Analysis",
        "description": "Statistics, data processing, visualization",
    },
    "research": {
        "name": "Research & Literature",
        "description": "Literature review, reading, synthesis",
    },
    "teaching": {
        "name": "Teaching & Grading",
        "description": "Course materials, grading, feedback",
    },
    "design": {
        "name": "Design & UX",
        "description": "UI/UX design, mockups, wireframes",
    },
}
