"""CLI interface for Claude Code History Explorer."""

import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

from .history import (
    list_projects,
    find_project,
    parse_session,
    search_sessions,
    get_session_by_id,
    get_projects_dir,
)

console = Console()


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
def projects(limit: int):
    """List all Claude Code projects."""
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
        last_mod = proj.last_modified.strftime("%Y-%m-%d %H:%M") if proj.last_modified else "unknown"
        table.add_row(proj.path, str(proj.session_count), last_mod)

    console.print(table)

    if len(all_projects) > limit:
        console.print(f"\n[dim]Showing {limit} of {len(all_projects)} projects. Use --limit to see more.[/dim]")


@main.command()
@click.argument("project_search")
@click.option("--limit", "-n", default=20, help="Maximum number of sessions to show")
def sessions(project_search: str, limit: int):
    """List sessions for a project.

    PROJECT_SEARCH can be a partial path match (e.g., 'lempicka' or 'Documents/myproject')
    """
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
        start_str = session.start_time.strftime("%Y-%m-%d %H:%M") if session.start_time else "unknown"
        slug = session.slug[:20] + "..." if session.slug and len(session.slug) > 20 else (session.slug or "")

        table.add_row(
            session.session_id[:12] + "...",
            str(session.message_count),
            str(session.user_message_count),
            session.duration_str,
            start_str,
            slug
        )

    console.print(table)

    if project.session_count > limit:
        console.print(f"\n[dim]Showing {limit} of {project.session_count} sessions. Use --limit to see more.[/dim]")


@main.command()
@click.argument("session_id")
@click.option("--project", "-p", default=None, help="Project path to search in")
@click.option("--limit", "-n", default=50, help="Maximum messages to show")
@click.option("--raw", is_flag=True, help="Show raw JSON output")
def show(session_id: str, project: str, limit: int, raw: bool):
    """Show messages from a specific session.

    SESSION_ID can be a partial match of the session ID.
    """
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
                "tool_uses": msg.tool_uses
            }
            console.print(json.dumps(output, indent=2))
        return

    console.print(Panel(
        f"[bold]Session:[/bold] {session.session_id}\n"
        f"[bold]Project:[/bold] {session.project_path}\n"
        f"[bold]Messages:[/bold] {session.message_count} ({session.user_message_count} from user)\n"
        f"[bold]Duration:[/bold] {session.duration_str}\n"
        f"[bold]Slug:[/bold] {session.slug or 'N/A'}",
        title="Session Info"
    ))

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
                content = content[:2000] + "\n\n[dim]... (truncated, use --raw for full content)[/dim]"
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
        console.print(f"[dim]Showing {limit} of {session.message_count} messages. Use --limit to see more.[/dim]")


@main.command()
@click.argument("pattern")
@click.option("--project", "-p", default=None, help="Limit search to a specific project")
@click.option("--case-sensitive", "-c", is_flag=True, help="Case-sensitive search")
@click.option("--limit", "-n", default=20, help="Maximum results to show")
@click.option("--context", "-C", default=100, help="Characters of context around match")
def search(pattern: str, project: str, case_sensitive: bool, limit: int, context: int):
    """Search for a pattern across all conversations.

    PATTERN is a regular expression to search for.

    Examples:
        claude-history search "TODO"
        claude-history search "error.*fix" -p myproject
        claude-history search "def.*function" --case-sensitive
    """
    proj = find_project(project) if project else None

    console.print(f"[bold]Searching for:[/bold] {pattern}")
    if proj:
        console.print(f"[bold]In project:[/bold] {proj.path}")
    console.print()

    results_count = 0
    for session, messages in search_sessions(pattern, proj, case_sensitive):
        if results_count >= limit:
            break

        console.print(Panel(
            f"[bold]Session:[/bold] {session.session_id[:12]}...\n"
            f"[bold]Project:[/bold] {session.project_path}\n"
            f"[bold]Matches:[/bold] {len(messages)}",
            title="Match Found",
            border_style="green"
        ))

        for msg in messages[:3]:  # Show first 3 matching messages
            role_style = "blue" if msg.role == "user" else "green"
            console.print(f"[{role_style}]{msg.role.upper()}:[/{role_style}]")

            # Show context around match
            content = msg.content
            import re
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
@click.argument("session_id")
@click.option("--project", "-p", default=None, help="Project path to search in")
@click.option("--format", "-f", "output_format", type=click.Choice(["json", "markdown", "text"]), default="markdown")
@click.option("--output", "-o", default=None, help="Output file (default: stdout)")
def export(session_id: str, project: str, output_format: str, output: str):
    """Export a session to various formats.

    SESSION_ID can be a partial match of the session ID.
    """
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
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "tool_uses": msg.tool_uses
                }
                for msg in session.messages
            ]
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
            ""
        ]

        for msg in session.messages:
            timestamp = msg.timestamp.strftime("%Y-%m-%d %H:%M:%S") if msg.timestamp else ""
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
            ""
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
def info():
    """Show Claude Code storage information."""
    from .history import get_claude_dir, get_projects_dir

    claude_dir = get_claude_dir()
    projects_dir = get_projects_dir()

    console.print(Panel(
        f"[bold]Claude directory:[/bold] {claude_dir}\n"
        f"[bold]Projects directory:[/bold] {projects_dir}\n"
        f"[bold]Directory exists:[/bold] {projects_dir.exists()}",
        title="Claude Code Storage Info"
    ))

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


if __name__ == "__main__":
    main()
