# Claude Code Wrapped 2025 - Specification

## Overview

A web app that lets users share their Claude Code usage story as a single shareable URL. All data is encoded in the URL itself—no database, no server-side storage, complete privacy.

## Core Concept

```
User runs CLI command -> Generates encoded URL -> Shares URL -> Recipients see rich visualization
```

---

## Example URLs

### Power User
```
https://wrapped.claude.codes/2025/eyJwIjo0LCJzIjo3MCwibSI6NTMxNi4uLg
```

### With Display Name
```
https://wrapped.claude.codes/2025/eyJuIjoiQWRld2FsZSIsInAiOjQsInMiOjcwLi4u
```

### OG Image URL (auto-generated)
```
https://wrapped.claude.codes/og/eyJwIjo0LCJzIjo3MCwibSI6NTMxNi4uLg.png
```

### URL Structure

```
https://wrapped.claude.codes/2025/<base64url-encoded-data>
        └──────────┬──────────┘ └─┬─┘ └─────────┬─────────┘
                domain          year    encoded story data (in path, not fragment)
```

**Note**: Data is in the path (not fragment) so the server can read it and generate dynamic OG tags for social sharing.

---

## Data Model

### WrappedStory Schema

```typescript
interface WrappedStory {
  // Identity (optional)
  n?: string;                    // display name
  
  // Core stats
  p: number;                     // total projects
  s: number;                     // total sessions
  m: number;                     // total messages
  h: number;                     // total hours (dev time)
  
  // Patterns
  t: string[];                   // personality traits (max 3)
  c: string;                     // collaboration style
  w: string;                     // work pace
  
  // Highlights
  pp: string;                    // peak project name
  pm: number;                    // peak project messages
  ci: number;                    // max concurrent instances
  ls: number;                    // longest session (hours)
  
  // Activity (for sparkline)
  a: number[];                   // monthly activity (12 values, Jan-Dec)
  
  // Top 3 projects
  tp: Array<{
    n: string;                   // project name (short)
    m: number;                   // messages
    d: number;                   // days active
  }>;
}
```

### URL Encoding Strategy

1. JSON -> MessagePack (binary, ~40% smaller than JSON)
2. MessagePack -> Base64URL (URL-safe encoding)
3. Place in URL **path** (so server can generate OG tags)

**Size budget**: ~2KB encoded = rich story that fits in any URL

---

## Architecture

### With Dynamic OG Images (Recommended)

```
┌────────────────────────────────────────────────────────────────────┐
│                     Cloudflare Pages                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      Router                                   │  │
│  │  /2025/<data>     -> HTML with dynamic OG tags + SPA         │  │
│  │  /og/<data>.png   -> Generate PNG image on-the-fly           │  │
│  │  /                -> Landing page                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│              ┌───────────────┴───────────────┐                    │
│              ▼                               ▼                    │
│  ┌──────────────────────┐      ┌──────────────────────┐          │
│  │   HTML Generator     │      │   Image Generator    │          │
│  │   (inject OG tags)   │      │   (Satori + Resvg)   │          │
│  └──────────────────────┘      └──────────────────────┘          │
└────────────────────────────────────────────────────────────────────┘
```

### Cloudflare Services

| Service | Free Tier | Use |
|---------|-----------|-----|
| **Pages** | Unlimited static, 500 builds/mo | Host SPA |
| **Pages Functions** | 100k req/day, 10ms CPU | Routing, OG tags |
| **R2** | 10GB, free egress | Cache generated images |
| **Workers Paid** | $5/mo, 30s CPU | Required for PNG generation |

**Key constraint**: Free tier has 10ms CPU limit. PNG generation with Satori + resvg takes 50-200ms. Options:
1. **Pay $5/month** for Workers Paid (recommended)
2. **SVG-only** OG images (may not render on all platforms)
3. **External service** like Vercel OG for image generation

---

## Social Card Generation

### Dynamic OG Meta Tags

The Worker decodes the URL data and injects personalized OG tags:

```html
<!-- Primary Meta Tags -->
<title>Adewale's Claude Code Wrapped 2025</title>
<meta name="description" content="5,316 messages across 4 projects. Agent-driven, Deep-work focused." />

<!-- Open Graph / Facebook / LinkedIn -->
<meta property="og:type" content="website" />
<meta property="og:url" content="https://wrapped.claude.codes/2025/eyJ..." />
<meta property="og:title" content="Adewale's Claude Code Wrapped 2025" />
<meta property="og:description" content="5,316 messages across 4 projects" />
<meta property="og:image" content="https://wrapped.claude.codes/og/eyJ....png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Adewale's Claude Code Wrapped 2025" />
<meta name="twitter:description" content="5,316 messages across 4 projects" />
<meta name="twitter:image" content="https://wrapped.claude.codes/og/eyJ....png" />
```

### Image Generation with Satori

```typescript
import satori from 'satori';
import { Resvg } from '@resvg/resvg-wasm';

async function generateOgImage(story: WrappedStory): Promise<Uint8Array> {
  const svg = await satori(
    <div style={{
      width: 1200,
      height: 630,
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'Inter',
      color: 'white',
    }}>
      <div style={{ fontSize: 32, opacity: 0.8 }}>Claude Code Wrapped 2025</div>
      <div style={{ fontSize: 72, fontWeight: 'bold', marginTop: 20 }}>
        {story.m.toLocaleString()} messages
      </div>
      <div style={{ fontSize: 36, marginTop: 20 }}>
        {story.p} projects · {story.h} hours
      </div>
      <div style={{ fontSize: 28, marginTop: 40, opacity: 0.9 }}>
        {story.t.join(' · ')}
      </div>
    </div>,
    { width: 1200, height: 630, fonts: [/* Inter font */] }
  );

  const resvg = new Resvg(svg);
  return resvg.render().asPng();
}
```

### Platform Image Sizes

| Platform | Size | Notes |
|----------|------|-------|
| Twitter/X | 1200x628 | `twitter:card` = `summary_large_image` |
| LinkedIn | 1200x627 | Crops slightly, keep text centered |
| Facebook | 1200x630 | Standard OG image |
| iMessage | 1200x630 | Uses OG image |

---

## Visualization Approaches

### Approach A: Spotify Wrapped Style (Emotional/Narrative)

A series of animated cards the user taps through, building a story:

#### Card 1: The Hook
```
┌─────────────────────────────────────────┐
│                                         │
│           You and Claude Code           │
│              had a big year             │
│                                         │
│              [Tap to begin]             │
│                                         │
└─────────────────────────────────────────┘
```

#### Card 2: Mind-Bending Comparison
```
┌─────────────────────────────────────────┐
│                                         │
│         You exchanged                   │
│                                         │
│             5,316                       │
│            messages                     │
│                                         │
│   That's more words than The Great      │
│   Gatsby. You wrote a novel this year.  │
│                                         │
└─────────────────────────────────────────┘
```

**Comparison thresholds**:
- < 500: "That's a solid short story"
- 500-2000: "Longer than a PhD thesis"
- 2000-5000: "The Great Gatsby territory"
- 5000-10000: "War and Peace vibes"
- 10000+: "You could fill a bookshelf"

#### Card 3: Activity Timeline
```
┌─────────────────────────────────────────┐
│                                         │
│         Your year in code               │
│                                         │
│        ▁▂▃▅▇█▇▅▃▂▁▃                     │
│        J F M A M J J A S O N D          │
│                                         │
│      October was your peak month.       │
│      Something big was happening.       │
│                                         │
└─────────────────────────────────────────┘
```

**Pattern-based copy**:
- Steady: "Consistent builder. You showed up every month."
- End-loaded: "Late bloomer. You found your flow in Q4."
- Start-loaded: "Strong start. Hit the ground running."
- Spiky: "Burst worker. When you ship, you ship hard."

#### Card 4: Personality Archetype
```
┌─────────────────────────────────────────┐
│                                         │
│     Your Claude Code Personality:       │
│                                         │
│         ╔═══════════════════╗          │
│         ║  THE ARCHITECT    ║          │
│         ╚═══════════════════╝          │
│                                         │
│         🤖 Agent-driven                │
│         🧘 Deep-work focused           │
│         ⚡ High-intensity              │
│                                         │
│   You don't code—you orchestrate.      │
│                                         │
└─────────────────────────────────────────┘
```

**Personality archetypes** (computed from traits):
- **The Architect**: Agent-driven + Deep-work → "You design systems"
- **The Sprinter**: High-intensity + Burst → "Fast and focused"
- **The Collaborator**: Hands-on + Iterative → "Think out loud"
- **The Craftsperson**: Deliberate + Solo → "Trust the process"

#### Card 5: Top Project
```
┌─────────────────────────────────────────┐
│                                         │
│          Your #1 Project                │
│                                         │
│            Keyboardia                   │
│                                         │
│      1,873 messages · 3 days            │
│                                         │
│   You were locked in.                   │
│   This project got your best work.      │
│                                         │
└─────────────────────────────────────────┘
```

#### Card 6: Parallel Power (if ci > 1)
```
┌─────────────────────────────────────────┐
│                                         │
│   At your peak, you were running        │
│                                         │
│          🤖     🤖     🤖              │
│                                         │
│   3 Claude instances simultaneously     │
│                                         │
│        You don't multitask.             │
│        You parallelize.                 │
│                                         │
└─────────────────────────────────────────┘
```

#### Card 7: Longest Session
```
┌─────────────────────────────────────────┐
│                                         │
│      Your longest session:              │
│                                         │
│           50.5 hours                    │
│                                         │
│    ☕☕☕☕☕☕☕☕☕☕☕☕☕☕☕☕            │
│                                         │
│      That's over 2 days straight.       │
│      Please tell us you slept.          │
│                                         │
└─────────────────────────────────────────┘
```

**Duration-based copy**:
- < 2h: "Quick and focused. In and out."
- 2-4h: "A proper deep work session."
- 4-8h: "Full day energy."
- 8-24h: "Marathon mode. Respect."
- 24h+: "...are you okay? We're concerned."

#### Card 8: Share Card
```
┌─────────────────────────────────────────┐
│                                         │
│      CLAUDE CODE WRAPPED 2025           │
│                                         │
│              Adewale                    │
│                                         │
│    5,316 messages · 312 hours           │
│                                         │
│        ▁▂▃▅▇█▇▅▃▂▁▃                    │
│                                         │
│         THE ARCHITECT                   │
│    Agent-driven · Deep-work focused     │
│                                         │
│    [ Share ]  [ Download Image ]        │
│                                         │
└─────────────────────────────────────────┘
```

### Approach B: Tufte Style (Data-Dense/Analytical)

Inspired by Edward Tufte's principles: maximize data-ink ratio, use sparklines, enable micro/macro readings.

#### Integrated Text + Graphics

Tufte advocates embedding graphics inline with text, "word-sized":

```
In 2025, you exchanged 5,316 messages across 70 sessions
                        ▁▂▃▅▇█▇▅▃▂▁▃
spanning 312 hours—your peak month was July, when you
sent 189 messages in a single day while juggling
3 Claude instances on Keyboardia.

Your style: Agent-driven, Steady flow, Heavy delegation.
```

#### Small Multiples for Projects

Same structure repeated, enabling instant comparison:

```
TOP PROJECTS

Keyboardia          Auriga             Lempicka
━━━━━━━━━━━        ━━━━━━━━━━━        ━━━━━━━━━━━
1,873 messages     1,701 messages     876 messages
3 days active      14 days active     7 days active
│█████████│        │████████ │        │████     │
```

#### Slopegraph for Comparisons

Compare yourself to averages (if available):

```
        You                         Average
        ───                         ───────
 5,316 ─messages───────────────────── 2,100
   312 ─hours────────────────────────── 180
    70 ─sessions──────────────────────── 45
```

#### Layered Sparklines

Multiple data dimensions on same axis:

```
2025 ACTIVITY

Hours:    ▁▂▃▅▇█▇▅▃▂▁▃  (312 total)
Messages: ▂▃▄▆█▇▆▅▄▃▂▄  (5,316 total)
          J F M A M J J A S O N D
                    ↑
                 October
```

#### Data-Ink Ratio: Strip Decoration

**Avoid:**
```
┌──────────────────────────┐
│  📊 MESSAGES: 5,316      │
│  ⏱️  HOURS: 312           │
│  📁 PROJECTS: 4          │
└──────────────────────────┘
```

**Prefer:**
```
5,316 messages   312 hours   70 sessions   4 projects
```

### Recommendation: Hybrid Approach

Use **Spotify style for the interactive experience** (cards, narrative, emotion) but incorporate **Tufte principles for the final share card** (data-dense, sparklines, no chartjunk).

---

## CLI Integration

New command added to `claude-history`:

```bash
# Generate shareable wrapped URL
claude-history wrapped

# With custom name
claude-history wrapped --name "Adewale"

# Output just the data (for debugging)
claude-history wrapped --raw
```

### CLI Output

```
🎁 Your Claude Code Wrapped 2025 is ready!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 4 projects | 70 sessions | 5,316 messages
⏱️  312 hours of development
🎭 Agent-driven, Deep-work focused, High-intensity
🔀 Used up to 3 Claude instances in parallel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Share your story:
https://wrapped.claude.codes/2025/eyJuIjoiQWRld2FsZSI...

📋 Copied to clipboard!
```

---

## Privacy Considerations

| Concern | Mitigation |
|---------|------------|
| Data visible to recipients | Only aggregate stats, no conversation content |
| Server sees data | Acceptable—it's just stats for OG generation |
| Analytics tracking | None, or privacy-respecting only |
| Name disclosure | Name field is optional |

---

## File Structure

```
claude-code-wrapped/
├── src/
│   ├── index.ts           # Pages Function entry
│   ├── og.ts              # OG image generation
│   └── index.html         # SPA template
├── public/
│   └── fonts/             # Inter font for Satori
├── wrangler.toml          # Cloudflare config
├── package.json
└── README.md
```

---

## Implementation Checklist

### Phase 1: CLI Command
- [ ] Add `wrapped` command to claude-history
- [ ] Collect 2025 data (filter by year)
- [ ] Generate WrappedStory JSON
- [ ] Encode with MessagePack + Base64URL
- [ ] Output URL and copy to clipboard

### Phase 2: Basic Web App
- [ ] Set up Cloudflare Pages project
- [ ] Create landing page
- [ ] Implement URL decoder
- [ ] Build card-based visualization
- [ ] Add share/copy buttons

### Phase 3: Social Cards
- [ ] Move data from fragment to path
- [ ] Implement dynamic OG tag injection
- [ ] Set up Satori + resvg for PNG generation
- [ ] Add R2 caching for generated images
- [ ] Test on Twitter, LinkedIn, Facebook

### Phase 4: Polish
- [ ] Add animations (Framer Motion)
- [ ] Mobile optimization
- [ ] Error handling for invalid URLs
- [ ] Analytics (privacy-respecting)

---

## Future Enhancements

- **Year selector**: Support 2026+ when the time comes
- **Comparison mode**: "You coded 50% more than last year"
- **Badges/Achievements**: "Night Owl", "Weekend Warrior", "Agent Whisperer"
- **Audio**: Background music like Spotify Wrapped
- **QR Code**: Generate QR for easy mobile sharing
- **Embeddable widget**: For blogs/READMEs

---

## Summary

| Aspect | Decision |
|--------|----------|
| **Storage** | None - all data in URL |
| **Privacy** | High - only aggregate stats shared |
| **Social Cards** | Dynamic OG images via Satori |
| **Cost** | $5/month (Workers Paid for image generation) |
| **Visualization** | Hybrid Spotify (narrative) + Tufte (data-dense) |
