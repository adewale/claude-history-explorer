# Claude History Explorer

Python CLI tool to explore, search, and visualize Claude Code conversation history.

**GitHub:** thenullwell/claude-history-explorer
**MAVERICK relevance:** Transcript mining for INT-077 (Constitutional Articles), INT-078 (Conversation Import)

---

## What This Is

Reads `~/.claude/projects/` JSONL files and provides:
- Session search (regex across all conversations)
- Story generation (work patterns, personality, collaboration style)
- Concurrent Claude detection
- Multiple export formats (JSON, Markdown, plain text)
- Rich terminal UI (tables, panels, sparklines)

Read-only by design — never modifies history files.

---

## Usage

```bash
# Install
pip install -e .

# Search sessions
claude-history search "MAVERICK"

# List sessions
claude-history list
```

---

## Git Workflow

Commit message format: `<type>: <description>` (feat, fix, docs, chore, test, refactor)

---

## Related

- **Mimir transcript miner:** `~/mimir/tools/transcript-miner.py` (complementary tool)
- **Conversation archive:** `~/mimir/tools/conversation-archive.py` (web export importer)
