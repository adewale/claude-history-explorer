# Claude History Explorer

A CLI tool to explore your Claude Code conversation history.

Claude Code stores all conversation history locally at `~/.claude/projects/` as JSONL files. This tool helps you browse, search, and export that history.

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
