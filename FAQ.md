# Frequently Asked Questions

## What is Claude History Explorer?

A CLI tool to explore your Claude Code conversation history stored locally at `~/.claude/projects/`. It turns raw JSONL files into searchable conversations, statistics, and insights about your coding journey.

## Is my data safe?

Yes. See [TRUST.md](TRUST.md) for the complete trust model. The short version:

| Guarantee | How It's Enforced |
|-----------|-------------------|
| **Read-only** | No write operations in code, verified by tests |
| **No network calls** | No HTTP libraries, works offline |
| **Auditable** | Open source, ~2,600 lines of Python |
| **Minimal deps** | Only `click`, `rich`, `sparklines` |

Your conversation data stays on your machine. Nothing is sent to any server.

**Don't trust us—verify it yourself:**

```bash
# Check for write operations (should find none)
grep -r "open.*'w'" claude_history_explorer/

# Check for network libraries (should find none)
grep -r "import requests" claude_history_explorer/

# Run the read-only verification test
uv run pytest tests/test_history.py -k "read_only" -v
```

## Will you support other AI coding agents?

Not at this time. We've researched the feasibility of supporting other agents:

| Agent | Location | Format | Feasibility | Data Richness |
|-------|----------|--------|-------------|---------------|
| **Claude Code** | `~/.claude/projects/` | JSONL | ✅ Supported | High (tokens, costs, tools) |
| **OpenCode** | `.opencode/` | JSON | ✅ Easy | Very High |
| **Aider** | `.aider.chat.history.md` | Markdown | ✅ Easy | Medium |
| **Continue.dev** | `~/.continue/` | JSON + SQLite | ✅ Easy | High |
| **Cline** | VS Code globalState | JSON | ⚠️ Medium | High |
| **OpenAI Codex CLI** | `~/.codex/` | TOML/JSON | ⚠️ Medium | Medium |
| **Cursor** | App data dir | Unknown | ❌ Hard | Unknown |
| **Windsurf** | App data dir | Unknown | ❌ Hard | Unknown |
| **GitHub Copilot** | Cloud primary | Proprietary | ❌ Hard | Minimal |
| **Gemini Code Assist** | Cloud only | N/A | ❌ Impossible | None |

Several agents (OpenCode, Aider, Continue.dev) would be relatively easy to add. If there's demand, we may add support in the future. Open an issue if you'd like to see a specific agent supported.

## Where does Claude Code store its history?

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

## What's the difference between "main" and "agent" sessions?

- **Main sessions**: Your direct conversations with Claude Code
- **Agent sessions**: Sub-tasks that Claude delegated to background agents

The `story` command analyzes the ratio between these to determine your "collaboration style" (e.g., "Heavy delegation" vs "Hands-on").

## What does "concurrent Claude instances" mean?

The tool detects when you were running multiple Claude Code sessions simultaneously (within 30 minutes of each other). This indicates parallel workflows—working on multiple tasks or projects at once.

## How do I generate my "Wrapped" story?

Run:
```bash
claude-history story
```

For a specific project:
```bash
claude-history story -p myproject
```

Different formats:
```bash
claude-history story --format brief
claude-history story --format detailed
claude-history story --format timeline
```

## Can I export my conversations?

Yes. Use the `export` command:

```bash
# Export to Markdown
claude-history export <session-id> -f markdown -o session.md

# Export to JSON
claude-history export <session-id> -f json -o session.json

# Export to plain text
claude-history export <session-id> -f text
```

## How do I view messages from a specific project?

Finding and viewing messages is a three-step process:

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  projects    │ ───► │  sessions    │ ───► │    show      │
│              │      │  <project>   │      │  <session>   │
│ "Find your   │      │ "List the    │      │ "View the    │
│  project"    │      │  sessions"   │      │  messages"   │
└──────────────┘      └──────────────┘      └──────────────┘
```

**Step 1: Find your project**
```bash
claude-history projects
```

**Step 2: List sessions for that project** (partial name match works)
```bash
claude-history sessions orange_garden
```

**Step 3: View messages from a session**
```bash
claude-history show <session-id> -n 5
```

**Note:** The `-n` flag shows the *first* N messages, not the last. To see the last messages of a long session:

```bash
# Option 1: Export and use tail
claude-history export <session-id> -f text | tail -50

# Option 2: Show more messages and scroll to the end
claude-history show <session-id> -n 200
```

## How do I show the last 5 messages from my project?

The `--limit` (`-n`) flag shows the *first* N messages, not the last. To see the most recent messages:

**Option 1: Export and pipe to `tail`**
```bash
# Get the session ID first
claude-history sessions myproject

# Export and show last 5 messages
claude-history export <session-id> -f text | tail -20
```

**Option 2: Use a large limit and scroll**
```bash
claude-history show <session-id> -n 500
# Then scroll to the bottom
```

**Option 3: Export to a file and view the end**
```bash
claude-history export <session-id> -f markdown -o session.md
tail -50 session.md
```

**Tip:** Sessions are sorted by most recent first, so the first session listed in `claude-history sessions myproject` is your latest conversation.

## How do I search across all my conversations?

```bash
# Simple search
claude-history search "TODO"

# Regex search
claude-history search "error.*fix"

# Search specific project
claude-history search "bug" -p myproject

# Case-sensitive
claude-history search "APIError" --case-sensitive
```

## What do the personality traits mean?

The `story` command classifies your work style:

**Collaboration style:**
- **Heavy delegation**: High ratio of agent sessions to main sessions
- **Balanced collaboration**: Mix of direct work and delegation
- **Hands-on**: Mostly direct interaction, few delegated tasks

**Work pace:**
- **Rapid-fire development**: >30 messages/hour
- **Steady, productive flow**: 20-30 messages/hour
- **Deliberate, thoughtful work**: 10-20 messages/hour
- **Careful, methodical development**: <10 messages/hour

**Session style:**
- **Marathon sessions**: Average session >2 hours
- **Extended sessions**: Average 1-2 hours
- **Standard sessions**: Average 30min-1 hour
- **Quick sprints**: Average <30 minutes

## The tool says "No projects found"

Make sure:
1. You have Claude Code installed and have used it at least once
2. The `~/.claude/projects/` directory exists
3. You're running the command as the same user who runs Claude Code

Check with:
```bash
claude-history info
```

## How do I install it?

Using `uv` (recommended):
```bash
uv tool install claude-history-explorer
```

Using pip:
```bash
pip install claude-history-explorer
```

From source:
```bash
git clone https://github.com/adewale/claude-history-explorer
cd claude-history-explorer
uv sync
uv run claude-history --help
```

## How do I get help for a specific command?

Every command has an `--example` flag:
```bash
claude-history search --example
claude-history story --example
claude-history export --example
```

Or use `--help`:
```bash
claude-history stats --help
```
