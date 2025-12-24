"""
Work type classifier for knowledge workers.

Categorizes AI-assisted work sessions into meaningful work types
beyond just "coding hours" - designed for academics, researchers,
and other knowledge workers.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict


# =============================================================================
# Work Categories
# =============================================================================

WORK_CATEGORIES = {
    "writing": {
        "name": "Writing & Drafting",
        "description": "Papers, proposals, reports, documentation",
        "keywords": [
            "paper", "draft", "write", "revise", "edit", "manuscript",
            "abstract", "introduction", "conclusion", "section", "paragraph",
            "thesis", "dissertation", "article", "essay", "proposal",
            "grant", "report", "document", "readme", "documentation",
            "latex", "overleaf", "markdown", "docx", "pdf",
            "narrative", "outline", "chapter"
        ],
        "file_patterns": [
            r"\.tex$", r"\.md$", r"\.docx?$", r"\.pdf$", r"\.rst$",
            r"paper", r"draft", r"manuscript", r"proposal"
        ]
    },
    "analysis": {
        "name": "Data Analysis",
        "description": "Statistics, data processing, visualization",
        "keywords": [
            "analyze", "analysis", "data", "dataset", "csv", "json",
            "statistics", "regression", "correlation", "plot", "chart",
            "graph", "visualization", "pandas", "numpy", "matplotlib",
            "r ", "rstats", "spss", "stata", "excel", "spreadsheet",
            "mean", "median", "standard deviation", "p-value", "significance",
            "hypothesis", "sample", "population", "variance"
        ],
        "file_patterns": [
            r"\.csv$", r"\.xlsx?$", r"\.ipynb$", r"\.r$", r"\.rmd$",
            r"analysis", r"data", r"results"
        ]
    },
    "research": {
        "name": "Research & Literature",
        "description": "Literature review, reading, synthesis",
        "keywords": [
            "literature", "review", "cite", "citation", "reference",
            "source", "study", "finding", "evidence", "theory",
            "framework", "model", "hypothesis", "research question",
            "methodology", "method", "qualitative", "quantitative",
            "interview", "survey", "ethnography", "case study",
            "scholar", "academic", "journal", "conference", "arxiv"
        ],
        "file_patterns": [
            r"references", r"bibliography", r"\.bib$", r"review"
        ]
    },
    "teaching": {
        "name": "Teaching & Grading",
        "description": "Course materials, grading, student feedback",
        "keywords": [
            "grade", "grading", "student", "assignment", "homework",
            "exam", "quiz", "rubric", "feedback", "comment",
            "course", "syllabus", "lecture", "class", "semester",
            "canvas", "gradescope", "lms", "submission", "deadline",
            "ta ", "teaching assistant", "office hours",
            "attendance", "presentation slide"
        ],
        "file_patterns": [
            r"grading", r"assignment", r"rubric", r"syllabus",
            r"course", r"student"
        ]
    },
    "research_tooling": {
        "name": "Research Tooling",
        "description": "Building tools and pipelines for research",
        "keywords": [
            "pipeline", "scraper", "parser", "extraction", "validation",
            "dashboard", "visualization", "telemetry", "metrics", "agent",
            "automation", "workflow", "batch", "processing"
        ],
        "file_patterns": [
            r"pipeline", r"scraper", r"agent", r"tool"
        ]
    },
    "coding": {
        "name": "Software Development",
        "description": "General coding, debugging, infrastructure",
        "keywords": [
            "function", "class", "method", "variable", "import",
            "error", "bug", "fix", "debug", "test", "unittest",
            "api", "endpoint", "database", "query", "sql",
            "git", "commit", "branch", "merge", "pull request",
            "deploy", "build", "compile", "package", "install"
        ],
        "file_patterns": [
            r"\.py$", r"\.js$", r"\.ts$", r"\.rs$", r"\.go$",
            r"\.java$", r"\.cpp?$", r"\.h$", r"src/", r"lib/"
        ]
    },
    "admin": {
        "name": "Administration",
        "description": "Email, scheduling, organization, logistics",
        "keywords": [
            "email", "meeting", "schedule", "calendar", "agenda",
            "budget", "expense", "reimbursement", "travel", "flight",
            "hotel", "booking", "form", "paperwork", "hr ",
            "human resources", "payroll", "invoice", "contract"
        ],
        "file_patterns": [
            r"admin", r"hr", r"budget", r"schedule"
        ]
    },
    "communication": {
        "name": "Communication",
        "description": "Presentations, correspondence, outreach",
        "keywords": [
            "presentation", "slides", "powerpoint", "keynote",
            "talk", "conference", "seminar", "workshop", "poster",
            "email", "letter", "response", "reply", "message",
            "collaborate", "coauthor", "reviewer", "editor"
        ],
        "file_patterns": [
            r"\.pptx?$", r"\.key$", r"slides", r"presentation"
        ]
    },
    "planning": {
        "name": "Planning & Strategy",
        "description": "Project planning, brainstorming, decision-making",
        "keywords": [
            "plan", "strategy", "roadmap", "timeline", "milestone",
            "goal", "objective", "priority", "decision", "option",
            "brainstorm", "idea", "concept", "design", "architecture",
            "todo", "task", "project", "initiative"
        ],
        "file_patterns": [
            r"plan", r"roadmap", r"todo", r"design"
        ]
    }
}


@dataclass
class WorkBreakdown:
    """Breakdown of work by category."""
    total_messages: int = 0
    total_minutes: int = 0
    category_messages: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    category_minutes: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    uncategorized_messages: int = 0
    uncategorized_minutes: int = 0

    def add_session(self, category: Optional[str], messages: int, minutes: int):
        """Add a session's contribution to a category."""
        self.total_messages += messages
        self.total_minutes += minutes
        if category:
            self.category_messages[category] += messages
            self.category_minutes[category] += minutes
        else:
            self.uncategorized_messages += messages
            self.uncategorized_minutes += minutes

    def get_summary(self) -> Dict[str, Dict]:
        """Get summary with percentages."""
        summary = {}
        for cat_id, cat_info in WORK_CATEGORIES.items():
            msgs = self.category_messages.get(cat_id, 0)
            mins = self.category_minutes.get(cat_id, 0)
            summary[cat_id] = {
                "name": cat_info["name"],
                "description": cat_info["description"],
                "messages": msgs,
                "minutes": mins,
                "hours": round(mins / 60, 1),
                "message_pct": round(100 * msgs / self.total_messages, 1) if self.total_messages else 0,
                "time_pct": round(100 * mins / self.total_minutes, 1) if self.total_minutes else 0
            }

        # Add uncategorized
        summary["other"] = {
            "name": "Other/Mixed",
            "description": "Sessions that don't fit a single category",
            "messages": self.uncategorized_messages,
            "minutes": self.uncategorized_minutes,
            "hours": round(self.uncategorized_minutes / 60, 1),
            "message_pct": round(100 * self.uncategorized_messages / self.total_messages, 1) if self.total_messages else 0,
            "time_pct": round(100 * self.uncategorized_minutes / self.total_minutes, 1) if self.total_minutes else 0
        }

        return summary


def classify_text(text: str) -> Dict[str, float]:
    """Score text against each work category.

    Uses simple keyword matching. Each keyword hit adds 1 to the score,
    which is then normalized by the number of keywords in that category.

    Args:
        text: Text to classify

    Returns:
        Dict of category_id -> score (0.0 to 1.0)
    """
    text_lower = text.lower()
    scores = {}

    for cat_id, cat_info in WORK_CATEGORIES.items():
        score = 0.0

        # Keyword matching
        for keyword in cat_info["keywords"]:
            if keyword in text_lower:
                score += 1.0

        # Normalize by number of keywords
        max_score = len(cat_info["keywords"])
        scores[cat_id] = min(score / max_score if max_score else 0, 1.0)

    return scores


def score_session(messages: List[str], project_path: str = "") -> Dict[str, float]:
    """Score a session against all work categories.

    Combines keyword matching on message content with file pattern
    matching on the project path.

    Args:
        messages: List of message content strings
        project_path: Optional project path for additional context

    Returns:
        Dict of category_id -> score (higher = more signal)
    """
    # Combine all text for analysis
    all_text = " ".join(messages) + " " + project_path

    scores = classify_text(all_text)

    # Also check project path against file patterns
    for cat_id, cat_info in WORK_CATEGORIES.items():
        for pattern in cat_info.get("file_patterns", []):
            if re.search(pattern, project_path, re.IGNORECASE):
                scores[cat_id] = scores.get(cat_id, 0) + 0.3

    return scores


def classify_session(messages: List[str], project_path: str = "") -> Optional[str]:
    """Classify a session into a single dominant work category.

    Uses winner-take-all classification. Returns None if no clear winner
    (top score must be at least 1.5x the second-highest score).

    Args:
        messages: List of message content strings
        project_path: Optional project path for additional context

    Returns:
        Category ID or None if unclear
    """
    scores = score_session(messages, project_path)

    if not scores:
        return None

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_cat, top_score = sorted_scores[0]

    # Require minimum score and clear winner
    if top_score < 0.05:
        return None

    if len(sorted_scores) > 1:
        second_score = sorted_scores[1][1]
        # Top category should be meaningfully higher
        if top_score < second_score * 1.5:
            return None

    return top_cat


def classify_session_proportional(
    messages: List[str], project_path: str = ""
) -> Dict[str, float]:
    """Classify a session proportionally across work categories.

    Knowledge work often spans multiple categories. This returns the
    proportional weight of each category based on signal strength,
    rather than picking a single winner.

    Args:
        messages: List of message content strings
        project_path: Optional project path for additional context

    Returns:
        Dict of category_id -> weight (0.0 to 1.0, sums to 1.0)
    """
    scores = score_session(messages, project_path)

    total_score = sum(scores.values())
    if total_score == 0:
        return {}

    return {cat_id: score / total_score for cat_id, score in scores.items()}


def format_work_breakdown(breakdown: WorkBreakdown) -> str:
    """Format work breakdown as a nice display string."""
    summary = breakdown.get_summary()

    # Sort by time percentage
    sorted_cats = sorted(
        summary.items(),
        key=lambda x: x[1]["time_pct"],
        reverse=True
    )

    lines = [
        "Work Breakdown",
        "=" * 50,
        ""
    ]

    for cat_id, data in sorted_cats:
        if data["time_pct"] < 1:  # Skip tiny categories
            continue

        bar_length = int(data["time_pct"] / 5)  # 20 chars max
        bar = "#" * bar_length + "-" * (20 - bar_length)

        lines.append(f"{data['name']:<25} {bar} {data['hours']:>5.1f}h ({data['time_pct']:>4.1f}%)")

    lines.append("")
    lines.append(f"Total: {breakdown.total_minutes / 60:.1f} hours across {breakdown.total_messages} messages")

    return "\n".join(lines)
