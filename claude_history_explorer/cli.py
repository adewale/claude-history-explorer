"""CLI interface for Claude Code History Explorer.

This module provides the command-line interface for exploring Claude Code
conversation history. It uses Click for argument parsing and Rich for
terminal formatting.

Commands:
    projects: List all Claude Code projects
    sessions: List sessions for a specific project
    show: Display messages from a session
    search: Search across all conversations
    export: Export sessions to various formats
    stats: Show detailed statistics
    summary: Generate comprehensive summaries
    story: Tell the story of your development journey
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from sparklines import sparklines

from .constants import (
    MESSAGE_DISPLAY_LIMIT,
    TOOL_INPUT_PREVIEW_LIMIT,
    SEARCH_TRUNCATION_LIMIT,
    SLUG_DISPLAY_LIMIT,
    DEFAULT_PROJECTS_LIMIT,
    DEFAULT_SESSIONS_LIMIT,
    DEFAULT_SHOW_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    DATETIME_FORMAT,
    DATETIME_FORMAT_FULL,
    WRAPPED_URL_DOMAIN,
)
from .history import (
    list_projects,
    find_project,
    parse_session,
    search_sessions,
    get_session_by_id,
    get_claude_dir,
    get_projects_dir,
    calculate_project_stats,
    calculate_global_stats,
    generate_project_story,
    generate_global_story,
    generate_wrapped_story_v3,
    encode_wrapped_story_v3,
    decode_wrapped_story_v3,
    ProjectStats,
    GlobalStats,
    ProjectStory,
    GlobalStory,
    WrappedStoryV3,
)

__all__ = ["main"]

console = Console()


def _sanitize_output_path(output: str) -> Path:
    """Sanitize output file path to prevent directory traversal attacks.

    Validates that relative paths don't escape the current working directory
    using parent directory references (e.g., ../../../etc/passwd).

    Args:
        output: The user-provided output file path

    Returns:
        Sanitized Path object

    Raises:
        click.ClickException: If relative path contains directory traversal
    """
    path = Path(output)

    # For relative paths, check for parent directory traversal
    if not path.is_absolute():
        try:
            # Resolve to catch traversal attempts like foo/../../../etc/passwd
            resolved = (Path.cwd() / path).resolve()
            if not str(resolved).startswith(str(Path.cwd().resolve())):
                raise click.ClickException(
                    f"Path escapes current directory: {output}\n"
                    "Use a path within the current directory."
                )
        except (OSError, ValueError) as e:
            raise click.ClickException(f"Invalid output path: {output} ({e})")

    return path


def format_datetime(dt: Optional[datetime], fallback: str = "unknown") -> str:
    """Format a datetime object consistently across the CLI.

    Args:
        dt: The datetime to format, or None
        fallback: String to return if dt is None

    Returns:
        Formatted datetime string or fallback value
    """
    if dt is None:
        return fallback
    return dt.strftime(DATETIME_FORMAT)


def truncate(text: str, limit: int, suffix: str = "...") -> str:
    """Truncate text to a maximum length with suffix.

    Args:
        text: The text to truncate
        limit: Maximum length before truncation
        suffix: String to append when truncated

    Returns:
        Original text if short enough, or truncated with suffix
    """
    if len(text) <= limit:
        return text
    return text[:limit] + suffix


def safe_sparkline(values: List[int]) -> Optional[str]:
    """Generate a sparkline string, returning None on failure.

    Wraps the sparklines library with error handling for edge cases
    like empty lists, single values, or invalid data.

    Args:
        values: List of integers to visualize

    Returns:
        Sparkline string or None if generation fails
    """
    if not values or len(values) < 2:
        return None
    try:
        result = sparklines(values)
        return result[0] if result else None
    except (ValueError, TypeError):
        return None


# Example text for each command
EXAMPLES = {
    "projects": """
Examples:
  claude-history projects           # List all projects
  claude-history projects -n 10     # Show only 10 projects
""",
    "sessions": """
Examples:
  claude-history sessions myproject          # List sessions for 'myproject'
  claude-history sessions "Documents/work"   # Partial path match
  claude-history sessions myproject -n 5     # Show 5 most recent sessions (--head is default)
  claude-history sessions myproject -n 5 --tail  # Show 5 oldest sessions
  claude-history sessions myproject -n 5 -t  # Show 5 oldest sessions (short form)
""",
    "show": """
Examples:
  claude-history show abc123                 # Show session by ID (partial match)
  claude-history show abc123 -n 20           # Show first 20 messages (--head is default)
  claude-history show abc123 -n 10 --tail    # Show last 10 messages
  claude-history show abc123 -n 5 -t         # Show last 5 messages (short form)
  claude-history show abc123 --raw           # Output raw JSON
  claude-history show abc123 -p myproject    # Search in specific project
""",
    "search": """
Examples:
  claude-history search "TODO"               # Search all projects
  claude-history search "error.*fix"         # Regex search
  claude-history search "bug" -p myproject   # Search specific project
  claude-history search "API" -c             # Case-sensitive search
""",
    "export": """
Examples:
  claude-history export abc123 -f markdown -o session.md   # Export to Markdown
  claude-history export abc123 -f json -o session.json     # Export to JSON
  claude-history export abc123 -f text                     # Export to stdout as text
""",
    "stats": """
Examples:
  claude-history stats                       # Global statistics
  claude-history stats -p myproject          # Project-specific stats
  claude-history stats --format json         # JSON output for scripting
""",
    "summary": """
Examples:
  claude-history summary                     # Global summary (text)
  claude-history summary -p myproject        # Project-specific summary
  claude-history summary --format markdown   # Markdown with charts
  claude-history summary -o report.md        # Save to file
""",
    "story": """
Examples:
  claude-history story                       # Story of all projects
  claude-history story -p myproject          # Story for specific project
  claude-history story --format brief        # Short summary
  claude-history story --format timeline     # Timeline with sparklines
  claude-history story -o journey.md         # Save to file
""",
    "info": """
Examples:
  claude-history info                        # Show storage location and stats
""",
    "wrapped": """
Examples:
  claude-history wrapped                     # Generate wrapped for current year
  claude-history wrapped --year 2025         # Generate wrapped for 2025
  claude-history wrapped -y 2025 -n "Alice"  # With display name
  claude-history wrapped --raw               # Output raw JSON
  claude-history wrapped --decode <url>      # Decode and inspect any Wrapped URL
  claude-history wrapped --no-copy           # Don't copy URL to clipboard
""",
}


def show_examples(command: str) -> None:
    """Display example usage for a command."""
    if command in EXAMPLES:
        console.print(EXAMPLES[command])
    else:
        console.print(f"[yellow]No examples available for '{command}'[/yellow]")


@click.group()
@click.version_option()
def main():
    """Explore your Claude Code conversation history.

    Claude Code stores conversation history in ~/.claude/projects/ as JSONL files.
    This tool helps you browse, search, and export that history.
    """
    pass


@main.command()
@click.option("--limit", "-n", default=DEFAULT_PROJECTS_LIMIT, help="Maximum number of projects to show")
@click.option("--example", is_flag=True, help="Show usage examples")
def projects(limit: int, example: bool):
    """List all Claude Code projects sorted by last use."""
    if example:
        show_examples("projects")
        return
    projects_dir = get_projects_dir()

    if not projects_dir.exists():
        console.print(f"[red]Claude Code directory not found at {projects_dir}[/red]")
        console.print("Make sure Claude Code has been used on this machine.")
        return

    all_projects = list_projects()

    if not all_projects:
        console.print("[yellow]No projects found.[/yellow]")
        return

    table = Table(title=f"Claude Code Projects ({len(all_projects)} total)")
    table.add_column("Project Path", style="cyan", no_wrap=False)
    table.add_column("Sessions", justify="right", style="green")
    table.add_column("Last Used", style="yellow")

    for proj in all_projects[:limit]:
        table.add_row(
            proj.path,
            str(proj.session_count),
            format_datetime(proj.last_modified),
        )

    console.print(table)

    if len(all_projects) > limit:
        console.print(
            f"\n[dim]Showing {limit} of {len(all_projects)} projects. Use --limit to see more.[/dim]"
        )


@main.command()
@click.argument("project_search", required=False)
@click.option("--limit", "-n", default=DEFAULT_SESSIONS_LIMIT, help="Maximum number of sessions to show")
@click.option("--head", is_flag=True, default=True, is_eager=True, help="Show most recent sessions (default)")
@click.option("--tail", "-t", is_flag=True, help="Show oldest sessions instead of most recent")
@click.option("--example", is_flag=True, help="Show usage examples")
def sessions(project_search: str, limit: int, head: bool, tail: bool, example: bool):
    """List sessions for a project.

    PROJECT_SEARCH can be a partial path match (e.g., 'myproject' or 'Documents/work')
    """
    if example:
        show_examples("sessions")
        return
    if not project_search:
        console.print("[red]Error: Missing argument 'PROJECT_SEARCH'[/red]")
        console.print("Use --example to see usage examples.")
        return
    project = find_project(project_search)

    if not project:
        console.print(f"[red]No project found matching '{project_search}'[/red]")
        console.print("\nUse 'claude-history projects' to see available projects.")
        return

    console.print(f"[bold]Project:[/bold] {project.path}\n")

    table = Table(title=f"Sessions ({project.session_count} total)")
    table.add_column("Session ID", style="cyan")
    table.add_column("Messages", justify="right", style="green")
    table.add_column("User Msgs", justify="right", style="blue")
    table.add_column("Duration", justify="right")
    table.add_column("Started", style="yellow")
    table.add_column("Slug", style="dim")

    # Select sessions from head (most recent, default) or tail (oldest)
    session_files = project.session_files[-limit:] if tail else project.session_files[:limit]

    for session_file in session_files:
        session = parse_session(session_file, project.path)
        slug = truncate(session.slug, SLUG_DISPLAY_LIMIT) if session.slug else ""

        table.add_row(
            session.session_id[:12] + "...",
            str(session.message_count),
            str(session.user_message_count),
            session.duration_str,
            format_datetime(session.start_time),
            slug,
        )

    console.print(table)

    if project.session_count > limit:
        position = "oldest" if tail else "most recent"
        console.print(
            f"\n[dim]Showing {position} {limit} of {project.session_count} sessions. Use --limit to see more.[/dim]"
        )


@main.command()
@click.argument("session_id", required=False)
@click.option("--project", "-p", default=None, help="Project path to search in")
@click.option("--limit", "-n", default=DEFAULT_SHOW_LIMIT, help="Maximum messages to show")
@click.option("--head", is_flag=True, default=True, is_eager=True, help="Show first N messages (default)")
@click.option("--tail", "-t", is_flag=True, help="Show last N messages instead of first")
@click.option("--raw", is_flag=True, help="Show raw JSON output")
@click.option("--example", is_flag=True, help="Show usage examples")
def show(session_id: str, project: str, limit: int, head: bool, tail: bool, raw: bool, example: bool):
    """Show messages from a specific session.

    SESSION_ID can be a partial match of the session ID.
    """
    if example:
        show_examples("show")
        return
    if not session_id:
        console.print("[red]Error: Missing argument 'SESSION_ID'[/red]")
        console.print("Use --example to see usage examples.")
        return
    proj = find_project(project) if project else None
    session = get_session_by_id(session_id, proj)

    if not session:
        console.print(f"[red]No session found matching '{session_id}'[/red]")
        return

    # Select messages from head (default) or tail
    messages = session.messages[-limit:] if tail else session.messages[:limit]

    if raw:
        for msg in messages:
            output = {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "tool_uses": msg.tool_uses,
            }
            console.print(json.dumps(output, indent=2))
        return

    console.print(
        Panel(
            f"[bold]Session:[/bold] {session.session_id}\n"
            f"[bold]Project:[/bold] {session.project_path}\n"
            f"[bold]Messages:[/bold] {session.message_count} ({session.user_message_count} from user)\n"
            f"[bold]Duration:[/bold] {session.duration_str}\n"
            f"[bold]Slug:[/bold] {session.slug or 'N/A'}",
            title="Session Info",
        )
    )

    console.print()

    for i, msg in enumerate(messages):
        if msg.role == "user":
            style = "bold blue"
            prefix = "USER"
        else:
            style = "bold green"
            prefix = "ASSISTANT"

        timestamp = msg.timestamp.strftime("%H:%M:%S") if msg.timestamp else ""

        console.print(f"[{style}]--- {prefix} [{timestamp}] ---[/{style}]")

        # Show content
        if msg.content:
            # Truncate very long messages
            content = msg.content
            if len(content) > MESSAGE_DISPLAY_LIMIT:
                content = truncate(
                    content,
                    MESSAGE_DISPLAY_LIMIT,
                    "\n\n[dim]... (truncated, use --raw for full content)[/dim]",
                )
            console.print(content)

        # Show tool uses
        if msg.tool_uses:
            for tool in msg.tool_uses:
                console.print(f"\n[yellow]Tool: {tool['name']}[/yellow]")
                if tool.get("input"):
                    input_preview = json.dumps(tool["input"], indent=2)
                    input_preview = truncate(
                        input_preview, TOOL_INPUT_PREVIEW_LIMIT, "\n..."
                    )
                    console.print(Syntax(input_preview, "json", theme="monokai"))

        console.print()

    if session.message_count > limit:
        position = "last" if tail else "first"
        console.print(
            f"[dim]Showing {position} {limit} of {session.message_count} messages. Use --limit to see more.[/dim]"
        )


@main.command()
@click.argument("pattern", required=False)
@click.option(
    "--project", "-p", default=None, help="Limit search to a specific project"
)
@click.option("--case-sensitive", "-c", is_flag=True, help="Case-sensitive search")
@click.option("--limit", "-n", default=DEFAULT_SEARCH_LIMIT, help="Maximum results to show")
@click.option("--context", "-C", default=100, help="Characters of context around match")
@click.option("--example", is_flag=True, help="Show usage examples")
def search(
    pattern: str,
    project: str,
    case_sensitive: bool,
    limit: int,
    context: int,
    example: bool,
):
    """Search for a pattern across all conversations.

    PATTERN is a regular expression to search for.
    """
    if example:
        show_examples("search")
        return
    if not pattern:
        console.print("[red]Error: Missing argument 'PATTERN'[/red]")
        console.print("Use --example to see usage examples.")
        return
    proj = find_project(project) if project else None

    console.print(f"[bold]Searching for:[/bold] {pattern}")
    if proj:
        console.print(f"[bold]In project:[/bold] {proj.path}")
    console.print()

    results_count = 0
    for session, messages in search_sessions(pattern, proj, case_sensitive):
        if results_count >= limit:
            break

        console.print(
            Panel(
                f"[bold]Session:[/bold] {session.session_id[:12]}...\n"
                f"[bold]Project:[/bold] {session.project_path}\n"
                f"[bold]Matches:[/bold] {len(messages)}",
                title="Match Found",
                border_style="green",
            )
        )

        for msg in messages[:3]:  # Show first 3 matching messages
            role_style = "blue" if msg.role == "user" else "green"
            console.print(f"[{role_style}]{msg.role.upper()}:[/{role_style}]")

            # Show context around match
            content = msg.content
            flags = 0 if case_sensitive else re.IGNORECASE
            match = re.search(pattern, content, flags)
            if match:
                start = max(0, match.start() - context)
                end = min(len(content), match.end() + context)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                console.print(f"  {snippet}")
            else:
                console.print(f"  {truncate(content, SEARCH_TRUNCATION_LIMIT)}")

        console.print()
        results_count += 1

    if results_count == 0:
        console.print("[yellow]No matches found.[/yellow]")
    else:
        console.print(f"[dim]Found {results_count} sessions with matches.[/dim]")


@main.command()
@click.argument("session_id", required=False)
@click.option("--project", "-p", default=None, help="Project path to search in")
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["json", "markdown", "text"]),
    default="markdown",
)
@click.option("--output", "-o", default=None, help="Output file (default: stdout)")
@click.option("--example", is_flag=True, help="Show usage examples")
def export(
    session_id: str, project: str, output_format: str, output: str, example: bool
):
    """Export a session to various formats (JSON, Markdown, or text).

    SESSION_ID can be a partial match of the session ID.
    """
    if example:
        show_examples("export")
        return
    if not session_id:
        console.print("[red]Error: Missing argument 'SESSION_ID'[/red]")
        console.print("Use --example to see usage examples.")
        return
    proj = find_project(project) if project else None
    session = get_session_by_id(session_id, proj)

    if not session:
        console.print(f"[red]No session found matching '{session_id}'[/red]")
        return

    if output_format == "json":
        data = {
            "session_id": session.session_id,
            "project_path": session.project_path,
            "slug": session.slug,
            "start_time": session.start_time.isoformat()
            if session.start_time
            else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "tool_uses": msg.tool_uses,
                }
                for msg in session.messages
            ],
        }
        result = json.dumps(data, indent=2)

    elif output_format == "markdown":
        lines = [
            f"# Session: {session.session_id}",
            "",
            f"**Project:** {session.project_path}",
            f"**Slug:** {session.slug or 'N/A'}",
            f"**Started:** {session.start_time.isoformat() if session.start_time else 'unknown'}",
            f"**Messages:** {session.message_count}",
            "",
            "---",
            "",
        ]

        for msg in session.messages:
            timestamp = (
                msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else ""
            )
            if msg.role == "user":
                lines.append(f"## User [{timestamp}]")
            else:
                lines.append(f"## Assistant [{timestamp}]")
            lines.append("")
            lines.append(msg.content)
            if msg.tool_uses:
                lines.append("")
                lines.append("**Tools used:**")
                for tool in msg.tool_uses:
                    lines.append(f"- `{tool['name']}`")
            lines.append("")
            lines.append("---")
            lines.append("")

        result = "\n".join(lines)

    else:  # text
        lines = [
            f"Session: {session.session_id}",
            f"Project: {session.project_path}",
            f"Started: {session.start_time.isoformat() if session.start_time else 'unknown'}",
            "",
            "=" * 60,
            "",
        ]

        for msg in session.messages:
            timestamp = msg.timestamp.strftime("%H:%M:%S") if msg.timestamp else ""
            lines.append(f"[{msg.role.upper()}] [{timestamp}]")
            lines.append(msg.content)
            lines.append("")
            lines.append("-" * 40)
            lines.append("")

        result = "\n".join(lines)

    if output:
        safe_path = _sanitize_output_path(output)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(result)
        console.print(f"[green]Exported to {safe_path}[/green]")
    else:
        console.print(result)


@main.command()
@click.option(
    "--project", "-p", default=None, help="Show stats for specific project only"
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
@click.option("--example", is_flag=True, help="Show usage examples")
def stats(project: str, output_format: str, example: bool):
    """Show detailed statistics for projects including message counts, duration, and storage."""
    if example:
        show_examples("stats")
        return
    try:
        if project:
            proj = find_project(project)
            if not proj:
                console.print(f"[red]No project found matching '{project}'[/red]")
                return
            project_stats = calculate_project_stats(proj)
            _display_project_stats(project_stats, output_format)
        else:
            global_stats = calculate_global_stats()
            _display_global_stats(global_stats, output_format)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option(
    "--project", "-p", default=None, help="Generate summary for specific project only"
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "markdown"]),
    default="text",
    help="Output format",
)
@click.option("--output", "-o", default=None, help="Output file (default: stdout)")
@click.option("--example", is_flag=True, help="Show usage examples")
def summary(project: str, output_format: str, output: str, example: bool):
    """Generate a comprehensive summary with insights, charts, and sparklines."""
    if example:
        show_examples("summary")
        return
    try:
        if project:
            proj = find_project(project)
            if not proj:
                console.print(f"[red]No project found matching '{project}'[/red]")
                return
            project_stats = calculate_project_stats(proj)
            summary_text = _generate_project_summary(project_stats, output_format)
        else:
            global_stats = calculate_global_stats()
            summary_text = _generate_global_summary(global_stats, output_format)

        if output:
            safe_path = _sanitize_output_path(output)
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(summary_text)
            console.print(f"[green]Summary written to {safe_path}[/green]")
        else:
            console.print(summary_text)

    except ValueError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option(
    "--project", "-p", default=None, help="Tell story for specific project only"
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["brief", "detailed", "timeline"]),
    default="detailed",
    help="Story format",
)
@click.option("--output", "-o", default=None, help="Output file (default: stdout)")
@click.option("--example", is_flag=True, help="Show usage examples")
def story(project: str, output_format: str, output: str, example: bool):
    """Tell the story of your development journey with personality insights and patterns."""
    if example:
        show_examples("story")
        return
    try:
        if project:
            proj = find_project(project)
            if not proj:
                console.print(f"[red]No project found matching '{project}'[/red]")
                return

            story_data = generate_project_story(proj)
            story_text = _format_project_story(story_data, output_format)
        else:
            story_data = generate_global_story()
            story_text = _format_global_story(story_data, output_format)

        if output:
            safe_path = _sanitize_output_path(output)
            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(story_text)
            console.print(f"[green]Story written to {safe_path}[/green]")
        else:
            console.print(story_text)

    except ValueError as e:
        console.print(f"[red]{e}[/red]")


@main.command()
@click.option("--example", is_flag=True, help="Show usage examples")
def info(example: bool):
    """Show Claude Code storage location and usage statistics."""
    if example:
        show_examples("info")
        return

    claude_dir = get_claude_dir()
    projects_dir = get_projects_dir()

    console.print(
        Panel(
            f"[bold]Claude directory:[/bold] {claude_dir}\n"
            f"[bold]Projects directory:[/bold] {projects_dir}\n"
            f"[bold]Directory exists:[/bold] {projects_dir.exists()}",
            title="Claude Code Storage Info",
        )
    )

    if projects_dir.exists():
        all_projects = list_projects()
        total_sessions = sum(p.session_count for p in all_projects)

        # Calculate total size
        total_size = 0
        for proj in all_projects:
            for f in proj.session_files:
                total_size += f.stat().st_size

        size_mb = total_size / (1024 * 1024)

        console.print(f"\n[bold]Statistics:[/bold]")
        console.print(f"  Projects: {len(all_projects)}")
        console.print(f"  Sessions: {total_sessions}")
        console.print(f"  Total size: {size_mb:.1f} MB")


def _display_project_stats(stats: ProjectStats, output_format: str) -> None:
    """Display statistics for a single project."""
    if output_format == "json":
        data = {
            "project_path": stats.project.path,
            "total_sessions": stats.total_sessions,
            "total_messages": stats.total_messages,
            "total_user_messages": stats.total_user_messages,
            "total_duration_minutes": stats.total_duration_minutes,
            "total_duration_str": stats.total_duration_str,
            "agent_sessions": stats.agent_sessions,
            "main_sessions": stats.main_sessions,
            "total_size_mb": stats.total_size_mb,
            "avg_messages_per_session": stats.avg_messages_per_session,
            "longest_session_duration": stats.longest_session_duration,
            "most_recent_session": stats.most_recent_session.isoformat()
            if stats.most_recent_session
            else None,
        }
        console.print(json.dumps(data, indent=2))
        return

    # Table format
    console.print(
        Panel(
            f"[bold]Project:[/bold] {stats.project.path}\n"
            f"[bold]Sessions:[/bold] {stats.total_sessions} ({stats.main_sessions} main, {stats.agent_sessions} agents)\n"
            f"[bold]Messages:[/bold] {stats.total_messages} ({stats.total_user_messages} from user)\n"
            f"[bold]Duration:[/bold] {stats.total_duration_str}\n"
            f"[bold]Size:[/bold] {stats.total_size_mb:.1f} MB\n"
            f"[bold]Avg messages/session:[/bold] {stats.avg_messages_per_session:.1f}\n"
            f"[bold]Longest session:[/bold] {stats.longest_session_duration}\n"
            f"[bold]Last active:[/bold] {stats.most_recent_session.strftime('%Y-%m-%d %H:%M') if stats.most_recent_session else 'unknown'}",
            title="Project Statistics",
        )
    )


def _display_global_stats(stats: GlobalStats, output_format: str) -> None:
    """Display global statistics across all projects."""
    if output_format == "json":
        data = {
            "total_projects": stats.total_projects,
            "total_sessions": stats.total_sessions,
            "total_messages": stats.total_messages,
            "total_user_messages": stats.total_user_messages,
            "total_duration_minutes": stats.total_duration_minutes,
            "total_duration_str": stats.total_duration_str,
            "total_size_mb": stats.total_size_mb,
            "avg_sessions_per_project": stats.avg_sessions_per_project,
            "avg_messages_per_session": stats.avg_messages_per_session,
            "most_active_project": stats.most_active_project,
            "largest_project": stats.largest_project,
            "most_recent_activity": stats.most_recent_activity.isoformat()
            if stats.most_recent_activity
            else None,
            "projects": [
                {
                    "path": p.project.path,
                    "sessions": p.total_sessions,
                    "messages": p.total_messages,
                    "size_mb": p.total_size_mb,
                    "duration_str": p.total_duration_str,
                }
                for p in stats.projects
            ],
        }
        console.print(json.dumps(data, indent=2))
        return

    # Overview panel
    console.print(
        Panel(
            f"[bold]Total Projects:[/bold] {stats.total_projects}\n"
            f"[bold]Total Sessions:[/bold] {stats.total_sessions}\n"
            f"[bold]Total Messages:[/bold] {stats.total_messages}\n"
            f"[bold]Total Duration:[/bold] {stats.total_duration_str}\n"
            f"[bold]Total Size:[/bold] {stats.total_size_mb:.1f} MB\n"
            f"[bold]Avg Sessions/Project:[/bold] {stats.avg_sessions_per_project:.1f}\n"
            f"[bold]Avg Messages/Session:[/bold] {stats.avg_messages_per_session:.1f}\n"
            f"[bold]Most Active Project:[/bold] {stats.most_active_project}\n"
            f"[bold]Largest Project:[/bold] {stats.largest_project}\n"
            f"[bold]Most Recent Activity:[/bold] {stats.most_recent_activity.strftime('%Y-%m-%d %H:%M') if stats.most_recent_activity else 'unknown'}",
            title="Global Statistics",
        )
    )

    # Projects table
    table = Table(title="Project Breakdown")
    table.add_column("Project", style="cyan", no_wrap=False)
    table.add_column("Sessions", justify="right", style="green")
    table.add_column("Messages", justify="right", style="blue")
    table.add_column("Size", justify="right", style="yellow")
    table.add_column("Duration", justify="right")
    table.add_column("Last Active", style="dim")

    for proj_stats in sorted(
        stats.projects, key=lambda p: p.total_messages, reverse=True
    ):
        table.add_row(
            proj_stats.project.path,
            str(proj_stats.total_sessions),
            str(proj_stats.total_messages),
            f"{proj_stats.total_size_mb:.1f} MB",
            proj_stats.total_duration_str,
            format_datetime(proj_stats.most_recent_session),
        )

    console.print("\n", table)


def _generate_project_summary(stats: ProjectStats, output_format: str) -> str:
    """Generate a text summary for a single project."""
    if output_format == "markdown":
        lines = [
            f"# Project Summary: {stats.project.path}",
            "",
            "## Overview",
            f"- **Total Sessions**: {stats.total_sessions}",
            f"- **Total Messages**: {stats.total_messages}",
            f"- **User Messages**: {stats.total_user_messages}",
            f"- **Total Duration**: {stats.total_duration_str}",
            f"- **Storage Size**: {stats.total_size_mb:.1f} MB",
            f"- **Average Messages per Session**: {stats.avg_messages_per_session:.1f}",
            "",
            "## Session Breakdown",
            f"- **Main Sessions**: {stats.main_sessions}",
            f"- **Agent Sessions**: {stats.agent_sessions}",
            f"- **Longest Session**: {stats.longest_session_duration}",
            f"- **Last Active**: {stats.most_recent_session.strftime('%Y-%m-%d %H:%M') if stats.most_recent_session else 'unknown'}",
            "",
            "## Insights",
        ]

        # Add insights
        if stats.agent_sessions > stats.main_sessions:
            lines.append("- Heavy agent usage suggests complex task decomposition")
        if stats.avg_messages_per_session > 100:
            lines.append("- High message volume indicates intensive development")
        if stats.total_duration_minutes > 1200:  # > 20 hours
            lines.append("- Significant time investment in this project")

        return "\n".join(lines)

    else:  # text format
        lines = [
            f"Project Summary: {stats.project.path}",
            "=" * 50,
            "",
            "Overview:",
            f"  Total Sessions: {stats.total_sessions}",
            f"  Total Messages: {stats.total_messages}",
            f"  User Messages: {stats.total_user_messages}",
            f"  Total Duration: {stats.total_duration_str}",
            f"  Storage Size: {stats.total_size_mb:.1f} MB",
            f"  Avg Messages/Session: {stats.avg_messages_per_session:.1f}",
            "",
            "Session Breakdown:",
            f"  Main Sessions: {stats.main_sessions}",
            f"  Agent Sessions: {stats.agent_sessions}",
            f"  Longest Session: {stats.longest_session_duration}",
            f"  Last Active: {stats.most_recent_session.strftime('%Y-%m-%d %H:%M') if stats.most_recent_session else 'unknown'}",
            "",
            "Key Insights:",
        ]

        # Add insights
        if stats.agent_sessions > stats.main_sessions:
            lines.append("  • Heavy agent usage suggests complex task decomposition")
        if stats.avg_messages_per_session > 100:
            lines.append("  • High message volume indicates intensive development")
        if stats.total_duration_minutes > 1200:  # > 20 hours
            lines.append("  • Significant time investment in this project")

        return "\n".join(lines)


def _generate_global_summary(stats: GlobalStats, output_format: str) -> str:
    """Generate a comprehensive summary of all projects."""
    if output_format == "markdown":
        lines = [
            "# Claude Code Project Analysis Summary",
            "",
            "## Overview",
            f"- **Total Projects**: {stats.total_projects}",
            f"- **Total Sessions**: {stats.total_sessions}",
            f"- **Total Messages**: {stats.total_messages}",
            f"- **Total Duration**: {stats.total_duration_str}",
            f"- **Total Storage**: {stats.total_size_mb:.1f} MB",
            f"- **Average Sessions per Project**: {stats.avg_sessions_per_project:.1f}",
            f"- **Average Messages per Session**: {stats.avg_messages_per_session:.1f}",
            "",
            f"**Most Active Project**: {stats.most_active_project}",
            f"**Largest Project**: {stats.largest_project}",
            f"**Most Recent Activity**: {stats.most_recent_activity.strftime('%Y-%m-%d %H:%M') if stats.most_recent_activity else 'unknown'}",
            "",
            "## Project Breakdown",
            "",
        ]

        # Add project breakdown
        for proj_stats in sorted(
            stats.projects, key=lambda p: p.total_messages, reverse=True
        ):
            lines.append(f"### {proj_stats.project.path}")
            lines.append(
                f"- **Sessions**: {proj_stats.total_sessions} ({proj_stats.main_sessions} main, {proj_stats.agent_sessions} agents)"
            )
            lines.append(
                f"- **Messages**: {proj_stats.total_messages} (avg: {proj_stats.avg_messages_per_session:.1f}/session)"
            )
            lines.append(f"- **Duration**: {proj_stats.total_duration_str}")
            lines.append(f"- **Size**: {proj_stats.total_size_mb:.1f} MB")
            lines.append("")

        # Add insights
        lines.append("## Key Insights")
        lines.append("")

        if stats.total_projects > 5:
            lines.append("- Diverse project portfolio with wide-ranging interests")

        if stats.avg_messages_per_session > 50:
            lines.append("- High engagement with detailed, intensive work sessions")

        most_active = max(stats.projects, key=lambda p: p.total_messages)
        if (
            most_active.total_messages
            > sum(p.total_messages for p in stats.projects) * 0.4
        ):
            lines.append(
                f"- **{most_active.project.path}** is your primary focus project"
            )

        lines.append("")
        lines.append("## ASCII Charts")
        lines.append("")

        # Enhanced charts with sparklines
        lines.append("### Session Distribution")
        max_sessions = max(p.total_sessions for p in stats.projects)
        session_data = [
            p.total_sessions
            for p in sorted(
                stats.projects, key=lambda p: p.total_sessions, reverse=True
            )
        ]

        # Add sparkline
        sparkline = safe_sparkline(session_data)
        if sparkline:
            lines.append(f"Session trend: {sparkline}")
            lines.append("")

        for proj_stats in sorted(
            stats.projects, key=lambda p: p.total_sessions, reverse=True
        ):
            bar_length = int((proj_stats.total_sessions / max_sessions) * 30)
            bar = "█" * bar_length
            lines.append(
                f"{proj_stats.project.path.split('/')[-1]:15} │{bar:30}│ {proj_stats.total_sessions}"
            )

        # Message volume sparkline
        lines.append("")
        lines.append("### Message Volume Trends")
        message_data = [
            p.total_messages
            for p in sorted(
                stats.projects, key=lambda p: p.total_messages, reverse=True
            )
        ]
        sparkline = safe_sparkline(message_data)
        if sparkline:
            lines.append(f"Message trend: {sparkline}")
            lines.append("")

        for proj_stats in sorted(
            stats.projects, key=lambda p: p.total_messages, reverse=True
        )[:5]:
            lines.append(
                f"• {proj_stats.project.path.split('/')[-1]}: {proj_stats.total_messages} messages"
            )

        return "\n".join(lines)

    else:  # text format
        lines = [
            "Claude Code Project Analysis Summary",
            "=" * 50,
            "",
            "Overview:",
            f"  Total Projects: {stats.total_projects}",
            f"  Total Sessions: {stats.total_sessions}",
            f"  Total Messages: {stats.total_messages}",
            f"  Total Duration: {stats.total_duration_str}",
            f"  Total Storage: {stats.total_size_mb:.1f} MB",
            f"  Avg Sessions/Project: {stats.avg_sessions_per_project:.1f}",
            f"  Avg Messages/Session: {stats.avg_messages_per_session:.1f}",
            "",
            f"Most Active Project: {stats.most_active_project}",
            f"Largest Project: {stats.largest_project}",
            f"Most Recent Activity: {stats.most_recent_activity.strftime('%Y-%m-%d %H:%M') if stats.most_recent_activity else 'unknown'}",
            "",
            "Project Breakdown:",
            "",
        ]

        # Add project breakdown
        for proj_stats in sorted(
            stats.projects, key=lambda p: p.total_messages, reverse=True
        ):
            lines.append(f"  {proj_stats.project.path}:")
            lines.append(
                f"    Sessions: {proj_stats.total_sessions} ({proj_stats.main_sessions} main, {proj_stats.agent_sessions} agents)"
            )
            lines.append(
                f"    Messages: {proj_stats.total_messages} (avg: {proj_stats.avg_messages_per_session:.1f}/session)"
            )
            lines.append(f"    Duration: {proj_stats.total_duration_str}")
            lines.append(f"    Size: {proj_stats.total_size_mb:.1f} MB")
            lines.append("")

        # Add insights
        lines.append("Key Insights:")
        lines.append("")

        if stats.total_projects > 5:
            lines.append("  • Diverse project portfolio with wide-ranging interests")

        if stats.avg_messages_per_session > 50:
            lines.append("  • High engagement with detailed, intensive work sessions")

        most_active = max(stats.projects, key=lambda p: p.total_messages)
        if (
            most_active.total_messages
            > sum(p.total_messages for p in stats.projects) * 0.4
        ):
            lines.append(
                f"  • {most_active.project.path} is your primary focus project"
            )

        return "\n".join(lines)


def _format_project_story(story: ProjectStory, format_type: str) -> str:
    """Format a project story for display."""
    if format_type == "brief":
        lines = [
            f"📖 {story.project_name.title()} Project Story",
            "=" * (len(story.project_name) + 18),
            "",
            f"📅 {story.lifecycle_days} days of development",
            f"🤝 {story.collaboration_style.lower()} ({story.agent_sessions} agents, {story.main_sessions} main sessions)",
            f"⚡ {story.total_messages} messages at {story.message_rate:.1f} msgs/hour",
            f"🎯 {story.work_pace.lower()} with {story.session_style.lower()}",
            f"🎭 {', '.join(story.personality_traits).lower()}",
        ]

        # Add concurrent usage if significant
        if story.concurrent_claude_instances > 1:
            lines.append(
                f"🔀 Used up to {story.concurrent_claude_instances} Claude instances in parallel"
            )

        lines.extend(
            [
                "",
                f"💡 Key insight: {story.insights[0] if story.insights else 'Steady progress'}",
            ]
        )
        return "\n".join(lines)

    elif format_type == "timeline":
        lines = [
            f"🕐 {story.project_name.title()} Development Timeline",
            "=" * (len(story.project_name) + 26),
            "",
            f"🌅 **Start**: {story.birth_date.strftime('%B %d, %Y at %I:%M %p')}",
            f"🌙 **End**: {story.last_active.strftime('%B %d, %Y at %I:%M %p')}",
            f"📊 **Duration**: {story.lifecycle_days} days",
            "",
        ]

        # Add sparkline for daily activity
        if story.daily_activity:
            sorted_days = sorted(story.daily_activity.keys())
            daily_values = [story.daily_activity[day] for day in sorted_days]
            sparkline = safe_sparkline(daily_values)
            if sparkline:
                lines.append(f"📈 Activity: {sparkline}")
                lines.append("")

        lines.append("### Daily Progress:")

        # Add daily highlights (simplified)
        if story.peak_day:
            lines.append(
                f"🏔️  **Peak**: {story.peak_day[1]} messages on {story.peak_day[0].strftime('%B %d')}"
            )

        lines.extend(
            [
                "",
                "### Work Patterns:",
                f"• **Style**: {story.session_style}",
                f"• **Collaboration**: {story.collaboration_style}",
                f"• **Pace**: {story.work_pace}",
                f"• **Personality**: {', '.join(story.personality_traits)}",
                "",
                f"📈 **Most Productive**: {story.most_productive_session.message_count} messages",
                f"⏱️  **Longest Session**: {story.longest_session_hours:.1f} hours",
            ]
        )

        # Add concurrent Claude usage insight
        if story.concurrent_claude_instances > 1:
            lines.append("")
            lines.append(
                f"🔀 **Parallel Workflow**: Used up to {story.concurrent_claude_instances} Claude instances simultaneously"
            )

        return "\n".join(lines)

    else:  # detailed format (default)
        lines = [
            f"📖 The Story of {story.project_name.title()}",
            "-" * (len(story.project_name) + 15),
            "",
            f"📅 Project Lifecycle: {story.lifecycle_days} days",
            f"   Born: {story.birth_date.strftime('%B %d, %Y at %I:%M %p')}",
            f"   Last Active: {story.last_active.strftime('%B %d, %Y at %I:%M %p')}",
            "",
        ]

        # Add sparkline for daily activity
        if story.daily_activity:
            sorted_days = sorted(story.daily_activity.keys())
            daily_values = [story.daily_activity[day] for day in sorted_days]
            sparkline = safe_sparkline(daily_values)
            if sparkline:
                lines.append(f"📈 Daily Activity: {sparkline}")
                lines.append("")

        lines.append(
            f"🏔️  Peak Activity: {story.peak_day[1]} messages on {story.peak_day[0].strftime('%B %d')}"
            if story.peak_day
            else "🏔️  Peak Activity: No data"
        )
        lines.extend(
            [
                "",
                f"🤖 Collaboration Pattern:",
                f"   Main Sessions: {story.main_sessions} (your direct work)",
                f"   Agent Sessions: {story.agent_sessions} (delegated tasks)",
                f"   Style: {story.collaboration_style}",
                "",
                f"⚡ Work Intensity:",
                f"   Total Messages: {story.total_messages}",
                f"   Development Time: {story.dev_time_hours:.1f} hours",
                f"   Message Rate: {story.message_rate:.1f} messages/hour",
                f"   Pace: {story.work_pace}",
                "",
                f"⏱️  Session Patterns:",
                f"   Average Session: {story.avg_session_hours:.1f} hours",
                f"   Longest Session: {story.longest_session_hours:.1f} hours",
                f"   Style: {story.session_style}",
                "",
            ]
        )

        # Add concurrent Claude usage section
        if story.concurrent_claude_instances > 1:
            lines.extend(
                [
                    f"🔀 Parallel Workflow:",
                    f"   Max concurrent instances: {story.concurrent_claude_instances}",
                    f"   Pattern: {'Heavy multi-tasking' if story.concurrent_claude_instances > 3 else 'Moderate parallelism'}",
                    "",
                ]
            )

        lines.extend(
            [
                f"🎭 Project Personality:",
                f"   {', '.join(story.personality_traits)}",
                "",
                f"💡 Key Insights:",
            ]
        )

        for insight in story.insights:
            lines.append(f"   • {insight}")

        return "\n".join(lines)


def _format_global_story(story: GlobalStory, format_type: str) -> str:
    """Format a global story for display."""
    if format_type == "brief":
        lines = [
            "🌍 Your Development Journey",
            "=" * 30,
            "",
            f"📊 {story.total_projects} projects, {story.total_messages} messages",
            f"⏱️  {story.total_dev_time:.1f} hours of creation",
            f"🤝 {story.avg_agent_ratio:.1f}x agent collaboration ratio",
            f"🎯 Common traits: {', '.join([trait[0] for trait in story.common_traits[:3]])}",
        ]
        return "\n".join(lines)

    elif format_type == "timeline":
        lines = [
            "🕐 Global Development Timeline",
            "=" * 35,
            "",
            "### Project Overview:",
        ]

        for proj_story in story.project_stories:
            lines.append(
                f"• **{proj_story.project_name}**: {proj_story.lifecycle_days} days, {proj_story.total_messages} messages"
            )

        lines.extend(
            [
                "",
                "### Work Patterns:",
                f"• **Total Projects**: {story.total_projects}",
                f"• **Total Development Time**: {story.total_dev_time:.1f} hours",
                f"• **Average Session Length**: {story.avg_session_length:.1f} hours",
                f"• **Agent Collaboration**: {story.avg_agent_ratio:.1f}x ratio",
                "",
                "### Personality Profile:",
            ]
        )

        for trait, count in story.common_traits:
            lines.append(f"• **{trait}**: {count} projects")

        return "\n".join(lines)

    else:  # detailed format (default)
        lines = [
            "🌍 Your Development Journey",
            "=" * 30,
            "",
            f"📊 Overview:",
            f"   Total Projects: {story.total_projects}",
            f"   Total Messages: {story.total_messages}",
            f"   Total Development Time: {story.total_dev_time:.1f} hours",
            f"   Average Agent Ratio: {story.avg_agent_ratio:.1f}x",
            f"   Average Session Length: {story.avg_session_length:.1f} hours",
            "",
            f"🎭 Your Development Personality:",
        ]

        for trait, count in story.common_traits:
            lines.append(f"   • {trait}: {count} projects")

        lines.extend(["", "📖 Individual Project Stories:", ""])

        for proj_story in story.project_stories:
            lines.extend(
                [
                    f"🎬 {proj_story.project_name.title()}:",
                    f"   {proj_story.lifecycle_days} days, {proj_story.total_messages} messages",
                    f"   {proj_story.collaboration_style.lower()}, {proj_story.work_pace.lower()}",
                    f"   {', '.join(proj_story.personality_traits).lower()}",
                    "",
                ]
            )

        if story.recent_activity:
            lines.extend(
                [
                    "🔄 Recent Activity:",
                ]
            )
            for timestamp, project_name in story.recent_activity[-5:]:
                lines.append(f"   {timestamp.strftime('%m/%d %H:%M')} - {project_name}")

        return "\n".join(lines)


@main.command()
@click.option("--year", "-y", type=int, default=None, help="Year to generate wrapped for (default: current year)")
@click.option("--name", "-n", type=str, default=None, help="Display name to show on wrapped cards")
@click.option("--raw", is_flag=True, help="Output raw JSON instead of URL")
@click.option("--no-copy", is_flag=True, help="Don't copy URL to clipboard")
@click.option("--decode", "-d", type=str, default=None, help="Decode and display a Wrapped URL")
@click.option("--example", is_flag=True, help="Show usage examples")
def wrapped(year: int, name: str, raw: bool, no_copy: bool, decode: str, example: bool):
    """Generate your Claude Code Wrapped URL for sharing.

    Creates a shareable URL containing your year-in-review stats.
    All data is encoded in the URL itself—no server storage.
    """
    import datetime as dt

    if example:
        show_examples("wrapped")
        return

    # Decode mode: inspect an existing URL
    if decode:
        _decode_wrapped_url(decode)
        return

    # Default to current year
    if year is None:
        year = dt.datetime.now().year

    # Validate year range (Claude Code didn't exist before 2024)
    current_year = dt.datetime.now().year
    if year < 2024:
        console.print(f"[red]Error: Year must be 2024 or later (Claude Code was released in 2024)[/red]")
        return
    if year > current_year + 1:
        console.print(f"[red]Error: Year cannot be more than 1 year in the future[/red]")
        return

    # Early January suggestion
    now = dt.datetime.now()
    if now.month == 1 and now.day <= 7 and year == now.year:
        # Check if previous year has more data
        try:
            prev_story = generate_wrapped_story_v3(year - 1, name)
            curr_story = generate_wrapped_story_v3(year, name)
            if prev_story.s > curr_story.s * 10:
                console.print(
                    f"[yellow]ℹ️  It's early {year} and you have much more activity in {year - 1}.[/yellow]"
                )
                console.print(f"[yellow]   Consider using --year {year - 1}[/yellow]")
                console.print()
        except ValueError:
            pass  # Ignore if either year has no data

    try:
        story = generate_wrapped_story_v3(year, name)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if raw:
        console.print_json(data=story.to_dict())
        return

    # Generate URL
    encoded = encode_wrapped_story_v3(story)
    url = f"https://{WRAPPED_URL_DOMAIN}/wrapped?d={encoded}"

    # Display summary
    _display_wrapped_summary(story, url, year)

    # Copy to clipboard
    if not no_copy:
        try:
            import pyperclip
            pyperclip.copy(url)
            console.print("\n[green]📋 Copied to clipboard![/green]")
        except (ImportError, OSError, RuntimeError):
            # ImportError: pyperclip not installed
            # OSError/RuntimeError: clipboard access failed (headless, permissions, etc.)
            console.print("\n[yellow]⚠️  Could not copy to clipboard[/yellow]")


def _decode_wrapped_url(url_or_data: str) -> None:
    """Decode and display a Wrapped V3 URL."""
    import re

    # Extract data from URL (V3 format: /wrapped?d=...)
    match = re.match(r"(?:https?://[^/]+)?/wrapped\?d=([A-Za-z0-9_-]+)", url_or_data)
    if not match:
        # Try old URL format (/year/data) or raw encoded data
        old_match = re.match(r"(?:https?://[^/]+/)?(\d{4})/([A-Za-z0-9_-]+)", url_or_data)
        if old_match:
            encoded_data = old_match.group(2)
        else:
            # Try as raw encoded data
            encoded_data = url_or_data
    else:
        encoded_data = match.group(1)

    try:
        story = decode_wrapped_story_v3(encoded_data)
    except ValueError as e:
        console.print(f"[red]Error: Failed to decode Wrapped URL[/red]")
        console.print(f"[dim]{e}[/dim]")
        return

    # Display decoded V3 data
    console.print("[bold cyan]🔍 Decoded Wrapped URL (V3)[/bold cyan]")
    console.print()
    console.print("━" * 50)
    console.print()
    console.print(f"[bold]Year:[/bold]           {story.y}")
    if story.n:
        console.print(f"[bold]Display Name:[/bold]   {story.n}")
    console.print()
    console.print("[bold]Core Stats:[/bold]")
    console.print(f"  Projects:     {story.p}")
    console.print(f"  Sessions:     {story.s}")
    console.print(f"  Messages:     {story.m:,}")
    console.print(f"  Hours:        {story.h}")
    console.print(f"  Days Active:  {story.d}")
    console.print()

    # Trait scores
    if story.ts:
        console.print("[bold]Coding Style (0-100):[/bold]")
        trait_names = {
            'ad': 'Delegation', 'sp': 'Deep Work', 'fc': 'Focus',
            'cc': 'Regularity', 'wr': 'Weekend', 'bs': 'Burst',
            'cs': 'Switching', 'mv': 'Verbose', 'td': 'Tools', 'ri': 'Intensity'
        }
        for key, name in trait_names.items():
            if key in story.ts:
                console.print(f"  {name:12} {story.ts[key]:3}")
        console.print()

    # Monthly activity sparkline
    if story.ma and any(story.ma):
        sparkline = safe_sparkline(story.ma)
        if sparkline:
            console.print("[bold]Monthly Activity:[/bold]")
            console.print(f"  {sparkline}")
            console.print("  J F M A M J J A S O N D")
            console.print()

    # Top projects (V3 format: [name, messages, hours, days, sessions, agent_ratio])
    if story.tp:
        console.print("[bold]Top Projects:[/bold]")
        for i, proj in enumerate(story.tp, 1):
            name = proj[0] if isinstance(proj, list) else proj.get('n', 'Unknown')
            msgs = proj[1] if isinstance(proj, list) else proj.get('m', 0)
            days = proj[3] if isinstance(proj, list) else proj.get('d', 0)
            console.print(f"  {i}. {name:20} {msgs:,} msgs, {days} days")
        console.print()

    # Streaks
    if story.sk and len(story.sk) >= 4 and story.sk[0] > 0:
        console.print("[bold]Streaks:[/bold]")
        console.print(f"  Total:    {story.sk[0]}")
        console.print(f"  Longest:  {story.sk[1]} days")
        console.print(f"  Current:  {story.sk[2]} days")
        console.print()

    console.print("━" * 50)
    console.print()
    console.print("[green]✓ This URL contains only aggregate statistics.[/green]")
    console.print("[dim]  No conversation content, code, or file paths.[/dim]")


def _display_wrapped_summary(story: WrappedStoryV3, url: str, year: int) -> None:
    """Display wrapped V3 summary with rich formatting."""
    console.print()
    console.print(f"[bold green]🎁 Your Claude Code Wrapped {year} is ready![/bold green]")
    console.print()
    console.print("━" * 50)
    console.print()
    console.print(f"[bold]📊[/bold] {story.p} projects | {story.s} sessions | {story.m:,} messages")
    console.print(f"[bold]⏱️[/bold]  {story.h} hours of development | {story.d} days active")

    # Show top trait descriptions based on scores
    trait_descs = []
    trait_map = {
        'ad': ('Hands-on', 'Delegates heavily'),
        'sp': ('Quick sessions', 'Marathon sessions'),
        'fc': ('Multi-project', 'Laser focused'),
        'ri': ('Light sessions', 'Intense sessions'),
    }
    for key, (low, high) in trait_map.items():
        if key in story.ts:
            score = story.ts[key]
            if score < 33:
                trait_descs.append(low)
            elif score > 67:
                trait_descs.append(high)
    if trait_descs:
        console.print(f"[bold]🎭[/bold] {', '.join(trait_descs[:3])}")
    console.print()

    # Monthly activity sparkline
    if story.ma and any(story.ma):
        sparkline = safe_sparkline(story.ma)
        if sparkline:
            console.print(f"[bold]📈[/bold] {sparkline}")
            console.print("   J F M A M J J A S O N D")
            console.print()

    console.print("━" * 50)
    console.print()
    console.print("[bold]Share your story:[/bold]")
    # Print URL without Rich formatting to ensure it's not truncated
    # Rich's overflow="ignore" was silently truncating the URL to terminal width
    print(url)


if __name__ == "__main__":
    main()
