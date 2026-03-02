# Sketch: `claude-history frequency` command

## What it does

A new `frequency` subcommand that answers two questions:
1. **What do I keep asking Claude?** — most frequent user prompts, per-project and globally
2. **What does Claude keep running?** — most frequent Bash commands Claude invokes, per-project and globally

---

## UX / CLI interface

```
claude-history frequency [--project/-p PROJECT] [--limit/-n 20] [--format/-f table|json] [--example]
```

Output is two Rich tables, back to back:

```
┌─────────────────────────────────────────────────────────────┐
│                  Top Prompts (global)                        │
├──────┬──────────────────────────────────────────┬───────────┤
│ Rank │ Prompt (normalised)                      │ Count     │
├──────┼──────────────────────────────────────────┼───────────┤
│  1   │ run the tests                            │  47       │
│  2   │ fix the build                            │  31       │
│  3   │ commit and push                          │  28       │
│  ...                                                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               Top Bash Commands (global)                    │
├──────┬──────────────────────────────────────────┬───────────┤
│ Rank │ Command (normalised)                     │ Count     │
├──────┼──────────────────────────────────────────┼───────────┤
│  1   │ npm test                                 │ 112       │
│  2   │ git status                               │  89       │
│  3   │ python -m pytest                         │  64       │
│  ...                                                        │
└─────────────────────────────────────────────────────────────┘
```

When `--project/-p` is supplied, scoped to that project. Otherwise, global with a
"by project" breakdown column.

---

## Architecture: where the pieces go

### 1. New module: `frequency.py` (core logic, no I/O)

```python
# claude_history_explorer/frequency.py

@dataclass
class FrequencyResult:
    """Holds the two ranked lists."""
    prompt_counts:  list[tuple[str, int]]   # (normalised_prompt, count)
    bash_counts:    list[tuple[str, int]]   # (normalised_command, count)
    project_path:   str | None              # None = global

def compute_frequency(
    project: Project | None = None,
    limit: int = 20,
) -> FrequencyResult:
    """Walk sessions, tally prompts & bash commands, return ranked results."""
    ...
```

This function iterates over every session (via the existing `parse_session`), and for
each message:

- **User messages** → tally `msg.content` after normalisation (see below)
- **Assistant messages** → inspect `msg.tool_uses` for `{"name": "Bash", ...}` and
  tally `tool_use["input"]["command"]` after normalisation

Returns a `FrequencyResult` with two sorted-descending lists.

### 2. Normalisation functions (inside `frequency.py`)

Prompt normalisation is the crux of the problem. Raw user prompts have tons of
variance ("run the tests", "Run tests", "can you run the tests please?", "please run
tests again"). A simple exact-match counter would be nearly useless.

**Layered approach — start simple, get fancier later:**

#### Layer 0: Deterministic text cleanup (ship this first)
```python
def normalise_prompt(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)           # collapse whitespace
    text = text.strip('?.!,;:')                # strip trailing punctuation
    # strip common filler prefixes
    for prefix in ["can you ", "could you ", "please ", "go ahead and "]:
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text
```

#### Layer 1: Command-template extraction for Bash
```python
def normalise_bash(command: str) -> str:
    """Collapse arguments so 'cat foo.py' and 'cat bar.py' both become 'cat <file>'."""
    # Split on pipes first to handle pipelines
    parts = command.split('|')
    normalised_parts = []
    for part in parts:
        tokens = shlex.split(part.strip())
        if not tokens:
            continue
        binary = tokens[0]                       # e.g. "npm", "git", "python"
        # keep first subcommand if it looks like one (no leading -)
        subcmd = tokens[1] if len(tokens) > 1 and not tokens[1].startswith('-') else None
        normalised_parts.append(f"{binary} {subcmd}" if subcmd else binary)
    return " | ".join(normalised_parts)
```

So `git diff --staged src/foo.py` → `git diff`, `npm run build` → `npm run`,
`cat foo.py | grep error` → `cat | grep`.

This is intentionally lossy — we want to cluster by *intent*, not exact args.

#### Layer 2 (future, not in v1): Semantic clustering
Use embeddings or an LLM to cluster prompts that mean the same thing. Out of scope
for the first cut but the data structure (`list[tuple[str,int]]`) is ready for it —
just swap the normaliser.

### 3. CLI layer: new command in `cli.py`

```python
@main.command()
@click.option("--project", "-p", default=None, help="Scope to a specific project")
@click.option("--limit", "-n", default=20, help="Number of entries to show")
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table")
@click.option("--example", is_flag=True, help="Show usage examples")
def frequency(project, limit, format, example):
    """Show most frequently repeated prompts and Bash commands."""
    ...
```

Follows the exact same Click pattern as `stats`, `search`, etc. Delegates to
`compute_frequency()`, then renders with Rich tables.

### 4. Wire up in `history.py` (public API)

Add re-exports so the public API stays consistent:

```python
from .frequency import compute_frequency, FrequencyResult
```

---

## Key design decisions to make before implementation

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **Filter out very short prompts?** | Yes / No | Yes — skip prompts < 4 chars (e.g. "y", "ok") or make a `--min-length` flag |
| **Filter out agent sessions?** | Yes / No | No — agent Bash commands are interesting too |
| **Separate "per-project" breakdown in global mode?** | Inline column / Separate section | Separate section below, like `stats` does |
| **How deep to normalise Bash?** | Binary only / Binary+subcmd / Full template | Binary+subcmd is the sweet spot (Layer 1 above) |
| **Handle multi-line Bash (heredocs, &&-chains)?** | Split on && / Keep whole | Split on `&&` and `;`, tally each segment |
| **Prompt similarity threshold** | Exact-after-normalisation / Fuzzy | Exact-after-normalisation for v1; fuzzy is a follow-up |

---

## Data flow

```
~/.claude/projects/**/*.jsonl
        │
        ▼
   parse_session()          # existing parser, returns Session with Messages
        │
        ▼
  ┌─────┴──────┐
  │  for msg   │
  │  in session│
  └─────┬──────┘
        │
   ┌────┴─────────────────┐
   │ role == "user"?       │──yes──▶ normalise_prompt(msg.content) ──▶ prompt_counter[key] += 1
   │                       │
   │ role == "assistant"   │──yes──▶ for tu in msg.tool_uses:
   │   & has Bash tool_use │           if tu["name"] == "Bash":
   └───────────────────────┘             normalise_bash(tu["input"]["command"]) ──▶ bash_counter[key] += 1
        │
        ▼
  Counter.most_common(limit) → FrequencyResult
```

---

## Rough size estimate

| File | New / Modified | ~Lines |
|------|----------------|--------|
| `frequency.py` | **New** | ~120 |
| `cli.py` | Modified | ~60 (new command + rendering) |
| `history.py` | Modified | ~3 (re-exports) |
| `tests/test_frequency.py` | **New** | ~80 |
| **Total** | | **~260 lines** |

---

## Edge cases to handle

- **Empty prompts / whitespace-only** — skip
- **Very long prompts (pasted code blocks)** — truncate to first 200 chars before normalising (these are rarely "repeated")
- **Bash commands with secrets** — the data is already on disk in JSONL, so no new exposure, but truncate display of env vars / tokens in output
- **shlex.split failures** (unbalanced quotes) — fall back to simple `.split()`
- **No sessions found** — friendly "No history data found" message
