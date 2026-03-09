# `claude-history frequency` — Specification

## Summary

A command that scans Claude Code conversation history and reports the most
frequently repeated user prompts and Bash commands, ranked by count with
project-spread metadata. The command reports facts. It does not classify,
recommend, or generate anything.

---

## Data Model

### FrequencyEntry

A single row in either the prompt or command frequency table.

```python
@dataclass
class FrequencyEntry:
    normalised:     str        # Canonical form displayed to the user
    count:          int        # Total occurrences across all matched sessions
    project_spread: int        # Distinct projects this pattern appears in
    projects:       list[str]  # Project paths (for drill-down / JSON output)
    examples:       list[str]  # 2–3 raw (pre-normalisation) strings
```

**Invariants:**
- `count >= min_count` (default 3; configurable via `--min-count`)
- `project_spread >= 1`
- `len(examples) <= 3`
- `normalised` is never empty

### FrequencyResult

The complete output of a frequency analysis.

```python
@dataclass
class FrequencyResult:
    prompt_entries: list[FrequencyEntry]  # Ranked by count descending
    bash_entries:   list[FrequencyEntry]  # Ranked by count descending
    project_path:   str | None            # None = global analysis
```

**Invariants:**
- `len(prompt_entries) <= limit` (default 20; configurable via `--limit`)
- `len(bash_entries) <= limit`
- Both lists are sorted by `count` descending, ties broken by `project_spread`
  descending

---

## CLI Interface

```
claude-history frequency [OPTIONS]
```

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--project / -p` | `str` | `None` | Scope analysis to a single project (partial match) |
| `--limit / -n` | `int` | `20` | Maximum entries per table |
| `--min-count` | `int` | `3` | Minimum occurrences to include |
| `--min-length` | `int` | `4` | Minimum prompt character length (filters "y", "ok") |
| `--format / -f` | `table\|json` | `table` | Output format |
| `--example` | flag | `false` | Show usage examples |

### Table Output (default)

Two Rich tables, one for prompts, one for Bash commands:

```
╭────────────────────────────────────────────────────────╮
│              Repeated Prompts (global)                   │
├──────┬─────────────────────────────┬───────┬────────────┤
│ Rank │ Prompt                      │ Count │ Projects   │
├──────┼─────────────────────────────┼───────┼────────────┤
│  1   │ run the tests               │  47   │ 12         │
│  2   │ commit and push             │  28   │  9         │
│  ...                                                     │
╰────────────────────────────────────────────────────────╯
```

When `--project` is supplied, the "Projects" column is omitted (always 1).

### JSON Output (`--format json`)

```json
{
  "project": null,
  "prompts": [
    {
      "normalised": "run the tests",
      "count": 47,
      "project_spread": 12,
      "projects": ["/Users/me/foo", "/Users/me/bar", ...],
      "examples": [
        "Run the tests",
        "can you please run the tests?",
        "run tests again"
      ]
    }
  ],
  "commands": [...]
}
```

The `examples` field is always present in JSON output. It shows the original
(pre-normalisation) strings that were bucketed into this entry, so the user
can inspect what the normaliser grouped together.

---

## Normalisation

### Design Principles

1. **Zero new dependencies.** Everything uses `re`, `shlex`, `os.path`, and
   `difflib` from the Python stdlib.
2. **Prompts and commands are normalised differently.** Prompts have
   natural-language variance (synonyms, politeness, filler). Commands have
   structural variance (arguments, paths, flags). Unifying them into one
   pipeline would make both worse.
3. **Normalisation is lossy by design.** The goal is to cluster by *intent*,
   not to preserve exact wording. The `examples` field preserves originals.
4. **The merge function is pluggable.** `SequenceMatcher` is the v1
   implementation, but the interface (`SimilarityMerger` protocol) allows
   swapping in character n-gram Jaccard or other algorithms.

### Prompt Normalisation Pipeline

Four passes, applied in order:

#### Pass 1: First-sentence extraction

Most user prompts are an instruction followed by context (error traces, code
blocks, file contents). The repeated part is the instruction.

```
Input:  "run the tests\n```\nERROR: test_foo failed at line 42...\n```"
Output: "run the tests"
```

Rules:
- If the text contains a code fence (`` ``` ``), keep only what precedes it
- Take the first line of the remaining text
- If that first line exceeds 150 characters, extract the first sentence
  (up to `.`, `!`, or `?` followed by whitespace), or truncate at 150

#### Pass 2: Deterministic text cleanup

```
Input:  "Ok now please run the tests?"
Output: "run the tests"
```

Rules:
- Lowercase
- Collapse whitespace to single spaces
- Strip leading/trailing whitespace
- Strip trailing punctuation (`?.!,;:`)
- Iteratively strip filler prefixes until stable:
  `can you`, `could you`, `would you`, `please`, `go ahead and`,
  `now`, `ok`, `okay`, `also`, `then`, `next`, `hey`, `hi`, `so`

"Iteratively" means `"ok now please run the tests"` strips `ok ` → `now ` →
`please ` → `"run the tests"` in one pass through the loop.

#### Pass 3: Stopword removal + Porter stemming

```
Input:  "running the tests"
Output: "run test"
```

**Stopwords** (hardcoded, ~50 words): common English function words that carry
no intent signal. See `frequency.py` for the full list. If removal would produce
an empty string, the original is returned.

**Stemming** uses a pure-Python implementation of the Porter stemming algorithm
(~260 lines, public domain). This is a proper implementation of the 5-step
algorithm, not a suffix table. Key improvements over naive suffix stripping:
- "dependencies" → "depend" (not "dependenc")
- "running" → "run" (not "runn")
- "caresses" → "caress" (not "caresse")
- Handles irregular cases: "ponies" → "poni", "ties" → "ti"

#### Pass 4: Post-hoc similarity merge

After counting, entries whose normalised keys are similar above a threshold
are merged. The canonical key is the one with the higher count. The merge
function conforms to the `SimilarityMerger` protocol:

```python
class SimilarityMerger(Protocol):
    def merge(
        self,
        counter: Counter[str],
        threshold: float,
    ) -> tuple[Counter[str], dict[str, str]]:
        """Merge similar keys.

        Returns:
            merged_counter: New counter with merged keys
            canonical_for:  Mapping from original key → canonical key
        """
        ...
```

**v1 implementation: `SequenceMatcherMerger`**

Uses `difflib.SequenceMatcher.ratio()`. O(n²) on distinct keys, but n is
bounded by the number of entries surviving `min_count` filtering (typically
< 100).

Default threshold: **0.75**. Rationale:
- "fix build error" / "fix build failure" → 0.81 (merged, correct)
- "run test" / "fix lint" → 0.35 (not merged, correct)
- "commit push" / "commit" → 0.77 (merged — borderline but acceptable since
  stopword removal already stripped "and")

**Future alternative: `CharNgramJaccardMerger`**

Uses set-of-character-trigrams Jaccard similarity. Sometimes outperforms
SequenceMatcher on short strings. Same interface, drop-in replacement.

### Bash Normalisation Pipeline

Two passes. No stemming, no stopword removal, no similarity merge.

#### Pass 1: Structural decomposition

Each command segment is reduced to its identity: the binary name plus a
configurable number of subcommand tokens.

```
Input:  "npm run test --verbose --coverage"
Output: "npm run test"

Input:  "python -m pytest tests/test_foo.py -v"
Output: "python -m pytest"

Input:  "/usr/local/bin/git diff --staged src/foo.py"
Output: "git diff"
```

Rules:
- Extract binary name via `os.path.basename` (strips full paths)
- Special case: `python -m <module>` → `python -m <module>`
- For other binaries, keep N subcommand tokens from the depth table:

| Binary | Depth | Example | Result |
|--------|-------|---------|--------|
| `git` | 1 | `git commit -m "msg"` | `git commit` |
| `npm` | 2 | `npm run test` | `npm run test` |
| `npx` | 1 | `npx tsc --strict` | `npx tsc` |
| `yarn` | 2 | `yarn run build` | `yarn run build` |
| `pnpm` | 2 | `pnpm run dev` | `pnpm run dev` |
| `cargo` | 1 | `cargo test -- --nocapture` | `cargo test` |
| `docker` | 1 | `docker build -t img .` | `docker build` |
| `docker-compose` | 1 | `docker-compose up -d` | `docker-compose up` |
| `kubectl` | 1 | `kubectl get pods -n ns` | `kubectl get` |
| `go` | 1 | `go test ./...` | `go test` |
| `make` | 1 | `make build` | `make build` |
| `gh` | 2 | `gh pr create --title t` | `gh pr create` |

- Subcommand tokens stop at the first token starting with `-` (a flag)
- Binaries not in the table get depth 0 (binary name only)
- `shlex.split` failures (unbalanced quotes) fall back to `.split()`

#### Pass 2: Compound command splitting

```
Input:  "git add . && git commit -m 'fix'"
Output: ["git add", "git commit"]       # two separate entries

Input:  "grep foo | wc -l"
Output: ["grep | wc"]                   # one entry (pipeline)
```

Rules:
- Split on `&&` and `;` → each segment becomes a separate frequency entry
- Pipe `|` segments stay together (a pipeline is one conceptual operation)
- Each segment is normalised via Pass 1

**Why no similarity merge for Bash?** Structural decomposition clusters
commands well. Fuzzy matching would falsely merge `npm run test` and
`npm run build`, which have very different intents.

---

## Computation

### Input

The function iterates over every session via the existing `parse_session()`.
For each message:

- **User messages** (`role == "user"`): normalise `msg.content`, tally
- **Assistant messages** (`role == "assistant"`): inspect `msg.tool_uses` for
  `{"name": "Bash", ...}`, normalise `tool_use["input"]["command"]`, tally
  each segment separately (compound commands produce multiple tallies)

### Filtering

Before normalisation:
- Skip empty / whitespace-only prompts
- Skip prompts shorter than `min_length` characters (default 4)

After counting and merging:
- Discard entries with `count < min_count`

### Output

- Sort by `count` descending, break ties by `project_spread` descending
- Truncate to `limit` entries per table
- Populate `examples` with up to 3 raw strings from the highest-count
  original keys that mapped to this canonical entry

### Complexity

- Time: O(M) for the scan (M = total messages across all sessions) +
  O(K²) for the merge pass (K = distinct normalised prompt keys surviving
  `min_count`). K is typically < 100, so the merge is negligible.
- Space: O(K) for counters and project sets.

---

## Module Layout

| File | New/Modified | Purpose |
|------|-------------|---------|
| `claude_history_explorer/stemmer.py` | **New** | Pure-Python Porter stemmer (~260 lines) |
| `claude_history_explorer/frequency.py` | **New** | `FrequencyEntry`, `FrequencyResult`, normalisation, merge, `compute_frequency()` |
| `claude_history_explorer/cli.py` | Modified | New `frequency` command + Rich rendering |
| `claude_history_explorer/history.py` | Modified | Re-exports: `compute_frequency`, `FrequencyResult`, `FrequencyEntry` |
| `tests/test_stemmer.py` | **New** | Comprehensive Porter stemmer tests |
| `tests/test_frequency.py` | **New** | Normalisation, merge, and integration tests |

---

## Edge Cases

| Case | Handling |
|------|----------|
| Empty / whitespace-only prompts | Skipped before normalisation |
| Prompts < `min_length` chars ("y", "ok") | Skipped before normalisation |
| Very long prompts (pasted code) | First-sentence extraction reduces to instruction |
| Multi-line prompts with code fences | Content after first fence stripped |
| `shlex.split` failure (unbalanced quotes) | Fallback to `.split()` |
| All stopwords removed ("do it") | Return original text, never empty |
| No sessions found | Print "No history data found" and exit cleanly |
| Bash commands with `&&`/`;` chains | Split into separate entries |
| Bash pipelines (`\|`) | Kept as single entry |
| Secrets in env vars | Data already on disk; no new exposure. Display truncates `export FOO=...` values |
| Single occurrence of everything | Empty tables after `min_count` filtering; print informational message |
