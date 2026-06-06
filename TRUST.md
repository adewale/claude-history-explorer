# Trust

This document explains what `claude-history-explorer` reads, writes, encodes, and sends.

## Core guarantee: history is read-only

The tool **never writes to, modifies, or deletes Claude Code history files** under `~/.claude/projects/`.

Allowed writes are explicit and user-controlled:
- `export --output`, `summary --output`, and `story --output` write the file path you provide.
- `wrapped` copies the generated URL to your clipboard by default; use `--no-copy` to disable this.
- The Wrapped website renders a URL you open/share; the CLI itself does not contact it.

Verify the history read-only behavior:

```bash
uv run pytest tests/test_history.py -k "read_only" -v
uv run pytest tests/test_audit_regressions.py -q
```

## Network model

The Python CLI has no HTTP client dependency and does not make network calls while reading, searching, exporting, or generating Wrapped data. It works offline.

Runtime dependencies are intentionally small and auditable:

| Dependency | Purpose |
|---|---|
| `click` | CLI framework |
| `rich` | Terminal formatting |
| `sparklines` | ASCII charts |
| `msgpack` | Compact Wrapped URL encoding |
| `pyperclip` | Optional clipboard copy for Wrapped URLs |

Verify dependencies:

```bash
cat pyproject.toml | grep dependencies -A 10
rg "import requests|import httpx|import urllib|import socket" claude_history_explorer
```

## Files read

The tool reads Claude Code session JSONL files:

```text
~/.claude/projects/
├── -Users-you-project-path/
│   ├── *.jsonl
│   └── agent-*.jsonl
```

It does not read your source tree, `.env`, git history, or other dotfiles.

## Data parsed from JSONL

| Field | Used for |
|---|---|
| `type` | user vs assistant messages |
| `message.content` | `show`, `search`, exports, statistics |
| `message.content[].tool_use` | tool names/inputs in `show`, `search`, JSON export, Wrapped tool diversity |
| `timestamp` | duration, activity, timelines |
| `message.usage` | token statistics |

Tool inputs can include file paths, shell commands, or pasted values. They are local by default, but they may appear in terminal output or JSON exports when you ask for those commands.

## Wrapped privacy model

`claude-history wrapped` creates a URL containing MessagePack/Base64URL-encoded aggregate data. The CLI prints the URL and optionally copies it; it does not upload it.

The encoded V3 payload can include:
- year, display name, project/session/message/hour/day counts
- monthly activity, heatmaps, distributions, trait scores, streaks
- top **short project names** and aggregate stats per project
- project co-occurrence edges, timeline events, session fingerprints
- token/model aggregate counts

It does **not** include conversation text, code content, full file paths, or tool input text.

Inspect any URL before sharing:

```bash
claude-history wrapped --decode "https://wrapped-claude-codes.adewale-883.workers.dev/wrapped?d=..."
```

## Wrapped website model

When you open a Wrapped URL, the Worker receives and decodes the encoded URL data to render the page and SVG social preview. Current behavior:
- no database, accounts, cookies, or analytics
- security/privacy headers are set (`no-store`, `no-referrer`, CSP, `nosniff`)
- per-user Wrapped HTML/SVG responses are not intentionally persisted in application storage or Cloudflare cache
- the website uses system fonts only; no Google Fonts requests

## Threat model

| Threat | Protection |
|---|---|
| Tool modifying history | History read-only code paths and tests |
| CLI data exfiltration | No CLI network calls |
| Hidden fields in Wrapped URLs | `wrapped --decode` exposes the payload |
| Malicious Wrapped URLs | Python and Worker decoders enforce Base64URL/size limits, runtime schema checks, bounded RLE, escaping, and CSP |
| Supply chain risk | Small dependency sets, `npm audit`, `ruff`, tests |

Out of scope: malware on your machine, someone with shell access to your account, screenshots/terminal logs you share, or a Wrapped URL you intentionally publish.

## Verification commands

```bash
uv run pytest -q
uv run ruff check .
uv run python scripts/smoketest_local_corpus.py
cd wrapped-website && npm test && npm run typecheck && npm run lint && npm audit
```

See [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md) for the audit lessons behind these checks.

The bottom line: you do not have to trust claims. Read the code, run the checks, and decode any Wrapped URL before sharing it.
