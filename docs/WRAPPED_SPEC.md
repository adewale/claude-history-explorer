# Claude Code Wrapped - Specification

## Overview

A web app that lets users share their Claude Code usage story as a single shareable URL. All data is encoded in the URL itself—no database, no server-side storage, complete privacy.

The experience starts with a CLI command (`claude-history wrapped`) that analyzes local history, generates a compact data payload, and produces a shareable URL pointing to the launch website.

## Core Concept

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   $ claude-history wrapped --year 2025                                      │
│                                                                             │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│   │ Read local  │───▶│ Filter to   │───▶│ Compute     │───▶│ Encode &    │  │
│   │ JSONL files │    │ year 2025   │    │ stats/story │    │ generate URL│  │
│   └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                             │
│        │                                                                    │
│        ▼                                                                    │
│   https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJuIjoiQWRld2FsZSI...                  │
│                                                                             │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    Launch Website                                    │   │
│   │  - Decodes URL data                                                 │   │
│   │  - Renders interactive visualization                                │   │
│   │  - Generates dynamic OG images for social sharing                   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Example URLs

### Power User (2025)
```
https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJ5IjoyMDI1LCJwIjo0LCJzIjo3MCwibSI6NTMxNi4uLg
```

### With Display Name
```
https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJ5IjoyMDI1LCJuIjoiQWRld2FsZSIsInAiOjQsInMiOjcwLi4u
```

### Future Year (2026)
```
https://wrapped-claude-codes.adewale-883.workers.dev/2026/eyJ5IjoyMDI2LCJwIjoxMiwicyI6MTUwLCJtIjoxMjAwMC4uLg
```

### OG Image URL (auto-generated)
```
https://wrapped-claude-codes.adewale-883.workers.dev/og/2025/eyJ5IjoyMDI1LCJwIjo0LC4uLg.png
```

### URL Structure

```
https://wrapped-claude-codes.adewale-883.workers.dev/<year>/<base64url-encoded-data>
        └──────────┬──────────┘ └─┬─┘ └─────────┬─────────┘
                domain          year    encoded story data (includes year for validation)
```

**Important design decisions:**

1. **Year in path AND data**: The year appears in both the URL path (`/2025/`) and the encoded data (`y: 2025`). This allows:
   - Server-side validation (reject mismatched years)
   - SEO-friendly URLs with visible year
   - Client-side rendering without decoding first

2. **Data in path (not fragment)**: Server can read it for dynamic OG tag generation.

3. **Year validation**: The server rejects URLs where path year ≠ data year, preventing data manipulation.

---

## Data Model

### WrappedStory Schema

```typescript
interface WrappedStory {
  // Year (required) - must match URL path year
  y: number;                     // year (e.g., 2025)

  // Identity (optional)
  n?: string;                    // display name

  // Core stats
  p: number;                     // total projects (with activity in this year)
  s: number;                     // total sessions (in this year)
  m: number;                     // total messages (in this year)
  h: number;                     // total hours (dev time in this year)

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
  a: number[];                   // monthly activity (12 values, Jan-Dec of this year)

  // Top 3 projects (for this year)
  tp: Array<{
    n: string;                   // project name (short)
    m: number;                   // messages
    d: number;                   // days active
  }>;
}
```

### Year Filtering Logic

The CLI filters all data to the specified year before computing stats:

```python
def filter_sessions_by_year(sessions: list[Session], year: int) -> list[Session]:
    """
    Filter sessions to only those that started in the given year.

    Sessions spanning year boundaries (e.g., Dec 31 -> Jan 1) are
    assigned to their START year.
    """
    year_start = datetime(year, 1, 1, tzinfo=timezone.utc)
    year_end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    return [
        s for s in sessions
        if s.start_time and year_start <= s.start_time < year_end
    ]
```

**Edge cases handled:**

| Scenario | Behavior |
|----------|----------|
| Session spans year boundary | Assigned to start year |
| No sessions in requested year | Return empty stats with warning |
| Future year requested | Error: "Cannot generate wrapped for future year" |
| Year before Claude Code existed | Error: "No Claude Code data exists for {year}" |

### URL Encoding Strategy

1. JSON -> MessagePack (binary, ~40% smaller than JSON)
2. MessagePack -> Base64URL (URL-safe encoding)
3. Place in URL **path** (so server can generate OG tags)

**Size budget**: ~2KB encoded = rich story that fits in any URL

### Server-Side Validation

```typescript
// Server validates year consistency
function validateWrappedUrl(pathYear: number, story: WrappedStory): boolean {
  if (story.y !== pathYear) {
    throw new Error(`Year mismatch: URL says ${pathYear}, data says ${story.y}`);
  }
  if (story.y > new Date().getFullYear()) {
    throw new Error(`Invalid year: ${story.y} is in the future`);
  }
  return true;
}
```

---

## Architecture

### With Dynamic OG Images (Recommended)

```
┌────────────────────────────────────────────────────────────────────┐
│                     Cloudflare Pages                               │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      Router                                   │  │
│  │  /:year/<data>       -> Validate year, HTML + dynamic OG     │  │
│  │  /og/:year/<data>.png -> Generate PNG with year branding     │  │
│  │  /                    -> Landing page (year selector)        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                     │
│              ┌───────────────┴───────────────┐                    │
│              ▼                               ▼                    │
│  ┌──────────────────────┐      ┌──────────────────────┐          │
│  │   HTML Generator     │      │   Image Generator    │          │
│  │   (inject OG tags    │      │   (Satori + Resvg    │          │
│  │    + validate year)  │      │    + year theming)   │          │
│  └──────────────────────┘      └──────────────────────┘          │
└────────────────────────────────────────────────────────────────────┘
```

### Route Handling

```typescript
// Cloudflare Pages Function: /functions/[[path]].ts
export async function onRequest({ request, params, env }) {
  const url = new URL(request.url);
  const pathParts = params.path || [];

  // Landing page
  if (pathParts.length === 0) {
    return renderLandingPage();
  }

  // OG image: /og/2025/<data>.png
  if (pathParts[0] === 'og' && pathParts.length === 3) {
    const year = parseInt(pathParts[1]);
    const data = pathParts[2].replace('.png', '');
    return generateOgImage(year, data, env);
  }

  // Wrapped page: /2025/<data>
  if (pathParts.length === 2) {
    const year = parseInt(pathParts[0]);
    const data = pathParts[1];

    // Validate year is reasonable (2024 = Claude Code launch year)
    if (year < 2024 || year > new Date().getFullYear()) {
      return new Response('Invalid year', { status: 400 });
    }

    return renderWrappedPage(year, data, env);
  }

  return new Response('Not found', { status: 404 });
}
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

The Worker decodes the URL data and injects personalized OG tags with the year:

```html
<!-- Primary Meta Tags (year from URL path + validated against data.y) -->
<title>Adewale's Claude Code Wrapped 2025</title>
<meta name="description" content="5,316 messages across 4 projects in 2025. Agent-driven, Deep-work focused." />

<!-- Open Graph / Facebook / LinkedIn -->
<meta property="og:type" content="website" />
<meta property="og:url" content="https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJ..." />
<meta property="og:title" content="Adewale's Claude Code Wrapped 2025" />
<meta property="og:description" content="5,316 messages across 4 projects in 2025" />
<meta property="og:image" content="https://wrapped-claude-codes.adewale-883.workers.dev/og/2025/eyJ....png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="Adewale's Claude Code Wrapped 2025" />
<meta name="twitter:description" content="5,316 messages across 4 projects in 2025" />
<meta name="twitter:image" content="https://wrapped-claude-codes.adewale-883.workers.dev/og/2025/eyJ....png" />
```

### OG Tag Generation

```typescript
function generateOgTags(year: number, story: WrappedStory): string {
  const title = story.n
    ? `${story.n}'s Claude Code Wrapped ${year}`
    : `Claude Code Wrapped ${year}`;

  const description = `${story.m.toLocaleString()} messages across ${story.p} projects in ${year}`;

  return `
    <title>${title}</title>
    <meta property="og:title" content="${title}" />
    <meta property="og:description" content="${description}" />
    <meta property="og:image" content="https://wrapped-claude-codes.adewale-883.workers.dev/og/${year}/${encodeStory(story)}.png" />
  `;
}
```

### Image Generation with Satori

```typescript
import satori from 'satori';
import { Resvg } from '@resvg/resvg-wasm';

async function generateOgImage(year: number, story: WrappedStory): Promise<Uint8Array> {
  // Validate year matches story data
  if (story.y !== year) {
    throw new Error(`Year mismatch: path=${year}, data=${story.y}`);
  }

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
      <div style={{ fontSize: 32, opacity: 0.8 }}>Claude Code Wrapped {year}</div>
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
│      CLAUDE CODE WRAPPED {year}         │
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

Note: `{year}` is dynamically rendered from `story.y`.

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

### Command Specification

New command added to `claude-history`:

```bash
claude-history wrapped [OPTIONS]
```

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--year` | `-y` | Current year | Year to generate wrapped for |
| `--name` | `-n` | None | Display name (appears on cards) |
| `--raw` | | False | Output raw JSON instead of URL |
| `--no-copy` | | False | Don't copy URL to clipboard |
| `--decode` | `-d` | None | Decode and display a Wrapped URL |

### Usage Examples

```bash
# Current year (default)
claude-history wrapped

# Specific year
claude-history wrapped --year 2025
claude-history wrapped -y 2025

# With display name
claude-history wrapped --name "Adewale"
claude-history wrapped -n "Adewale" -y 2025

# Output raw JSON (for debugging)
claude-history wrapped --raw

# Don't copy to clipboard
claude-history wrapped --no-copy

# Decode a URL to see what's inside (yours or anyone's)
claude-history wrapped --decode "https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJ5IjoyMDI1..."
claude-history wrapped -d "https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJ5IjoyMDI1..."
```

### Decode Output

```bash
$ claude-history wrapped --decode "https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJ5IjoyMDI1Li4u"

🔍 Decoded Wrapped URL

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Year:           2025
Display Name:   Adewale

Core Stats:
  Projects:     4
  Sessions:     70
  Messages:     5,316
  Hours:        312

Personality:
  Archetype:    Agent-driven, Deep-work focused, High-intensity
  Work Pace:    Steady
  Style:        Heavy delegation

Highlights:
  Peak Project: Keyboardia (1,873 messages)
  Longest:      50.5 hours
  Max Parallel: 3 instances

Monthly Activity:
  ▁▂▃▅▇█▇▅▃▂▁▃
  J F M A M J J A S O N D

Top Projects:
  1. Keyboardia    1,873 msgs, 3 days
  2. Auriga        1,701 msgs, 14 days
  3. Lempicka        876 msgs, 7 days

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ This URL contains only aggregate statistics.
  No conversation content, code, or file paths.
```

This decode feature serves multiple purposes:
1. **Verify before sharing** — Users can inspect exactly what they're about to share
2. **Inspect any URL** — Anyone can decode any Wrapped URL to see what's in it
3. **Build trust** — Proves the "URL is the database" architecture
4. **Debug** — Useful for development and troubleshooting

### Implementation

```python
@click.command()
@click.option('--year', '-y', type=int, default=None,
              help='Year to generate wrapped for (default: current year)')
@click.option('--name', '-n', type=str, default=None,
              help='Display name to show on wrapped cards')
@click.option('--raw', is_flag=True,
              help='Output raw JSON instead of URL')
@click.option('--no-copy', is_flag=True,
              help="Don't copy URL to clipboard")
@click.option('--decode', '-d', type=str, default=None,
              help='Decode and display a Wrapped URL')
def wrapped(year: int | None, name: str | None, raw: bool, no_copy: bool, decode: str | None):
    """Generate your Claude Code Wrapped URL for sharing."""
    import datetime

    # Decode mode: inspect an existing URL
    if decode:
        story, url_year = decode_wrapped_url(decode)
        display_decoded_wrapped(story, url_year)
        return

    # Default to current year
    if year is None:
        year = datetime.datetime.now().year

    # Validate year
    current_year = datetime.datetime.now().year
    if year > current_year:
        raise click.ClickException(f"Cannot generate wrapped for future year {year}")
    if year < 2024:  # Claude Code launch year
        raise click.ClickException(f"Claude Code didn't exist in {year}")

    # Filter and compute stats for the year
    story = generate_wrapped_story(year, name)

    if story.s == 0:
        raise click.ClickException(f"No Claude Code activity found for {year}")

    if raw:
        console.print_json(data=asdict(story))
        return

    # Encode and generate URL
    encoded = encode_wrapped_story(story)
    url = f"https://wrapped-claude-codes.adewale-883.workers.dev/{year}/{encoded}"

    # Display and optionally copy
    display_wrapped_summary(story, url, year)

    if not no_copy:
        pyperclip.copy(url)
        console.print("📋 Copied to clipboard!")


def decode_wrapped_url(url: str) -> tuple[WrappedStory, int]:
    """
    Decode a Wrapped URL and return the story data and year.

    Handles both full URLs and just the encoded data portion.
    """
    import re
    import base64
    import msgpack

    # Extract year and data from URL
    match = re.match(r'(?:https?://[^/]+/)?(\d{4})/([A-Za-z0-9_-]+)', url)
    if not match:
        raise click.ClickException("Invalid Wrapped URL format")

    url_year = int(match.group(1))
    encoded_data = match.group(2)

    # Decode: Base64URL -> MessagePack -> dict -> WrappedStory
    try:
        # Add padding if needed
        padded = encoded_data + '=' * (4 - len(encoded_data) % 4)
        binary = base64.urlsafe_b64decode(padded)
        data = msgpack.unpackb(binary)
        story = WrappedStory(**data)
    except Exception as e:
        raise click.ClickException(f"Failed to decode URL: {e}")

    # Validate year matches
    if story.y != url_year:
        console.print(f"[yellow]⚠ Warning: URL year ({url_year}) doesn't match data year ({story.y})[/yellow]")

    return story, url_year
```

### CLI Output

**Standard output:**
```
🎁 Your Claude Code Wrapped 2025 is ready!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 4 projects | 70 sessions | 5,316 messages
⏱️  312 hours of development
🎭 Agent-driven, Deep-work focused, High-intensity
🔀 Used up to 3 Claude instances in parallel

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Share your story:
https://wrapped-claude-codes.adewale-883.workers.dev/2025/eyJuIjoiQWRld2FsZSI...

📋 Copied to clipboard!
```

**With `--year 2024`:**
```
🎁 Your Claude Code Wrapped 2024 is ready!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 2 projects | 15 sessions | 842 messages
⏱️  45 hours of development
🎭 Hands-on, Iterative, Exploratory

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Share your story:
https://wrapped-claude-codes.adewale-883.workers.dev/2024/eyJ5IjoyMDI0LCJwIjoy...

📋 Copied to clipboard!
```

**Error cases:**

```bash
$ claude-history wrapped --year 2030
Error: Cannot generate wrapped for future year 2030

$ claude-history wrapped --year 2020
Error: Claude Code didn't exist in 2020

$ claude-history wrapped --year 2025  # (no activity)
Error: No Claude Code activity found for 2025
```

### Year Detection Heuristics

When the user runs `wrapped` without a year near year boundaries:

```python
def suggest_year_if_ambiguous(current_year: int) -> int | None:
    """
    If running in early January, suggest previous year if it has more data.
    Returns suggested year or None if current year is fine.
    """
    now = datetime.datetime.now()

    # Only suggest if we're in the first week of January
    if now.month != 1 or now.day > 7:
        return None

    prev_year = current_year - 1
    prev_sessions = count_sessions_for_year(prev_year)
    curr_sessions = count_sessions_for_year(current_year)

    # If previous year has significantly more data, suggest it
    if prev_sessions > curr_sessions * 10:
        return prev_year

    return None
```

**Early January prompt:**
```
$ claude-history wrapped
ℹ️  It's early 2026 and you have much more activity in 2025.
   Generate for 2025 instead? [Y/n]
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

### Phase 1: CLI Command (`claude-history wrapped`)
- [ ] Add `wrapped` command to `cli.py`
- [ ] Implement `--year` option (default: current year)
- [ ] Implement `--name` option for display name
- [ ] Implement `--raw` flag for JSON output
- [ ] Implement `--no-copy` flag
- [ ] Implement `--decode` option to inspect any Wrapped URL
- [ ] Add year validation (not future, >= 2024)
- [ ] Add `filter_sessions_by_year()` to `history.py`
- [ ] Add `generate_wrapped_story()` to `history.py`
- [ ] Add `decode_wrapped_url()` for URL inspection
- [ ] Implement MessagePack + Base64URL encoding/decoding
- [ ] Add `y` (year) field to WrappedStory dataclass
- [ ] Integrate pyperclip for clipboard support
- [ ] Add early-January year suggestion heuristic
- [ ] Write tests for year filtering edge cases
- [ ] Write tests for encode/decode round-trip

### Phase 2: Launch Website (Basic)
- [ ] Set up Cloudflare Pages project at `wrapped-claude-codes.adewale-883.workers.dev`
- [ ] Implement `/:year/<data>` route handling
- [ ] Create landing page with year selector
- [ ] Implement URL decoder (Base64URL -> MessagePack -> JSON)
- [ ] Add year validation (path year must match data.y)
- [ ] Build card-based visualization (year-aware)
- [ ] Add share/copy buttons

### Phase 3: Social Cards (Dynamic OG)
- [ ] Implement `/og/:year/<data>.png` route
- [ ] Add year to OG title/description
- [ ] Set up Satori + resvg for PNG generation
- [ ] Add R2 caching for generated images (keyed by year + data hash)
- [ ] Test on Twitter, LinkedIn, Facebook, iMessage

### Phase 4: Polish
- [ ] Add animations (Framer Motion)
- [ ] Mobile optimization
- [ ] Error handling for invalid/mismatched years
- [ ] 404 page for invalid year ranges
- [ ] Analytics (privacy-respecting, year-segmented)

---

## Future Enhancements

- **Comparison mode**: "You coded 50% more than last year" (requires multiple years of data)
- **Multi-year view**: Combined stats across all years
- **Badges/Achievements**: "Night Owl", "Weekend Warrior", "Agent Whisperer"
- **Audio**: Background music like Spotify Wrapped
- **QR Code**: Generate QR for easy mobile sharing
- **Embeddable widget**: For blogs/READMEs
- **Year-over-year trends**: Sparkline comparing multiple years

---

## Summary

| Aspect | Decision |
|--------|----------|
| **CLI Command** | `claude-history wrapped --year YYYY` |
| **Year Handling** | Default current year, parameter for any past year |
| **Storage** | None - all data in URL (including year for validation) |
| **URL Format** | `https://wrapped-claude-codes.adewale-883.workers.dev/{year}/{encoded-data}` |
| **Privacy** | High - only aggregate stats shared |
| **Social Cards** | Dynamic OG images via Satori (year in title) |
| **Cost** | $5/month (Workers Paid for image generation) |
| **Visualization** | Hybrid Spotify (narrative) + Tufte (data-dense) |
