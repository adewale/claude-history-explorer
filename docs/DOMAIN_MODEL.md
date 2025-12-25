# Domain Model

This document provides a visual overview of the Claude History Explorer's domain model, showing how data is structured and flows through the system.

```
╔══════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                           CLAUDE HISTORY EXPLORER - DOMAIN MODEL                                         ║
║                                                                                                          ║
║  A read-only tool for exploring Claude Code conversation history stored in ~/.claude/projects/          ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════════╝


┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        STORAGE LAYER (Filesystem)                                        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘

    ~/.claude/
        │
        └── projects/                              ◄── get_projects_dir()
                │
                ├── -Users-ade-myproject/          ◄── Encoded path (/ → -)
                │       │
                │       ├── abc123def456.jsonl     ◄── Main session file
                │       ├── xyz789...jsonl
                │       └── agent-task123.jsonl    ◄── Agent session (delegated task)
                │
                ├── -Users-ade-another-project/
                │       └── ...
                │
                └── -tmp/
                        └── ...



┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           CORE ENTITIES                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘


    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                PROJECT                                       │
    │  The root container - a codebase directory that Claude Code was used in     │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  name: str              # Encoded dir name: "-Users-ade-myproject"          │
    │  path: str              # Decoded filesystem path: "/Users/ade/myproject"   │
    │  dir_path: Path         # Full path to project dir in ~/.claude/projects/  │
    │  session_files: [Path]  # List of .jsonl files, sorted by mtime desc        │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  Properties:                                                                │
    │    session_count: int         # len(session_files)                          │
    │    short_name: str            # "My Project" (prettified last component)    │
    │    last_modified: datetime    # mtime of most recent session file           │
    └───────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                            │ 1:N
                                            ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                SESSION                                       │
    │  A single conversation - one Claude Code invocation or resumed session      │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  session_id: str        # UUID (filename without .jsonl)                    │
    │  project_path: str      # Decoded project path for context                  │
    │  file_path: Path        # Path to the .jsonl file                           │
    │  messages: [Message]    # List of parsed messages                           │
    │  start_time: datetime?  # Timestamp of first message                        │
    │  end_time: datetime?    # Timestamp of last message                         │
    │  slug: str?             # Optional session title/summary                    │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  Properties:                                                                │
    │    message_count: int         # len(messages)                               │
    │    user_message_count: int    # count where role == "user"                  │
    │    duration_str: str          # "2h 30m" formatted duration                 │
    └───────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                            │ 1:N
                                            ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                                MESSAGE                                       │
    │  A single turn in the conversation - either user input or assistant output  │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  role: str              # "user" or "assistant"                             │
    │  content: str           # Text content of the message                       │
    │  timestamp: datetime?   # When the message was sent                         │
    │  tool_uses: [dict]      # List of {name: str, input: dict}                  │
    │  token_usage: TokenUsage?  # Token stats (assistant only)                   │
    └───────────────────────────────────────┬─────────────────────────────────────┘
                                            │
                                            │ 0..1 (assistant messages only)
                                            ▼
    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                              TOKEN USAGE                                     │
    │  API usage statistics for an assistant response                             │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  input_tokens: int              # Tokens in the prompt                      │
    │  output_tokens: int             # Tokens in the response                    │
    │  cache_creation_tokens: int     # Tokens used to create cache               │
    │  cache_read_tokens: int         # Tokens read from cache                    │
    │  model: str                     # e.g., "claude-opus-4-5-20251101"          │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  Properties:                                                                │
    │    total_tokens: int            # input_tokens + output_tokens              │
    └─────────────────────────────────────────────────────────────────────────────┘



┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      DERIVED/COMPUTED ENTITIES                                           │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘


           ┌───────────────────────────────┐          ┌───────────────────────────────┐
           │         SESSION INFO          │          │       SESSION INFO V3         │
           │   (Lightweight summary)       │          │   (Extended with project)     │
           ├───────────────────────────────┤          ├───────────────────────────────┤
           │  session_id: str              │          │  (inherits SessionInfo)       │
           │  start_time: datetime         │◄─────────┤  project_name: str            │
           │  end_time: datetime?          │          │  project_path: str            │
           │  duration_minutes: int        │          └───────────────────────────────┘
           │  message_count: int           │
           │  user_message_count: int      │
           │  is_agent: bool               │          Used for story generation
           │  slug: str?                   │          and wrapped computations
           └───────────────────────────────┘


    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                            PROJECT STATS                                     │
    │  Computed statistics for a single project                                   │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  project: Project                   # Reference to source project           │
    │  total_sessions: int                                                        │
    │  total_messages: int                                                        │
    │  total_user_messages: int                                                   │
    │  total_duration_minutes: int                                                │
    │  agent_sessions: int                # Sessions prefixed with "agent-"       │
    │  main_sessions: int                 # Non-agent sessions                    │
    │  total_size_bytes: int                                                      │
    │  avg_messages_per_session: float                                            │
    │  longest_session_duration: str      # Formatted: "2h 30m"                   │
    │  most_recent_session: datetime?                                             │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  Properties:                                                                │
    │    total_size_mb: float                                                     │
    │    total_duration_str: str          # Formatted duration                    │
    └─────────────────────────────────────────────────────────────────────────────┘


    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                             GLOBAL STATS                                     │
    │  Aggregated statistics across ALL projects                                  │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  projects: [ProjectStats]           # Stats for each project                │
    │  total_projects: int                                                        │
    │  total_sessions: int                                                        │
    │  total_messages: int                                                        │
    │  total_user_messages: int                                                   │
    │  total_duration_minutes: int                                                │
    │  total_size_bytes: int                                                      │
    │  avg_sessions_per_project: float                                            │
    │  avg_messages_per_session: float                                            │
    │  most_active_project: str           # Path of highest message count         │
    │  largest_project: str               # Path of highest storage size          │
    │  most_recent_activity: datetime?                                            │
    └─────────────────────────────────────────────────────────────────────────────┘



┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    NARRATIVE/STORY ENTITIES                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘


    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                            PROJECT STORY                                     │
    │  Narrative analysis of a project's development journey                      │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  IDENTITY                                                                   │
    │    project_name: str                # Short prettified name                 │
    │    project_path: str                # Full decoded path                     │
    │                                                                             │
    │  LIFECYCLE                                                                  │
    │    lifecycle_days: int              # Days from first to last session       │
    │    birth_date: datetime             # First session timestamp               │
    │    last_active: datetime            # Most recent session                   │
    │    peak_day: (date, int)?           # Highest activity day + count          │
    │    break_periods: [(start, end, days)]  # Gaps in activity                  │
    │                                                                             │
    │  COLLABORATION                                                              │
    │    agent_sessions: int                                                      │
    │    main_sessions: int                                                       │
    │    collaboration_style: str         # "Heavy delegation" / "Hands-on"       │
    │                                                                             │
    │  INTENSITY                                                                  │
    │    total_messages: int                                                      │
    │    dev_time_hours: float                                                    │
    │    message_rate: float              # Messages per hour                     │
    │    work_pace: str                   # "Rapid-fire" / "Steady" / "Methodical"│
    │                                                                             │
    │  SESSION PATTERNS                                                           │
    │    avg_session_hours: float                                                 │
    │    longest_session_hours: float                                             │
    │    session_style: str               # "Marathon" / "Extended" / "Sprints"   │
    │                                                                             │
    │  PERSONALITY                                                                │
    │    personality_traits: [str]        # ["Agent-driven", "Deep-work focused"] │
    │    most_productive_session: SessionInfo                                     │
    │    daily_engagement: str            # Pattern description                   │
    │    insights: [str]                  # Key insight strings                   │
    │                                                                             │
    │  ADVANCED                                                                   │
    │    daily_activity: {date: int}      # For sparklines                        │
    │    concurrent_claude_instances: int # Max parallel instances detected       │
    │    concurrent_insights: [str]                                               │
    └─────────────────────────────────────────────────────────────────────────────┘


    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                             GLOBAL STORY                                     │
    │  Narrative analysis across ALL projects                                     │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  total_projects: int                                                        │
    │  total_messages: int                                                        │
    │  total_dev_time: float              # Total hours                           │
    │  avg_agent_ratio: float             # Agent collaboration tendency          │
    │  avg_session_length: float          # Hours                                 │
    │  common_traits: [(trait, count)]    # Most frequent personality traits      │
    │  project_stories: [ProjectStory]    # Individual project narratives         │
    │  recent_activity: [(datetime, name)] # Recent work across projects          │
    └─────────────────────────────────────────────────────────────────────────────┘



┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              WRAPPED STORY V3 (Shareable Year Summary)                                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘


    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                          WRAPPED STORY V3                                    │
    │  Compact, shareable year-in-review (encoded in URL, no server storage)      │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  IDENTITY                                                                   │
    │    v: int = 3                       # Version                               │
    │    y: int                           # Year                                  │
    │    n: str?                          # Display name                          │
    │                                                                             │
    │  CORE COUNTS                                                                │
    │    p: int                           # Total projects                        │
    │    s: int                           # Total sessions                        │
    │    m: int                           # Total messages                        │
    │    h: int                           # Total hours (integer)                 │
    │    d: int                           # Days active                           │
    │                                                                             │
    │  TEMPORAL DATA                                                              │
    │    hm: [int; 168]                   # 7x24 activity heatmap (quantized)     │
    │    ma: [int; 12]                    # Monthly activity (messages)           │
    │    mh: [int; 12]                    # Monthly hours                         │
    │    ms: [int; 12]                    # Monthly sessions                      │
    │                                                                             │
    │  DISTRIBUTIONS                                                              │
    │    sd: [int; 10]                    # Session duration buckets              │
    │    ar: [int; 10]                    # Agent ratio buckets                   │
    │    ml: [int; 8]                     # Message length buckets                │
    │                                                                             │
    │  TRAIT SCORES (0-100 integers)                                              │
    │    ts: {                                                                    │
    │      ad: int  # Agent Delegation    sp: int  # Session depth/length         │
    │      fc: int  # Focus Concentration cc: int  # Circadian Consistency        │
    │      wr: int  # Weekend Ratio       bs: int  # Burst vs Steady              │
    │      cs: int  # Context Switching   mv: int  # Message Verbosity            │
    │      td: int  # Tool Diversity      ri: int  # Response Intensity           │
    │    }                                                                        │
    │                                                                             │
    │  PROJECT DATA                                                               │
    │    tp: [[name, msgs, hrs, days, sessions, agent_ratio%], ...]               │
    │    pc: [(proj_a_idx, proj_b_idx, co_occurrence_days), ...]                  │
    │                                                                             │
    │  TIMELINE & FINGERPRINTS                                                    │
    │    te: [[day_of_year, event_type, value, proj_idx], ...]                    │
    │    sf: [[duration, msgs, is_agent, hour, weekday, proj_idx, fp0..fp7], ...] │
    │                                                                             │
    │  ADDITIONAL METRICS                                                         │
    │    ls: float                        # Longest session (hours)               │
    │    sk: [count, longest, current, avg]  # Streak stats                       │
    │    tk: {total, input, output, cache_read, cache_create, models: {...}}      │
    │    yoy: {pm, ph, ps, pp, pd}?       # Year-over-year comparison             │
    └─────────────────────────────────────────────────────────────────────────────┘

         │
         │ encode_wrapped_story_v3()              decode_wrapped_story_v3()
         │ ──────────────────────────►            ◄──────────────────────────
         ▼

    ┌─────────────────────────────────────────────────────────────────────────────┐
    │                           URL ENCODING                                       │
    ├─────────────────────────────────────────────────────────────────────────────┤
    │  1. Quantize heatmap to 0-15 scale                                          │
    │  2. RLE encode if smaller (hm_rle flag)                                     │
    │  3. Pack with msgpack (binary)                                              │
    │  4. Base64 URL-safe encode                                                  │
    │                                                                             │
    │  Result: https://wrapped.../wrapped?d=<base64_encoded_data>                 │
    └─────────────────────────────────────────────────────────────────────────────┘



┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    ENTITY RELATIONSHIPS                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘


                                    ┌───────────────────┐
                                    │   FILESYSTEM      │
                                    │  ~/.claude/       │
                                    │   projects/       │
                                    └─────────┬─────────┘
                                              │
                                              │ list_projects()
                                              ▼
                      ┌───────────────────────────────────────────────┐
                      │                  PROJECT                       │
                      │            (encoded directory)                 │
                      └───────────────────────┬───────────────────────┘
                                              │
                      ┌───────────────────────┼───────────────────────┐
                      │                       │                       │
                      ▼                       ▼                       ▼
            ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
            │     SESSION     │    │     SESSION     │    │     SESSION     │
            │   (main.jsonl)  │    │  (agent-*.jsonl)│    │     ...         │
            └────────┬────────┘    └────────┬────────┘    └─────────────────┘
                     │                      │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │      MESSAGES       │
                     │  user <-> assistant │
                     └──────────┬──────────┘
                                │
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
           ┌───────────┐ ┌───────────┐ ┌───────────┐
           │  content  │ │ tool_uses │ │token_usage│
           │  (text)   │ │  (list)   │ │  (stats)  │
           └───────────┘ └───────────┘ └───────────┘



                           COMPUTATION FLOW

    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
    │   PROJECT   │─────▶│PROJECT STATS│─────▶│GLOBAL STATS │
    └─────────────┘      └─────────────┘      └─────────────┘
           │                    │
           │                    │
           ▼                    ▼
    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
    │   SESSION   │─────▶│PROJECT STORY│─────▶│GLOBAL STORY │
    └─────────────┘      └─────────────┘      └─────────────┘
           │                    │
           │                    │
           ▼                    ▼
    ┌─────────────┐      ┌─────────────────────┐
    │ SessionInfo │─────▶│   WRAPPED V3        │───▶ URL
    │ SessionInfoV3      │  (year summary)     │
    └─────────────┘      └─────────────────────┘



┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLI COMMANDS -> ENTITIES                                              │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘


    ┌────────────────────┬────────────────────────────────────────────────────────┐
    │ COMMAND            │ PRIMARY ENTITIES USED                                  │
    ├────────────────────┼────────────────────────────────────────────────────────┤
    │ projects           │ Project                                                │
    │ sessions <project> │ Project -> Session                                     │
    │ show <session_id>  │ Session -> Message                                     │
    │ search <pattern>   │ Project -> Session -> Message                          │
    │ export <session>   │ Session -> Message                                     │
    │ stats              │ ProjectStats, GlobalStats                              │
    │ summary            │ ProjectStats, GlobalStats (+ insights)                 │
    │ story              │ ProjectStory, GlobalStory                              │
    │ wrapped            │ WrappedStoryV3 (all temporal + trait data)             │
    │ info               │ Project (filesystem info only)                         │
    └────────────────────┴────────────────────────────────────────────────────────┘
```

## Key Concepts

### Storage
- Claude Code stores all conversation history in `~/.claude/projects/`
- Each project directory name is an encoded filesystem path (e.g., `/Users/ade/myproject` becomes `-Users-ade-myproject`)
- Session files are JSONL format, with `agent-*` prefix indicating delegated tasks

### Core Entities
- **Project**: A codebase directory where Claude Code was used
- **Session**: A single conversation (one CLI invocation or resumed session)
- **Message**: A single turn in the conversation (user or assistant)
- **TokenUsage**: API usage statistics attached to assistant messages

### Computed Entities
- **ProjectStats/GlobalStats**: Quantitative metrics (counts, durations, sizes)
- **ProjectStory/GlobalStory**: Narrative analysis with personality traits and insights
- **WrappedStoryV3**: Compact, shareable year-in-review encoded in a URL

### Design Principles
1. **Read-only**: Never modifies any Claude Code history files
2. **Streaming**: Parses JSONL line-by-line for memory efficiency
3. **Graceful degradation**: Skips malformed lines, handles missing data
4. **Privacy-first**: Wrapped URLs contain only aggregate statistics, no content
