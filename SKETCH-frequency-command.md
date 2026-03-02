# Sketch: `claude-history frequency` command

## Why this exists

Every repeated prompt is a missing Skill. Every repeated Bash invocation is a missing
tool or hook. This command mines your Claude history to surface those patterns:

- **Repeated prompts** per-project and globally
- **Repeated Bash commands** per-project and globally

The command reports. The user interprets. A prompt you type 40 times across 12
projects might be a Skill waiting to be born, or it might just be how you work. A
Bash command Claude runs 100 times might deserve a hook — or not. That's your call.

---

## UX / CLI interface

```
claude-history frequency [--project/-p PROJECT] [--limit/-n 20] [--format/-f table|json] [--min-count 3] [--example]
```

### Default output: two tables

```
╭───────────────────────────────────────────────────────────────╮
│                   Repeated Prompts (global)                    │
├──────┬──────────────────────────────────┬───────┬─────────────┤
│ Rank │ Prompt                           │ Count │ Projects    │
├──────┼──────────────────────────────────┼───────┼─────────────┤
│  1   │ run the tests                    │  47   │ 12          │
│  2   │ commit and push                  │  28   │  9          │
│  3   │ fix the lint errors              │  22   │  1          │
│  4   │ review this PR                   │  18   │  7          │
│  ...                                                           │
╰───────────────────────────────────────────────────────────────╯

╭───────────────────────────────────────────────────────────────╮
│                Repeated Bash Commands (global)                 │
├──────┬──────────────────────────────────┬───────┬─────────────┤
│ Rank │ Command                          │ Count │ Projects    │
├──────┼──────────────────────────────────┼───────┼─────────────┤
│  1   │ npm test                         │ 112   │  5          │
│  2   │ git status                       │  89   │ 14          │
│  3   │ python -m pytest                 │  64   │  3          │
│  4   │ eslint --fix                     │  41   │  5          │
│  5   │ docker compose up                │  33   │  2          │
│  ...                                                           │
╰───────────────────────────────────────────────────────────────╯
```

**"Projects"** = how many distinct projects the pattern appears in. That's it — a
fact, not a recommendation.

When `--project/-p` is supplied, the "Projects" column is dropped (it would always
be 1).

`--format json` emits the full `FrequencyEntry` objects including the `examples`
list, so you can pipe it into other tools or inspect what raw prompts got bucketed
together.

---

## Architecture: where the pieces go

### 1. New module: `frequency.py` (core logic, no I/O)

```python
@dataclass
class FrequencyEntry:
    """A single row in the frequency table."""
    normalised:     str          # the canonical form (what gets displayed)
    count:          int          # total occurrences
    project_spread: int          # distinct projects it appears in
    projects:       list[str]    # which project paths
    examples:       list[str]    # 2-3 raw (pre-normalisation) strings for context

@dataclass
class FrequencyResult:
    """Complete output of the frequency analysis."""
    prompt_entries:  list[FrequencyEntry]
    bash_entries:    list[FrequencyEntry]
    project_path:    str | None    # None = global

def compute_frequency(
    project: Project | None = None,
    limit: int = 20,
    min_count: int = 3,
) -> FrequencyResult:
    """Walk sessions, tally prompts & bash commands, return ranked results."""
    ...
```

---

## Normalisation (the hard part)

The goal: collapse surface-level variation so that the same *intent* gets counted
once. Zero new dependencies — everything below uses `re`, `shlex`, and
`difflib` from the stdlib.

### Prompt normalisation: three passes

#### Pass 1 — Deterministic text cleanup

```python
def _clean_prompt(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)           # collapse whitespace
    text = text.strip('?.!,;:')                # trailing punctuation
    # strip filler prefixes (applied repeatedly until stable)
    changed = True
    while changed:
        changed = False
        for prefix in FILLER_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):]
                changed = True
    return text

FILLER_PREFIXES = [
    "can you ", "could you ", "would you ", "please ",
    "go ahead and ", "now ", "ok ", "okay ", "also ",
    "then ", "next ", "hey ", "hi ", "so ",
]
```

This handles "ok now please run the tests" → "run the tests".

#### Pass 2 — First-sentence extraction

Many user prompts are multi-line: an instruction followed by a pasted error trace,
code block, or context. The repeated part is almost always the first sentence.

```python
def _extract_instruction(text: str) -> str:
    """Pull out the actionable first sentence/line."""
    # If it has a code fence, only keep what's before it
    fence = text.find('```')
    if fence > 0:
        text = text[:fence]

    # Take the first line if multi-line
    first_line = text.split('\n')[0].strip()

    # If the first line is very long (>150 chars), it's probably pasted
    # content, not an instruction — fall back to first sentence
    if len(first_line) > 150:
        # Split on sentence-ending punctuation
        m = re.match(r'^(.+?[.!?])\s', first_line)
        if m:
            return m.group(1)
        return first_line[:150]

    return first_line
```

This is the single biggest improvement. Without it, a prompt like:

> run the tests
>
> ```
> ERROR: test_foo failed at line 42...
> (200 more lines)
> ```

Would never match the bare "run the tests". With it, both reduce to the same key.

#### Pass 3 — Stopword removal + simple stemming

No NLTK needed. A hardcoded stopword list and a minimal suffix stripper:

```python
STOPWORDS = {
    "the", "a", "an", "this", "that", "these", "those",
    "my", "your", "its", "our", "their",
    "is", "are", "was", "were", "be", "been", "being",
    "it", "for", "to", "in", "on", "of", "and", "or",
    "i", "me", "we", "us",
    "do", "does", "did",
    "all", "any", "some", "just", "only",
    "so", "if", "but", "not", "no",
    "up", "out", "about",
    "make", "sure",
}

def _remove_stopwords(text: str) -> str:
    tokens = text.split()
    kept = [t for t in tokens if t not in STOPWORDS]
    return ' '.join(kept) if kept else text   # never return empty

STEM_SUFFIXES = [
    ("ting", 1),   # "committing" → "commit" (strip "ting", keep 1+ char)
    ("ning", 1),   # "running" → "run"
    ("sing", 1),   # "using" → "u" — caught by min-length, so harmless
    ("ing", 1),    # "fixing" → "fix"
    ("tion", 2),   # "creation" → "crea" — imperfect but clusters
    ("sion", 2),   # "expression" → "expres"
    ("ment", 2),   # "deployment" → "deploy"
    ("ies", 1),    # "dependencies" → "dependenc"
    ("es", 2),     # "fixes" → "fix"
    ("ed", 2),     # "failed" → "fail"
    ("s", 2),      # "tests" → "test"
]

def _stem(word: str) -> str:
    for suffix, min_remaining in STEM_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= min_remaining:
            return word[:-len(suffix)]
    return word

def _stem_tokens(text: str) -> str:
    return ' '.join(_stem(t) for t in text.split())
```

Now "run the tests", "running tests", "please run test" all become `run test`.

#### Full pipeline

```python
def normalise_prompt(text: str) -> str:
    text = _extract_instruction(text)
    text = _clean_prompt(text)
    text = _remove_stopwords(text)
    text = _stem_tokens(text)
    return text
```

#### Pass 4 — Post-hoc merge with `difflib.SequenceMatcher`

After counting, we have a dict of `{normalised_key: count}`. Some entries will
still be near-duplicates that the deterministic passes didn't catch (e.g.,
"fix build error" vs "fix build failure"). A final merge pass:

```python
from difflib import SequenceMatcher

def _merge_similar(counter: Counter, threshold: float = 0.75) -> Counter:
    """Merge counter keys that are similar above threshold.

    O(n²) on number of distinct keys — fine because we only run this on
    entries that survived min_count filtering (typically <100).
    """
    keys = list(counter.keys())
    merged = {}          # canonical_key → total_count
    canonical_for = {}   # key → canonical_key (union-find style)

    for key in keys:
        best_match = None
        best_ratio = 0.0
        for canon in merged:
            ratio = SequenceMatcher(None, key, canon).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = canon
        if best_match and best_ratio >= threshold:
            merged[best_match] += counter[key]
            canonical_for[key] = best_match
        else:
            merged[key] = counter[key]
            canonical_for[key] = key

    return Counter(merged), canonical_for
```

This is the "semantic" layer — no embeddings, no LLM, just `difflib`. It handles
typos, synonym-ish variations, and minor wording differences. The threshold of 0.75
is conservative enough to avoid false merges but catches things like:
- "fix lint error" / "fix linting error" (0.88)
- "run test" / "run test again" (0.80)
- "commit push" / "commit and push" — already handled by stopword removal, but
  SequenceMatcher would catch it too (0.86)

The `canonical_for` mapping lets us populate `examples` correctly — we know which
raw strings got bucketed into which canonical key.

### Bash normalisation: two passes

Bash commands have less natural-language variance but more structural variance.

#### Pass 1 — Structural decomposition

```python
# Binaries where the subcommand is semantically important,
# and how many tokens after the binary form the "identity"
SUBCOMMAND_DEPTH = {
    "git": 1,        # git diff, git commit, git push
    "npm": 2,        # npm run test, npm run build
    "npx": 1,        # npx tsc, npx jest
    "yarn": 2,       # yarn run test
    "pnpm": 2,       # pnpm run build
    "cargo": 1,      # cargo build, cargo test
    "docker": 1,     # docker build, docker run
    "docker-compose": 1,  # docker-compose up
    "kubectl": 1,    # kubectl get, kubectl apply
    "python": 1,     # python -m pytest (special-cased below)
    "go": 1,         # go build, go test
    "make": 1,       # make build, make test
    "gh": 2,         # gh pr create, gh issue list
}

def _normalise_single_command(cmd: str) -> str:
    """Normalise a single command (no pipes, no &&)."""
    try:
        tokens = shlex.split(cmd.strip())
    except ValueError:
        tokens = cmd.strip().split()

    if not tokens:
        return cmd.strip()

    binary = os.path.basename(tokens[0])   # /usr/bin/python → python
    rest = tokens[1:]

    # Special case: python -m <module> → python -m <module>
    if binary == "python" and len(rest) >= 2 and rest[0] == "-m":
        return f"python -m {rest[1]}"

    # Look up how many subcommand tokens to keep
    depth = SUBCOMMAND_DEPTH.get(binary, 0)
    subcmd_tokens = []
    for token in rest[:depth]:
        if token.startswith('-'):
            break                          # stop at flags
        subcmd_tokens.append(token)

    if subcmd_tokens:
        return f"{binary} {' '.join(subcmd_tokens)}"
    return binary
```

This keeps `npm run test` intact (3 tokens) instead of collapsing it to `npm run`.
It also handles `python -m pytest` correctly, and strips full paths from binaries.

#### Pass 2 — Compound command splitting

```python
def normalise_bash(command: str) -> list[str]:
    """Split compound commands and normalise each segment.

    Returns a list because `cmd1 && cmd2` produces TWO frequency entries,
    not one entry for the combined string.
    """
    # Split on && and ; (but not inside quotes)
    segments = re.split(r'\s*(?:&&|;)\s*', command)
    # Split on | to handle pipelines — but keep the pipeline as one unit
    results = []
    for segment in segments:
        if '|' in segment:
            pipe_parts = segment.split('|')
            normalised_pipe = ' | '.join(
                _normalise_single_command(p) for p in pipe_parts
            )
            results.append(normalised_pipe)
        else:
            results.append(_normalise_single_command(segment))
    return [r for r in results if r]
```

Key insight: `&&`-chained commands get split into separate frequency entries (because
"git add . && git commit" is really two distinct actions), but pipelines stay together
(because `grep foo | wc -l` is one conceptual operation).

#### No SequenceMatcher merge for Bash

Bash commands cluster well with just the structural decomposition. Fuzzy matching
would over-merge: `npm run test` and `npm run build` should stay separate. So the
merge pass is prompt-only.

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
   ┌────┴────────────────────────┐
   │ role == "user"?              │   normalise_prompt(msg.content)
   │                              │──▶  prompt_counter[key] += 1
   │                              │     prompt_projects[key].add(project_path)
   │                              │     prompt_examples[key].append(raw_first_line)
   │                              │
   │ role == "assistant"          │   for tu in msg.tool_uses:
   │   & has Bash tool_use        │     for cmd in normalise_bash(tu["input"]["command"]):
   │                              │──▶    bash_counter[cmd] += 1
   └──────────────────────────────┘       bash_projects[cmd].add(project_path)
                                          bash_examples[cmd].append(raw_command)
        │
        ▼
  filter by min_count
        │
        ▼
  _merge_similar() on prompt keys   (difflib pass, prompts only)
        │
        ▼
  Counter.most_common(limit) → build FrequencyEntry list → FrequencyResult
```

---

## Key design decisions to make before implementation

| Decision | Options | Recommendation |
|----------|---------|----------------|
| **Filter out very short prompts?** | Yes / No | Yes — skip prompts < 4 chars (e.g. "y", "ok") via `--min-length` |
| **Filter out agent sessions?** | Yes / No | No — agent Bash commands are valuable signal |
| **Handle &&-chained Bash?** | Split / Keep whole | Split — each segment is a separate intent |
| **SequenceMatcher threshold** | 0.7 / 0.75 / 0.8 | 0.75 — conservative but catches real duplicates |
| **Show raw examples?** | Always / In JSON only | In `--format json` only — keeps the table clean |
| **difflib merge: prompts only or Bash too?** | Prompts only / Both | Prompts only — Bash clusters well structurally |

---

## Rough size estimate

| File | New / Modified | ~Lines |
|------|----------------|--------|
| `frequency.py` | **New** | ~250 (models, normalisation, merge, compute) |
| `cli.py` | Modified | ~60 (new command + Rich rendering) |
| `history.py` | Modified | ~3 (re-exports) |
| `tests/test_frequency.py` | **New** | ~150 (normalisation edge cases deserve good coverage) |
| **Total** | | **~460 lines** |

---

## Edge cases to handle

- **Empty prompts / whitespace-only** — skip
- **Very long prompts (pasted code blocks)** — first-sentence extraction handles this; raw paste never becomes the key
- **Bash commands with secrets** — data is already on disk in JSONL, no new exposure; truncate `export FOO=...` values in display
- **shlex.split failures** (unbalanced quotes) — fall back to `.split()`
- **No sessions found** — friendly "No history data found" message
- **Single-occurrence prompts** — filtered by `--min-count 3` default
- **Stemmer producing nonsense** — the stem is only used as a grouping key; `examples` stores the original wording for display context in JSON output
- **SequenceMatcher false merges** — the 0.75 threshold + post-stopword-removal input means the strings being compared are already short and semantically dense; false merges are rare but possible. `--format json` exposing `examples` makes misgroups inspectable
