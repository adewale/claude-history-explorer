# Sketch: `claude-history frequency` command

## Why this exists

Every repeated prompt is a missing Skill. Every repeated Bash invocation is a missing
tool or hook. This command mines your Claude history to surface those automation
opportunities:

- **Repeated prompts** → candidates for **Skills** (slash commands) or
  **CLAUDE.md instructions** that eliminate the need to ask at all
- **Repeated Bash commands** → candidates for **hooks** (session-start, pre/post tool),
  **MCP tools**, or built-in tool configurations
- **Per-project patterns** → project-specific hooks or CLAUDE.md rules
- **Cross-project patterns** → global Skills or `~/.claude/settings.json` additions

The output isn't just a frequency table — it's an **actionable audit** of what you
and Claude are doing by hand that could be automated.

---

## UX / CLI interface

```
claude-history frequency [--project/-p PROJECT] [--limit/-n 20] [--format/-f table|json] [--min-count 3] [--example]
```

### Default output: two tables with an automation-hint column

```
╭──────────────────────────────────────────────────────────────────────────╮
│              Repeated Prompts — Skill & Instruction Candidates           │
├──────┬───────────────────────────────┬───────┬───────┬──────────────────┤
│ Rank │ Prompt (normalised)           │ Count │ Where │ Opportunity      │
├──────┼───────────────────────────────┼───────┼───────┼──────────────────┤
│  1   │ run the tests                 │  47   │ 12 pr │ Skill / Hook     │
│  2   │ commit and push               │  28   │  9 pr │ Skill            │
│  3   │ fix the lint errors           │  22   │  1 pr │ CLAUDE.md rule   │
│  4   │ review this PR                │  18   │  7 pr │ Skill            │
│  ...                                                                     │
╰──────────────────────────────────────────────────────────────────────────╯

╭──────────────────────────────────────────────────────────────────────────╮
│            Repeated Bash Commands — Tool & Hook Candidates               │
├──────┬───────────────────────────────┬───────┬───────┬──────────────────┤
│ Rank │ Command (normalised)          │ Count │ Where │ Opportunity      │
├──────┼───────────────────────────────┼───────┼───────┼──────────────────┤
│  1   │ npm test                      │ 112   │ 5 pr  │ Hook             │
│  2   │ git status                    │  89   │ 14 pr │ (built-in)       │
│  3   │ python -m pytest              │  64   │ 3 pr  │ Hook             │
│  4   │ eslint --fix                  │  41   │ 5 pr  │ Hook             │
│  5   │ docker compose up             │  33   │ 2 pr  │ Session hook     │
│  ...                                                                     │
╰──────────────────────────────────────────────────────────────────────────╯
```

The **"Where"** column shows project spread: `12 pr` = seen in 12 projects.
Single-project patterns get `1 pr` — those are project-local hook candidates.

The **"Opportunity"** column is a heuristic classification:
- **Skill** — prompt appears across many projects → global slash command
- **CLAUDE.md rule** — prompt is specific to one project → project instruction
- **Hook** — Bash command runs repeatedly → automate via hook
- **Session hook** — setup/infra command (docker, server starts) → session-start hook
- **(built-in)** — already a Claude Code tool (git status, read, etc.) — noise, dimmed

### With `--project/-p`: scoped view, different framing

```
╭──────────────────────────────────────────────────────────────────────────╮
│    Repeated Prompts in my-web-app — CLAUDE.md & Skill Candidates         │
├──────┬───────────────────────────────┬───────┬──────────────────────────┤
│ Rank │ Prompt (normalised)           │ Count │ Suggestion               │
├──────┼───────────────────────────────┼───────┼──────────────────────────┤
│  1   │ run the tests                 │  12   │ Add to CLAUDE.md or hook │
│  2   │ fix the lint errors           │  22   │ Pre-commit hook          │
│  ...                                                                     │
╰──────────────────────────────────────────────────────────────────────────╯
```

When scoped, "Where" is replaced by **"Suggestion"** — more specific advice since
we know the project context.

---

## Architecture: where the pieces go

### 1. New module: `frequency.py` (core logic, no I/O)

```python
# claude_history_explorer/frequency.py

@dataclass
class FrequencyEntry:
    """A single row in the frequency table."""
    normalised:   str              # the normalised prompt or command
    count:        int              # total occurrences
    project_spread: int            # how many distinct projects it appears in
    projects:     list[str]        # which project paths (for drill-down)
    opportunity:  str              # "skill" | "hook" | "session_hook" | "claude_md" | "built_in"
    examples:     list[str]        # 2-3 raw (pre-normalisation) examples for context

@dataclass
class FrequencyResult:
    """Complete output of the frequency analysis."""
    prompt_entries:  list[FrequencyEntry]
    bash_entries:    list[FrequencyEntry]
    project_path:    str | None       # None = global

def compute_frequency(
    project: Project | None = None,
    limit: int = 20,
    min_count: int = 3,
) -> FrequencyResult:
    """Walk sessions, tally prompts & bash commands, classify opportunities."""
    ...
```

This function iterates over every session (via the existing `parse_session`), and for
each message:

- **User messages** → tally `msg.content` after normalisation
- **Assistant messages** → inspect `msg.tool_uses` for `{"name": "Bash", ...}` and
  tally `tool_use["input"]["command"]` after normalisation

Then **classifies each entry** by opportunity type (see below) and returns a
`FrequencyResult` with two ranked lists.

### 2. Opportunity classification (the interesting part)

After counting, each entry gets tagged with a heuristic opportunity type. This is
what turns a frequency table into actionable output.

```python
# Bash commands that already map to built-in Claude Code tools — noise to dim
BUILT_IN_COMMANDS = {
    "git status", "git diff", "git log", "git add", "git commit",
    "cat", "head", "tail", "ls", "find", "grep", "rg",
}

# Patterns that suggest session-start / environment setup
SESSION_SETUP_PATTERNS = [
    r"docker compose", r"docker run", r"npm start", r"npm run dev",
    r"python -m \w+\.server", r"rails server", r"cargo build",
    r"source .*/bin/activate", r"nvm use", r"export \w+=",
]

def classify_prompt_opportunity(entry) -> str:
    """Classify a repeated prompt as a potential automation."""
    if entry.project_spread >= 3:
        return "skill"             # cross-project → global slash command
    elif entry.project_spread == 1:
        return "claude_md"         # single-project → project-level instruction
    else:
        return "skill"             # 2 projects — lean toward skill

def classify_bash_opportunity(entry) -> str:
    """Classify a repeated Bash command as a potential automation."""
    cmd = entry.normalised
    if cmd in BUILT_IN_COMMANDS:
        return "built_in"          # already a tool, dim in output
    for pattern in SESSION_SETUP_PATTERNS:
        if re.match(pattern, cmd):
            return "session_hook"  # runs at start of session
    if entry.project_spread >= 3:
        return "hook"              # cross-project → global hook
    else:
        return "hook"              # project-specific → project hook
```

The classification is intentionally simple and wrong-sometimes — the goal is to
**prompt the user to think** about what to automate, not to be a perfect classifier.

### 3. Normalisation functions

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
    for prefix in ["can you ", "could you ", "please ", "go ahead and ",
                    "now ", "ok ", "okay ", "also ", "then ", "next "]:
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
for the first cut but the data structures are ready for it — just swap the normaliser.

### 4. CLI layer: new command in `cli.py`

```python
@main.command()
@click.option("--project", "-p", default=None, help="Scope to a specific project")
@click.option("--limit", "-n", default=20, help="Number of entries to show")
@click.option("--min-count", default=3, help="Minimum occurrences to show")
@click.option("--format", "-f", type=click.Choice(["table", "json"]), default="table")
@click.option("--example", is_flag=True, help="Show usage examples")
def frequency(project, limit, min_count, format, example):
    """Surface repeated prompts and commands — find missing Skills and hooks."""
    ...
```

Follows the exact same Click pattern as `stats`, `search`, etc. Delegates to
`compute_frequency()`, then renders with Rich tables. Entries classified as
`built_in` are dimmed. The `examples` field is shown on hover / in `--format json`
for context on what the normalised bucket actually captures.

### 5. Wire up in `history.py` (public API)

Add re-exports so the public API stays consistent:

```python
from .frequency import compute_frequency, FrequencyResult, FrequencyEntry
```

---

## Key design decisions to make before implementation

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **Filter out very short prompts?** | Yes / No | Yes — skip prompts < 4 chars (e.g. "y", "ok") via `--min-length` |
| **Filter out agent sessions?** | Yes / No | No — agent Bash commands are valuable signal too |
| **How deep to normalise Bash?** | Binary only / Binary+subcmd / Full template | Binary+subcmd is the sweet spot (Layer 1 above) |
| **Handle &&-chained Bash?** | Split on && / Keep whole | Split on `&&` and `;`, tally each segment separately |
| **Prompt similarity threshold** | Exact-after-normalisation / Fuzzy | Exact-after-normalisation for v1; fuzzy is a follow-up |
| **Show raw examples?** | Always / On flag / In JSON only | Store 2-3 examples always; show in table with `--verbose`, always in `--format json` |
| **Dim built-in commands?** | Yes / Hide them / Show normally | Dim them — they're noise but still informative |

---

## Data flow

```
~/.claude/projects/**/*.jsonl
        │
        ▼
   parse_session()            # existing parser, returns Session with Messages
        │
        ▼
  ┌─────┴──────┐
  │  for msg   │  (tracking current project_path throughout)
  │  in session│
  └─────┬──────┘
        │
   ┌────┴──────────────────────┐
   │ role == "user"?            │──yes──▶ normalise_prompt(msg.content)
   │                            │         prompt_counter[key] += 1
   │                            │         prompt_projects[key].add(project_path)
   │                            │         prompt_examples[key].append(raw)
   │                            │
   │ role == "assistant"        │──yes──▶ for tu in msg.tool_uses:
   │   & has Bash tool_use      │           if tu["name"] == "Bash":
   └────────────────────────────┘             normalise_bash(tu["input"]["command"])
                                              bash_counter[key] += 1
                                              bash_projects[key].add(project_path)
                                              bash_examples[key].append(raw)
        │
        ▼
  Counter.most_common(limit)
        │
        ▼
  classify_prompt_opportunity() / classify_bash_opportunity()
        │
        ▼
  FrequencyResult with FrequencyEntry list (count + spread + opportunity + examples)
```

---

## Rough size estimate

| File | New / Modified | ~Lines |
|------|----------------|--------|
| `frequency.py` | **New** | ~200 (models, normalisation, classification, compute) |
| `cli.py` | Modified | ~80 (new command + Rich rendering with opportunity column) |
| `history.py` | Modified | ~3 (re-exports) |
| `tests/test_frequency.py` | **New** | ~120 |
| **Total** | | **~400 lines** |

---

## Edge cases to handle

- **Empty prompts / whitespace-only** — skip
- **Very long prompts (pasted code blocks)** — truncate to first 200 chars before normalising (these are rarely "repeated"; they're one-off pastes, not automation candidates)
- **Bash commands with secrets** — the data is already on disk in JSONL, so no new exposure, but truncate display of env vars / tokens in rendered output
- **shlex.split failures** (unbalanced quotes) — fall back to simple `.split()`
- **No sessions found** — friendly "No history data found" message
- **Single-occurrence prompts** — filtered by `--min-count 3` default so the table only shows genuinely repeated patterns

---

## Future extensions (not in v1, but the data model supports them)

1. **`--generate-skill`** — pick entry #N from the table, scaffold a Claude Code
   Skill TOML file from it (pre-filled with the prompt pattern as the trigger)
2. **`--generate-hook`** — pick entry #N from the Bash table, scaffold a hook config
   for `settings.json` or `.claude/hooks/`
3. **`--diff`** — compare frequency between two time windows ("what did I stop asking
   after I added that hook last month?")
4. **Semantic clustering (Layer 2)** — group "run tests", "execute the test suite",
   "make sure tests pass" into one bucket using embeddings
5. **Integration with `wrapped`** — surface top automation opportunities in the
   year-end wrapped story
