# Thread Map Specification

## Overview

Thread Map visualizes the relationship between Claude Code sessions, showing how main sessions spawn agent sub-conversations and revealing work patterns over time.

## Concepts

### Session Types
- **Main Session**: Primary conversation (`{uuid}.jsonl`)
- **Agent Session**: Sub-conversation spawned via Task tool (`agent-{uuid}.jsonl`)

### Inferred Relationships

Since Claude Code doesn't explicitly track parent-child relationships, we infer them:

```
Parent Detection Algorithm:
1. For each agent session A:
2.   Find main sessions M where: M.start <= A.start <= M.end + 5min buffer
3.   If multiple matches: choose M with closest start time to A.start
4.   If no match: mark A as "orphan" (standalone agent)
```

### Detected Patterns

| Pattern | Detection Rule | Meaning |
|---------|---------------|---------|
| **Hub-and-Spoke** | Main session with 3+ agents | Heavy delegation style |
| **Chain** | Sequential mains, <30min gap | Iterative development |
| **Parallel** | 2+ mains overlapping | Multi-tasking |
| **Deep** | Agent spawning agents (depth 2+) | Complex task decomposition |

## Data Model

```python
@dataclass
class ThreadNode:
    id: str                    # Session ID (truncated for display)
    type: str                  # "main" or "agent"
    start: datetime
    end: Optional[datetime]
    messages: int
    slug: Optional[str]        # Session title
    children: List[ThreadNode] # Spawned agents
    depth: int                 # Nesting level (0 for main)

@dataclass
class ThreadMap:
    project: str               # Project short name
    path: str                  # Full project path
    roots: List[ThreadNode]    # Main sessions (tree roots)
    orphans: List[ThreadNode]  # Unmatched agents
    patterns: List[str]        # Detected patterns
    stats: ThreadMapStats      # Aggregate statistics
    timespan: Tuple[datetime, datetime]  # Date range

@dataclass
class ThreadMapStats:
    total_sessions: int
    main_sessions: int
    agent_sessions: int
    max_depth: int             # Deepest agent nesting
    max_concurrent: int        # Peak parallel sessions
    avg_agents_per_main: float
    total_messages: int
    total_hours: float
```

## URL Encoding

Compact format for shareable URLs (similar to Wrapped):

```python
# Encoded fields (single-char keys for compactness)
{
    "v": 1,           # Version
    "p": "my-app",    # Project name
    "r": [...],       # Roots (compressed node list)
    "o": [...],       # Orphans
    "pt": [0, 2],     # Pattern indices
    "st": {...},      # Stats
    "ts": [start, end] # Timespan as unix timestamps
}

# Node compression: [id, type, start, end, msgs, slug, [children]]
# - id: last 6 chars of session ID
# - type: 0=main, 1=agent
# - start/end: unix timestamp (seconds)
# - children: recursive node array
```

Target URL size: <4KB for typical projects (50 sessions)

## CLI Interface

```bash
# Basic usage - most recent project
claude-history thread-map

# Specific project
claude-history thread-map --project myapp

# Limit timeframe
claude-history thread-map --days 30

# Output formats
claude-history thread-map --format ascii   # Terminal visualization (default)
claude-history thread-map --format json    # Raw data
claude-history thread-map --format url     # Shareable URL
```

### ASCII Output

```
Thread Map: my-app
══════════════════════════════════════════════════════════════════
Timespan: Dec 10-15, 2024 (5 days)
Sessions: 4 main, 8 agents | Patterns: Hub-and-spoke, Chain
──────────────────────────────────────────────────────────────────

[Dec 10 09:15] abc123 "fix auth bug" ━━━━━━━━━━━━━━━━━━━━━━━━━━━
               │ 45 msgs, 2h 15m
               ├── agent-d4e5f6 ━━━━━━━ (12 msgs)
               ├── agent-g7h8i9 ━━━━━━━━━━━━━ (28 msgs)
               └── agent-j0k1l2 ━━━━━━━━━━━━━━━━━━ (15 msgs)

[Dec 11 14:30] def456 "add user tests" ━━━━━━━━━━━━━━
               │ 23 msgs, 1h 10m
               └── agent-m3n4o5 ━━━━━━ (8 msgs)

[Dec 12 10:00] ghi789 "refactor api" ━━━━━━━━━━━━━━━━━━━━
               │ 67 msgs, 3h 45m  ⚡ hub (4 agents)
               ├── agent-p6q7r8 ━━━━━━ (22 msgs)
               │   └── agent-nested ━━━ (5 msgs)  ← depth 2
               ├── agent-s9t0u1 ━━━━━━━━━━━━ (31 msgs)
               └── agent-v2w3x4 ━━━━━ (9 msgs)

──────────────────────────────────────────────────────────────────
Legend: ━ duration | ⚡ hub (3+ agents) | → chain link
```

## Web Visualization

### URL Structure
```
https://wrapped-claude-codes.pages.dev/thread-map?d={encoded_data}
```

### Visual Design

1. **Timeline View** (primary)
   - Horizontal time axis
   - Main sessions as horizontal bars
   - Agent sessions as branches below their parent
   - Color: main=#d4a574 (gold), agent=#8b9dc3 (blue-gray)

2. **Graph View** (toggle)
   - Force-directed graph layout
   - Nodes sized by message count
   - Edges show parent-child relationships

3. **Interactive Features**
   - Hover: Show session details (slug, messages, duration)
   - Click: Expand/collapse agent branches
   - Filter: By date range, session type
   - Pattern highlighting

### Components

```
┌─────────────────────────────────────────────────────────────┐
│  Thread Map: my-app                           [Timeline ▼]  │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    TIMELINE VIEW                     │   │
│  │  Dec 10    Dec 11    Dec 12    Dec 13    Dec 14     │   │
│  │  ─┬────────┬─────────┬─────────┬─────────┬─────     │   │
│  │   █████████                                          │   │
│  │    ├─███                                             │   │
│  │    ├─██████                                          │   │
│  │    └─████████                                        │   │
│  │              ██████████                              │   │
│  │               └─████                                 │   │
│  │                          ████████████████            │   │
│  │                           ├─██████                   │   │
│  │                           │  └─███                   │   │
│  │                           ├─████████████             │   │
│  │                           └─█████                    │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  Stats: 4 main sessions, 8 agents | Max depth: 2           │
│  Patterns: Hub-and-spoke (1), Chain (2)                    │
│  Total: 180 messages over 7h 10m                           │
├─────────────────────────────────────────────────────────────┤
│  [Share]  [Copy URL]                                        │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Data Layer
- [ ] Add dataclasses to `history.py`
- [ ] Implement `build_thread_map(project, days=30)`
- [ ] Implement pattern detection
- [ ] Add URL encoding/decoding

### Phase 2: CLI
- [ ] Add `thread-map` command to `cli.py`
- [ ] Implement ASCII renderer
- [ ] Add `--format` options (ascii, json, url)

### Phase 3: Web
- [ ] Add `/thread-map` route
- [ ] Create timeline visualization (SVG)
- [ ] Add interactivity
- [ ] Generate OG image for sharing

## Privacy

Same model as Wrapped:
- No conversation content in URLs
- Only session IDs (truncated), timestamps, message counts
- Project name included (can be anonymized with `--anon` flag)
