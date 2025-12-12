# Trust

This document explains why you should (or shouldn't) trust claude-history-explorer with access to your Claude Code conversation history.

---

## The Trust Question

You're being asked to run a tool that reads your AI coding conversations. These conversations may contain:

- Proprietary code and architecture discussions
- API keys or secrets (accidentally pasted)
- Business logic and internal processes
- Personal coding struggles and questions

**You should be skeptical.** Here's how we address that skepticism.

---

## Guarantee #1: Read-Only by Design

The tool **never writes to, modifies, or deletes** your Claude Code history files.

### How We Enforce This

1. **Code design**: All file operations use read-only mode (`open(file, 'r')`)
2. **No write imports**: We don't import `shutil`, `os.remove`, or similar
3. **Automated verification**: Our test suite includes static analysis that fails if write operations are detected

### How You Can Verify

```bash
# Clone the repo
git clone https://github.com/adewale/claude-history-explorer
cd claude-history-explorer

# Search for write operations (should find none in core code)
grep -r "open.*'w'" claude_history_explorer/
grep -r "\.write(" claude_history_explorer/
grep -r "shutil\." claude_history_explorer/
grep -r "os\.remove" claude_history_explorer/

# Run the static analysis test
uv run pytest tests/test_history.py -k "read_only" -v
```

---

## Guarantee #2: No Network Calls

The tool **never sends data anywhere**. Your conversations stay on your machine.

### How We Enforce This

1. **No HTTP libraries**: We don't import `requests`, `httpx`, `urllib`, or `aiohttp`
2. **No network dependencies**: Check `pyproject.toml`—only `click`, `rich`, and `sparklines`
3. **Offline operation**: The tool works identically with no internet connection

### How You Can Verify

```bash
# Check dependencies (no network libraries)
cat pyproject.toml | grep dependencies -A 10

# Search for network imports
grep -r "import requests" claude_history_explorer/
grep -r "import httpx" claude_history_explorer/
grep -r "import urllib" claude_history_explorer/
grep -r "import socket" claude_history_explorer/

# Run with network disabled (tool should work fine)
# macOS/Linux:
unset http_proxy https_proxy
# Then run any command—it works offline
```

### The Exception: Wrapped URLs

The `wrapped` command generates a URL pointing to `wrapped-claude-codes.adewale-883.workers.dev`. However:

- **The CLI itself makes no network calls**—it just prints a URL
- **You choose whether to share that URL**
- **The URL contains encoded stats, not conversation content** (see below)

---

## Guarantee #3: Open Source & Auditable

The entire codebase is open source. You can read every line before running it.

### Repository Structure

```
claude_history_explorer/
├── __init__.py      # Just version metadata
├── constants.py     # Threshold values for analysis
├── history.py       # Data models and file parsing
└── cli.py           # Command implementations
```

**Total: ~2,600 lines of Python.** Small enough to audit in an afternoon.

### Key Files to Audit

| If you're concerned about... | Audit this file |
|------------------------------|-----------------|
| File access patterns | `history.py` lines 1-200 |
| What data is collected | `history.py` `Session` and `Message` classes |
| Command behavior | `cli.py` (each command is a function) |
| Wrapped URL encoding | `cli.py` `wrapped` command |

---

## Guarantee #4: Minimal Dependencies

We use only 3 runtime dependencies, all well-known and auditable:

| Dependency | Purpose | Weekly Downloads | Source |
|------------|---------|------------------|--------|
| `click` | CLI framework | 30M+ | [GitHub](https://github.com/pallets/click) |
| `rich` | Terminal formatting | 20M+ | [GitHub](https://github.com/Textualize/rich) |
| `sparklines` | ASCII charts | 100K+ | [GitHub](https://github.com/deeplook/sparklines) |

No dependency does anything with files or network. They only format output.

### Verify Dependencies

```bash
# See exactly what gets installed
uv pip compile pyproject.toml

# Or inspect the lock file
cat uv.lock
```

---

## Guarantee #5: What We Access

### Files We Read

```
~/.claude/projects/
├── -Users-you-project-path/
│   ├── *.jsonl          # We read these (conversation logs)
│   └── agent-*.jsonl    # We read these (agent conversations)
```

**That's it.** We don't read:
- Your source code files
- Your `.env` or credentials
- Your git history
- Any other dotfiles

### What We Parse From JSONL

Each line in a session file is a JSON object. We extract:

| Field | What We Use It For |
|-------|-------------------|
| `type` | Distinguish user vs assistant messages |
| `message.content` | Display in `show` command, search in `search` |
| `timestamp` | Calculate session duration, activity timeline |
| `message.usage` | Token counts for statistics |

We **do not** parse or store:
- Tool call contents (file reads, bash commands)
- Error messages or stack traces
- Model reasoning or chain-of-thought

---

## The Wrapped Feature: Additional Privacy Model

The `wrapped` command creates a shareable URL. Here's its specific trust model:

### What Gets Encoded in the URL

```
✓ Aggregate counts only:
  - Number of projects, sessions, messages
  - Total hours
  - Monthly activity (12 numbers)
  - Personality traits (computed labels)
  - Top project names (optional, can be excluded)

✗ Never included:
  - Actual conversation content
  - Code you wrote or discussed
  - File paths or project structure
  - Error messages or debugging sessions
  - Anything that could reveal proprietary information
```

### Verify What's in a URL

You can decode any Wrapped URL to see exactly what it contains:

```bash
claude-history wrapped --decode "https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJ5..."
```

This shows you the complete data—no hidden fields, no surprises.

### The Website's Trust Model

When someone visits a Wrapped URL:

1. **Data is in the URL, not our database**—we store nothing
2. **We decode and render on-the-fly**—no persistence
3. **OG images are generated transiently**—not logged
4. **No analytics that track individuals**—no cookies, no user IDs

You can verify this:
- View the website source code (link in footer)
- Open browser DevTools → Network tab → no tracking requests
- The URL works even if our server goes down (it's just data)

---

## Threat Model

### What This Tool Protects Against

| Threat | Protection |
|--------|------------|
| Tool modifying your files | Read-only guarantee (tested) |
| Data exfiltration to our servers | No network calls (auditable) |
| Hidden data collection | Open source, small codebase |
| Supply chain attacks | Minimal, auditable dependencies |
| Wrapped URL exposing secrets | Only aggregate counts, verifiable via `--decode` |

### What This Tool Does NOT Protect Against

| Threat | Why It's Out of Scope |
|--------|----------------------|
| Malware on your machine | If your machine is compromised, everything is |
| Someone with shell access | They can read `~/.claude/` directly |
| Screenshots of output | If you show someone your screen, they see it |
| Shared Wrapped URLs | You choose what to share—we can't unshare it |

---

## Reporting Security Issues

If you find a security vulnerability:

1. **Do NOT open a public issue**
2. Email: [security contact - add your email]
3. Include: description, reproduction steps, potential impact
4. We'll respond within 48 hours

For non-security bugs, open a regular GitHub issue.

---

## Summary

| Claim | How We Enforce It | How You Verify It |
|-------|-------------------|-------------------|
| Read-only | No write operations in code | `grep` for writes, run tests |
| No network | No HTTP libraries | Check deps, run offline |
| Auditable | Open source, small codebase | Read the 2,600 lines |
| Minimal deps | 3 well-known libraries | Check `pyproject.toml` |
| Wrapped privacy | Aggregate counts only | Use `--decode` on any URL |

**The bottom line**: You don't have to trust us. The code is small enough to read, the guarantees are testable, and the Wrapped URLs are decodable. Verify everything yourself.
