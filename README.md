# Claude History Explorer
A Python CLI tool to explore, search and visualise your Claude Code conversation history.
The history is stored locally at `~/.claude/projects/` and this tool turns raw JSONL files into searchable conversations and insights about your coding journey.

## Highlights

- **Story Generation** - Analyzes sessions to create narratives about work patterns, personality traits, and collaboration style
- **Concurrent Claude Detection** - Identifies when you've used multiple Claude instances in parallel
- **Rich Terminal UI** - Tables, panels, sparklines, and syntax highlighting
- **Multiple Export Formats** - JSON, Markdown, plain text
- **Regex Search** - Search across all conversations with full regex support
- **Read-Only by Design** - Never modifies your Claude history files ([why trust this?](TRUST.md))
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

> **Tip:** Every command supports `--example` to show usage examples: `claude-history search --example`

### projects

List all Claude Code projects sorted by last use.

```bash
claude-history projects
claude-history projects -n 10        # Limit to 10 projects
```

| Option | Description |
|--------|-------------|
| `-n, --limit` | Maximum projects to show (default: 20) |

### sessions

List sessions for a project. Search is a partial match on project path.

```bash
claude-history sessions myproject
claude-history sessions "Documents/work" -n 5
```

| Option | Description |
|--------|-------------|
| `-n, --limit` | Maximum sessions to show (default: 20) |

### show

Display messages from a session. Session ID can be a partial match.

```bash
claude-history show e5c477f0
claude-history show e5c477f0 -n 100
claude-history show e5c477f0 --raw
claude-history show e5c477f0 -p myproject
```

| Option | Description |
|--------|-------------|
| `-p, --project` | Limit search to specific project |
| `-n, --limit` | Maximum messages to show (default: 50) |
| `--raw` | Output raw JSON |

### search

Search for a regex pattern across all conversations.

```bash
claude-history search "TODO"
claude-history search "error.*fix"
claude-history search "bug" -p myproject
claude-history search "API" -c
claude-history search "function" -C 200
```

| Option | Description |
|--------|-------------|
| `-p, --project` | Limit search to specific project |
| `-c, --case-sensitive` | Case-sensitive search |
| `-n, --limit` | Maximum results to show (default: 20) |
| `-C, --context` | Characters of context around match (default: 100) |

### export

Export a session to JSON, Markdown, or plain text.

```bash
claude-history export e5c477f0 -f markdown -o session.md
claude-history export e5c477f0 -f json -o session.json
claude-history export e5c477f0 -f text
claude-history export e5c477f0 -p myproject -f json
```

| Option | Description |
|--------|-------------|
| `-p, --project` | Limit search to specific project |
| `-f, --format` | Output format: `json`, `markdown`, `text` (default: markdown) |
| `-o, --output` | Output file (default: stdout) |

### info

Show Claude Code storage location and usage statistics.

```bash
claude-history info
```

### stats

Show detailed statistics including message counts, duration, storage size, and agent usage.

```bash
claude-history stats
claude-history stats -p myproject
claude-history stats -f json
```

| Option | Description |
|--------|-------------|
| `-p, --project` | Show stats for specific project only |
| `-f, --format` | Output format: `table`, `json` (default: table) |

### summary

Generate a comprehensive summary with insights and charts.

```bash
claude-history summary
claude-history summary -p myproject
claude-history summary -f markdown -o report.md
```

| Option | Description |
|--------|-------------|
| `-p, --project` | Generate summary for specific project |
| `-f, --format` | Output format: `text`, `markdown` (default: text) |
| `-o, --output` | Output file (default: stdout) |

### story

Tell the story of your development journey with personality insights and patterns.

```bash
claude-history story
claude-history story -p myproject
claude-history story -f brief
claude-history story -f timeline -o journey.md
```

| Option | Description |
|--------|-------------|
| `-p, --project` | Tell story for specific project |
| `-f, --format` | Story format: `brief`, `detailed`, `timeline` (default: detailed) |
| `-o, --output` | Output file (default: stdout) |

Generates narrative insights including project lifecycle, collaboration style, work intensity, personality traits, and timeline visualization with sparklines.

### wrapped

Generate a shareable Wrapped URL containing your year's stats. All data is encoded in the URL—nothing is stored on any server.

```bash
claude-history wrapped
claude-history wrapped -y 2024
claude-history wrapped -n "Your Name"
claude-history wrapped --raw
claude-history wrapped --decode "https://..."
```

| Option | Description |
|--------|-------------|
| `-y, --year` | Year to generate wrapped for (default: current year) |
| `-n, --name` | Display name to show on wrapped cards |
| `--raw` | Output raw JSON instead of URL |
| `--no-copy` | Don't copy URL to clipboard |
| `-d, --decode` | Decode and display a Wrapped URL |

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
