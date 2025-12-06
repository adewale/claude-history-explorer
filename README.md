# Claude History Explorer

A CLI tool to explore your Claude Code conversation history stored locally at `~/.claude/projects/`. Turns raw JSONL files into searchable conversations and insights about your coding journey.

## Highlights

- **Story Generation** - Analyzes sessions to create narratives about work patterns, personality traits, and collaboration style
- **Concurrent Claude Detection** - Identifies when you've used multiple Claude instances in parallel
- **Rich Terminal UI** - Tables, panels, sparklines, and syntax highlighting
- **Multiple Export Formats** - JSON, Markdown, plain text
- **Regex Search** - Search across all conversations with full regex support
- **Read-Only by Design** - Never modifies your Claude history files
- **Streaming JSONL** - Line-by-line parsing handles large files efficiently

### Example Output

```
📖 Keyboardia Project Story
============================

📅 3 days of development
🤝 heavy delegation (16 agents, 2 main sessions)
⚡ 1873 messages at 25.0 msgs/hour
🎯 steady, productive flow with marathon sessions
🎭 agent-driven, deep-work focused, high-intensity
🔀 Used up to 3 Claude instances in parallel

💡 Key insight: Most productive session: 1530 messages
```

## Installation

Using `uv` (recommended):

```bash
# Install directly
uv tool install .

# Or run without installing
uv run claude-history --help
```

Using pip:

```bash
pip install .
```

## Usage

### List all projects

```bash
claude-history projects
```

Shows all projects you've used Claude Code with, sorted by last use.

### List sessions for a project

```bash
claude-history sessions lempicka
claude-history sessions "Documents/myproject"
```

Shows all conversation sessions for a project. The search is a partial match on the project path.

### View a session

```bash
claude-history show e5c477f0
claude-history show e5c477f0 --limit 100
claude-history show e5c477f0 --raw
```

Shows the conversation messages from a session. Session ID can be a partial match.

### Search across conversations

```bash
# Search all projects
claude-history search "TODO"

# Search with regex
claude-history search "error.*fix"

# Search specific project
claude-history search "prompt" -p lempicka

# Case-sensitive search
claude-history search "APIError" --case-sensitive
```

### Export a session

```bash
# Export to Markdown
claude-history export e5c477f0 -f markdown -o session.md

# Export to JSON
claude-history export e5c477f0 -f json -o session.json

# Export to plain text
claude-history export e5c477f0 -f text
```

### Show storage info

```bash
claude-history info
```

Shows where Claude Code stores data and statistics about your usage.

### View statistics

```bash
# Global statistics
claude-history stats

# Project-specific statistics
claude-history stats -p auriga

# JSON output format
claude-history stats --format json
```

Shows detailed statistics including message counts, duration, storage size, and agent usage.

### Generate summary

```bash
# Global summary (text format)
claude-history summary

# Project-specific summary
claude-history summary -p auriga

# Markdown format
claude-history summary --format markdown

# Save to file
claude-history summary -o summary.md
```

Generates a comprehensive summary with insights, ASCII bar charts, and sparklines for trend visualization. The summary command reuses the stats functionality for analysis.

### Tell project story

```bash
# Global story of all projects
claude-history story

# Story for specific project
claude-history story -p auriga

# Different story formats
claude-history story --format brief
claude-history story --format detailed
claude-history story --format timeline

# Save story to file
claude-history story -p auriga -o auriga_story.md
```

Generates narrative insights about your development journey, including:
- **Project lifecycle** and evolution patterns
- **Collaboration style** and agent usage patterns
- **Work intensity** and session patterns
- **Project personality** traits
- **Key insights** and productivity patterns
- **Timeline visualization** with sparklines showing daily activity patterns

The story command transforms raw conversation data into compelling narratives about your coding journey, work patterns, and development personality.

## How Claude Code Stores History

Claude Code stores conversation history in:

```
~/.claude/projects/
├── -Users-username-path-to-project1/
│   ├── session-id-1.jsonl
│   ├── session-id-2.jsonl
│   └── agent-xyz.jsonl
├── -Users-username-path-to-project2/
│   └── ...
```

- Project directories are named with the path encoded (slashes become dashes)
- Each `.jsonl` file is a conversation session
- Files prefixed with `agent-` are sub-agent conversations
- Each line in a JSONL file is a JSON object representing a message or event

## Development

```bash
# Clone and install in dev mode
git clone <repo>
cd claude-history-explorer
uv sync

# Run tests
uv run pytest

# Run the CLI
uv run claude-history --help
```

## License

MIT
