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

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text
from sparklines import sparklines

from .history import (
    list_projects,
    find_project,
    parse_session,
    search_sessions,
    get_session_by_id,
    get_projects_dir,
    calculate_project_stats,
    calculate_global_stats,
    generate_project_story,
    generate_global_story,
    ProjectStats,
    GlobalStats,
    ProjectStory,
)

__all__ = ["main"]

console = Console()

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
  claude-history sessions myproject -n 5     # Show only 5 sessions
""",
    "show": """
Examples:
  claude-history show abc123                 # Show session by ID (partial match)
  claude-history show abc123 --limit 20      # Show first 20 messages
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
@click.option("--limit", "-n", default=20, help="Maximum number of projects to show")
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
        last_mod = (
            proj.last_modified.strftime("%Y-%m-%d %H:%M")
            if proj.last_modified
            else "unknown"
        )
        table.add_row(proj.path, str(proj.session_count), last_mod)

    console.print(table)

    if len(all_projects) > limit:
        console.print(
            f"\n[dim]Showing {limit} of {len(all_projects)} projects. Use --limit to see more.[/dim]"
        )


@main.command()
@click.argument("project_search", required=False)
@click.option("--limit", "-n", default=20, help="Maximum number of sessions to show")
@click.option("--example", is_flag=True, help="Show usage examples")
def sessions(project_search: str, limit: int, example: bool):
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

    for session_file in project.session_files[:limit]:
        session = parse_session(session_file, project.path)
        start_str = (
            session.start_time.strftime("%Y-%m-%d %H:%M")
            if session.start_time
            else "unknown"
        )
        slug = (
            session.slug[:20] + "..."
            if session.slug and len(session.slug) > 20
            else (session.slug or "")
        )

        table.add_row(
            session.session_id[:12] + "...",
            str(session.message_count),
            str(session.user_message_count),
            session.duration_str,
            start_str,
            slug,
        )

    console.print(table)

    if project.session_count > limit:
        console.print(
            f"\n[dim]Showing {limit} of {project.session_count} sessions. Use --limit to see more.[/dim]"
        )


@main.command()
@click.argument("session_id", required=False)
@click.option("--project", "-p", default=None, help="Project path to search in")
@click.option("--limit", "-n", default=50, help="Maximum messages to show")
@click.option("--raw", is_flag=True, help="Show raw JSON output")
@click.option("--example", is_flag=True, help="Show usage examples")
def show(session_id: str, project: str, limit: int, raw: bool, example: bool):
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

    if raw:
        for msg in session.messages[:limit]:
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

    for i, msg in enumerate(session.messages[:limit]):
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
            if len(content) > 2000:
                content = (
                    content[:2000]
                    + "\n\n[dim]... (truncated, use --raw for full content)[/dim]"
                )
            console.print(content)

        # Show tool uses
        if msg.tool_uses:
            for tool in msg.tool_uses:
                console.print(f"\n[yellow]Tool: {tool['name']}[/yellow]")
                if tool.get("input"):
                    input_preview = json.dumps(tool["input"], indent=2)
                    if len(input_preview) > 500:
                        input_preview = input_preview[:500] + "\n..."
                    console.print(Syntax(input_preview, "json", theme="monokai"))

        console.print()

    if session.message_count > limit:
        console.print(
            f"[dim]Showing {limit} of {session.message_count} messages. Use --limit to see more.[/dim]"
        )


@main.command()
@click.argument("pattern", required=False)
@click.option(
    "--project", "-p", default=None, help="Limit search to a specific project"
)
@click.option("--case-sensitive", "-c", is_flag=True, help="Case-sensitive search")
@click.option("--limit", "-n", default=20, help="Maximum results to show")
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
                console.print(f"  {content[:200]}...")

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
        with open(output, "w", encoding="utf-8") as f:
            f.write(result)
        console.print(f"[green]Exported to {output}[/green]")
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
            with open(output, "w", encoding="utf-8") as f:
                f.write(summary_text)
            console.print(f"[green]Summary written to {output}[/green]")
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

            story_data = generate_project_story(proj, output_format)
            story_text = _format_project_story(story_data, output_format)
        else:
            story_data = generate_global_story()
            story_text = _format_global_story(story_data, output_format)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(story_text)
            console.print(f"[green]Story written to {output}[/green]")
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
    from .history import get_claude_dir, get_projects_dir

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


def _display_project_stats(stats: ProjectStats, output_format: str):
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


def _display_global_stats(stats: GlobalStats, output_format: str):
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
        last_active = (
            proj_stats.most_recent_session.strftime("%Y-%m-%d %H:%M")
            if proj_stats.most_recent_session
            else "unknown"
        )
        table.add_row(
            proj_stats.project.path,
            str(proj_stats.total_sessions),
            str(proj_stats.total_messages),
            f"{proj_stats.total_size_mb:.1f} MB",
            proj_stats.total_duration_str,
            last_active,
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
        try:
            if len(session_data) > 1:
                sparkline_list = sparklines(session_data)
                if sparkline_list:
                    lines.append(f"Session trend: {sparkline_list[0]}")
                    lines.append("")
        except (ValueError, TypeError):
            pass  # sparklines may fail with invalid data

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
        try:
            if len(message_data) > 1:
                sparkline_list = sparklines(message_data)
                if sparkline_list:
                    lines.append(f"Message trend: {sparkline_list[0]}")
                    lines.append("")
        except (ValueError, TypeError):
            pass  # sparklines may fail with invalid data

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
            "",
            f"💡 Key insight: {story.insights[0] if story.insights else 'Steady progress'}",
        ]
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
            try:
                if len(daily_values) > 1:
                    sparkline_list = sparklines(daily_values)
                    if sparkline_list:
                        lines.append(f"📈 Activity: {sparkline_list[0]}")
                        lines.append("")
            except (ValueError, TypeError):
                pass  # sparklines may fail with invalid data

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
                f"📈 **Most Productive**: {story.most_productive_session['message_count']} messages",
                f"⏱️  **Longest Session**: {story.longest_session_hours:.1f} hours",
            ]
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
            try:
                if len(daily_values) > 1:
                    sparkline_list = sparklines(daily_values)
                    if sparkline_list:
                        lines.append(f"📈 Daily Activity: {sparkline_list[0]}")
                        lines.append("")
            except (ValueError, TypeError):
                pass  # sparklines may fail with invalid data

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
                f"🎭 Project Personality:",
                f"   {', '.join(story.personality_traits)}",
                "",
                f"💡 Key Insights:",
            ]
        )

        for insight in story.insights:
            lines.append(f"   • {insight}")

        return "\n".join(lines)


def _format_global_story(story_data: dict, format_type: str) -> str:
    """Format a global story for display."""
    if format_type == "brief":
        lines = [
            "🌍 Your Development Journey",
            "=" * 30,
            "",
            f"📊 {story_data['total_projects']} projects, {story_data['total_messages']} messages",
            f"⏱️  {story_data['total_dev_time']:.1f} hours of creation",
            f"🤝 {story_data['avg_agent_ratio']:.1f}x agent collaboration ratio",
            f"🎯 Common traits: {', '.join([trait[0] for trait in story_data['common_traits'][:3]])}",
        ]
        return "\n".join(lines)

    elif format_type == "timeline":
        lines = [
            "🕐 Global Development Timeline",
            "=" * 35,
            "",
            "### Project Overview:",
        ]

        for proj_story in story_data["project_stories"]:
            lines.append(
                f"• **{proj_story.project_name}**: {proj_story.lifecycle_days} days, {proj_story.total_messages} messages"
            )

        lines.extend(
            [
                "",
                "### Work Patterns:",
                f"• **Total Projects**: {story_data['total_projects']}",
                f"• **Total Development Time**: {story_data['total_dev_time']:.1f} hours",
                f"• **Average Session Length**: {story_data['avg_session_length']:.1f} hours",
                f"• **Agent Collaboration**: {story_data['avg_agent_ratio']:.1f}x ratio",
                "",
                "### Personality Profile:",
            ]
        )

        for trait, count in story_data["common_traits"]:
            lines.append(f"• **{trait}**: {count} projects")

        return "\n".join(lines)

    else:  # detailed format (default)
        lines = [
            "🌍 Your Development Journey",
            "=" * 30,
            "",
            f"📊 Overview:",
            f"   Total Projects: {story_data['total_projects']}",
            f"   Total Messages: {story_data['total_messages']}",
            f"   Total Development Time: {story_data['total_dev_time']:.1f} hours",
            f"   Average Agent Ratio: {story_data['avg_agent_ratio']:.1f}x",
            f"   Average Session Length: {story_data['avg_session_length']:.1f} hours",
            "",
            f"🎭 Your Development Personality:",
        ]

        for trait, count in story_data["common_traits"]:
            lines.append(f"   • {trait}: {count} projects")

        lines.extend(["", "📖 Individual Project Stories:", ""])

        for proj_story in story_data["project_stories"]:
            lines.extend(
                [
                    f"🎬 {proj_story.project_name.title()}:",
                    f"   {proj_story.lifecycle_days} days, {proj_story.total_messages} messages",
                    f"   {proj_story.collaboration_style.lower()}, {proj_story.work_pace.lower()}",
                    f"   {', '.join(proj_story.personality_traits).lower()}",
                    "",
                ]
            )

        if story_data["recent_activity"]:
            lines.extend(
                [
                    "🔄 Recent Activity:",
                ]
            )
            for timestamp, project_name in story_data["recent_activity"][-5:]:
                lines.append(f"   {timestamp.strftime('%m/%d %H:%M')} - {project_name}")

        return "\n".join(lines)


if __name__ == "__main__":
    main()
