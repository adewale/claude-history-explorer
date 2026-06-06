# Wrapped Architecture

> **Current implementation note:** The live implementation is V3-only and uses `/wrapped?d=...` on `wrapped-claude-codes.adewale-883.workers.dev`. Historical examples in this document that use `wrapped.claude.codes/{year}/{data}`, KV counters, Queues/R2, Durable Objects, Browser Rendering, or generated PNG storage are proposal/future architecture notes, not current behavior.

## End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER'S MACHINE                                  │
│                                                                             │
│  ~/.claude/projects/                                                        │
│  ├── -Users-me-project1/          $ claude-history wrapped --year 2025     │
│  │   ├── session-1.jsonl    ───▶  ┌─────────────────────────────────────┐  │
│  │   └── session-2.jsonl          │  1. Filter sessions to 2025         │  │
│  └── -Users-me-project2/          │  2. Compute aggregate stats         │  │
│      └── ...                      │  3. Encode: JSON → MessagePack →    │  │
│                                   │     Base64URL                        │  │
│                                   │  4. Generate URL                     │  │
│                                   └─────────────────────────────────────┘  │
│                                              │                              │
│                                              ▼                              │
│                   https://wrapped.claude.codes/2025/eyJ5IjoyMDI1...        │
│                                                                             │
│                              📋 Copied to clipboard                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ User shares URL
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLOUDFLARE EDGE                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Pages + Functions                            │   │
│  │                                                                      │   │
│  │   Route: /:year/<data>                                              │   │
│  │   ┌──────────────────────────────────────────────────────────────┐  │   │
│  │   │  1. Validate year (2024 ≤ year ≤ current)                    │  │   │
│  │   │  2. Decode Base64URL → MessagePack → JSON                    │  │   │
│  │   │  3. Validate story.y === path year                           │  │   │
│  │   │  4. Inject dynamic OG meta tags                              │  │   │
│  │   │  5. Return HTML + hydrate client                             │  │   │
│  │   └──────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│         ┌────────────────────┼────────────────────┐                        │
│         ▼                    ▼                    ▼                        │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐                │
│  │ Workers KV  │      │   Queues    │      │  Durable    │                │
│  │             │      │             │      │  Objects    │                │
│  │ View counts │      │ Image jobs  │      │             │                │
│  │ by year     │      │             │      │ Live        │                │
│  │             │      │      │      │      │ presence    │                │
│  │ 2025:views: │      │      ▼      │      │             │                │
│  │ 2025:global │      │ ┌───────┐   │      │ WebSocket   │                │
│  └─────────────┘      │ │Worker │   │      │ "3 viewing" │                │
│                       │ │       │   │      └─────────────┘                │
│                       │ │Satori │   │                                      │
│                       │ │+Resvg │   │                                      │
│                       │ └───┬───┘   │                                      │
│                       └─────┼───────┘                                      │
│                             ▼                                              │
│                       ┌─────────────┐                                      │
│                       │     R2      │                                      │
│                       │             │                                      │
│                       │ 2025/       │                                      │
│                       │  └─hash.png │                                      │
│                       │ 2026/       │                                      │
│                       │  └─...      │                                      │
│                       └─────────────┘                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            USER'S BROWSER                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │   Print View (Tufte-inspired, information-dense single page)         │   │
│  │   ┌───────────────────────────────────────────────────────────────┐ │   │
│  │   │ Header: Name + Year                                           │ │   │
│  │   │ Summary: Messages · Hours · Projects · Days                   │ │   │
│  │   │ Heatmap: 7×24 weekly rhythm                                   │ │   │
│  │   │ Sparkline: Monthly activity                                   │ │   │
│  │   │ Projects: Top projects table                                  │ │   │
│  │   │ Traits: Coding style profile                                  │ │   │
│  │   │ Tokens: Usage breakdown (if available)                        │ │   │
│  │   │ Streaks: Activity streaks                                     │ │   │
│  │   └───────────────────────────────────────────────────────────────┘ │   │
│  │                                                                      │   │
│  │   🔒 Your stats stay in this URL. We store nothing.                 │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   LOCAL                    URL                      EDGE                 │
│                                                                          │
│   Sessions     Aggregate    Encode      Decode     Render                │
│   (JSONL)  ──▶  Stats   ──▶ (msgpack ──▶ (msgpack ──▶ (HTML +            │
│                             +base64)    +base64)     OG tags)            │
│                                                                          │
│   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐        │
│   │msg     │   │p: 4    │   │eyJ5Ijo │   │{y:2025 │   │<html>  │        │
│   │msg     │──▶│s: 70   │──▶│yMDI1LC │──▶│ p:4    │──▶│<og:..> │        │
│   │msg     │   │m: 5316 │   │JwIjo0L │   │ s:70   │   │<card/> │        │
│   │...     │   │h: 312  │   │CJzIjo3 │   │ ...}   │   │</html> │        │
│   └────────┘   │t: [...] │   │MH0=    │   └────────┘   └────────┘        │
│                └────────┘   └────────┘                                   │
│   ~2MB          ~500B        ~700B        ~500B                          │
│                                                                          │
│   PRIVATE      PRIVATE      SHAREABLE    SHAREABLE    SHAREABLE          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## URL Anatomy

```
https://wrapped.claude.codes/2025/eyJ5IjoyMDI1LCJuIjoiQWRld2FsZSIsInAiOjQs...
│       │                    │    │
│       │                    │    └─── Encoded WrappedStory (MessagePack + Base64URL)
│       │                    │
│       │                    └──────── Year (must match story.y inside)
│       │
│       └───────────────────────────── Domain (Cloudflare Pages)
│
└───────────────────────────────────── Protocol
```

---

## WrappedStory Schema

```
WrappedStory {
  y: 2025                          ─── Year (required, validated against URL)
  n: "Adewale"                     ─── Display name (optional)

  p: 4                             ─┐
  s: 70                             │  Core counts
  m: 5316                           │  (aggregates only,
  h: 312                           ─┘  never content)

  t: ["Agent-driven", ...]         ─── Personality traits
  c: "Heavy delegation"            ─── Collaboration style
  w: "Steady flow"                 ─── Work pace

  pp: "Keyboardia"                 ─┐
  pm: 1873                          │  Highlights
  ci: 3                             │
  ls: 50.5                         ─┘

  a: [12,45,89,120,...]            ─── Monthly activity (12 values)

  tp: [{n,m,d}, ...]               ─── Top 3 projects
}
```

---

## Privacy Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   WHAT'S IN THE URL                    WHAT'S NOT IN THE URL           │
│   (shared when you share)              (stays on your machine)          │
│                                                                         │
│   ✓ Message COUNT (5316)               ✗ Message CONTENT               │
│   ✓ Session COUNT (70)                 ✗ Code you discussed            │
│   ✓ Project COUNT (4)                  ✗ File paths                    │
│   ✓ Hours total (312)                  ✗ Error messages                │
│   ✓ Monthly activity bars              ✗ Tool call details             │
│   ✓ Personality labels                 ✗ Anything proprietary          │
│   ✓ Display name (if you add it)                                       │
│                                                                         │
│   ~700 bytes                           ~2MB+ of JSONL                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

                    Verify with: claude-history wrapped --decode <url>
```

---

## Year Namespacing

All Cloudflare primitives are namespaced by year:

```
Workers KV                    Durable Objects              R2 Storage
─────────────────            ─────────────────            ─────────────────
2024:views:<hash>            2024:<hash>                  2024/<hash>.png
2024:global:count            2025:<hash>                  2025/<hash>.png
2025:views:<hash>                                         2026/<hash>.png
2025:global:count

     └─────────────────────────────┴─────────────────────────────┘
                          Enables:
                          • Year-specific leaderboards
                          • Cross-year comparisons
                          • Clean data lifecycle
                          • No collisions
```

---

## Cloudflare Primitives Used

| User Sees | Primitive | Purpose |
|-----------|-----------|---------|
| Page loads instantly | **Pages** | Static hosting at edge |
| Dynamic OG cards | **Functions** | Server-side rendering |
| "You're #12,847 of 2025" | **Workers KV** | Global view counter |
| "3 others viewing" | **Durable Objects** | Real-time presence |
| Social card image | **Queues + R2** | Async generation + storage |
| PDF download | **Browser Rendering** | Headless Chrome at edge |

---

## Related Documents

- [WRAPPED_SPEC.md](WRAPPED_SPEC.md) — Full feature specification
- [WRAPPED_UX.md](WRAPPED_UX.md) — User experience design
- [WRAPPED_CLOUDFLARE_SHOWCASE.md](WRAPPED_CLOUDFLARE_SHOWCASE.md) — Platform showcase details
