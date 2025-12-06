# Claude Code Wrapped 2025 - Specification

## Overview

A web app that lets users share their Claude Code usage story as a single shareable URL. All data is encoded in the URL itself—no database, no server-side storage, complete privacy.

## Core Concept

```
User runs CLI command -> Generates encoded URL -> Shares URL -> Recipients see rich visualization
```

## Example URLs

### Minimal Story (Power User)
```
https://wrapped.claude.codes/2025#eyJwIjo0LCJzIjo3MCwibSI6NTMxNiwiaCI6MzEyLCJ0IjpbIkFnZW50LWRyaXZlbiIsIkRlZXAtd29yayBmb2N1c2VkIiwiSGlnaC1pbnRlbnNpdHkiXSwiYyI6IkhlYXZ5IGRlbGVnYXRpb24iLCJ3IjoiU3RlYWR5IGZsb3ciLCJwcCI6IktleWJvYXJkaWEiLCJwbSI6MTg3MywiY2kiOjMsImxzIjo1MC41LCJhIjpbMTIsMzQsNTYsNzgsOTAsMTIzLDE1NiwxODksMjEwLDI0NSwyNzgsMzAwXSwidHAiOlt7Im4iOiJLZXlib2FyZGlhIiwibSI6MTg3MywiZCI6M30seyJuIjoiQXVyaWdhIiwibSI6MTcwMSwiZCI6MTR9LHsibiI6IkxlbXBpY2thIiwibSI6ODc2LCJkIjo3fV19
```

Decodes to:
```json
{
  "p": 4,
  "s": 70,
  "m": 5316,
  "h": 312,
  "t": ["Agent-driven", "Deep-work focused", "High-intensity"],
  "c": "Heavy delegation",
  "w": "Steady flow",
  "pp": "Keyboardia",
  "pm": 1873,
  "ci": 3,
  "ls": 50.5,
  "a": [12, 34, 56, 78, 90, 123, 156, 189, 210, 245, 278, 300],
  "tp": [
    {"n": "Keyboardia", "m": 1873, "d": 3},
    {"n": "Auriga", "m": 1701, "d": 14},
    {"n": "Lempicka", "m": 876, "d": 7}
  ]
}
```

### With Display Name
```
https://wrapped.claude.codes/2025#eyJuIjoiQWRld2FsZSIsInAiOjQsInMiOjcwLCJtIjo1MzE2LCJoIjozMTIsInQiOlsiQWdlbnQtZHJpdmVuIl0sImMiOiJIZWF2eSBkZWxlZ2F0aW9uIiwidyI6IlN0ZWFkeSBmbG93IiwicHAiOiJLZXlib2FyZGlhIiwicG0iOjE4NzMsImNpIjozLCJscyI6NTAuNSwiYSI6WzEyLDM0LDU2LDc4LDkwLDEyMywxNTYsMTg5LDIxMCwyNDUsMjc4LDMwMF0sInRwIjpbXX0
```

Decodes to same as above but with `"n": "Adewale"` added.

### Casual User (Smaller Payload)
```
https://wrapped.claude.codes/2025#eyJwIjoxLCJzIjo1LCJtIjoxNTAsImgiOjgsInQiOlsiSGFuZHMtb24iXSwiYyI6IlNvbG8gd29yayIsInciOiJEZWxpYmVyYXRlIiwicHAiOiJteS1hcHAiLCJwbSI6MTUwLCJjaSI6MSwiYSI6WzAsMCwwLDAsMCwwLDAsMCwwLDE1MCwwLDBdLCJ0cCI6W119
```

Decodes to:
```json
{
  "p": 1,
  "s": 5,
  "m": 150,
  "h": 8,
  "t": ["Hands-on"],
  "c": "Solo work",
  "w": "Deliberate",
  "pp": "my-app",
  "pm": 150,
  "ci": 1,
  "a": [0, 0, 0, 0, 0, 0, 0, 0, 0, 150, 0, 0],
  "tp": []
}
```

### URL Structure

```
https://wrapped.claude.codes/2025#<base64url-encoded-msgpack>
        └──────────┬──────────┘ └─┬─┘ └───────────┬──────────┘
                domain          year    encoded story data
```

- **Domain**: `wrapped.claude.codes` (or similar)
- **Year**: `/2025` path segment for future year support
- **Fragment**: `#...` contains all data (never sent to server in HTTP requests)

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

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `n` | string | No | Display name |
| `p` | number | Yes | Total projects |
| `s` | number | Yes | Total sessions |
| `m` | number | Yes | Total messages |
| `h` | number | Yes | Total hours |
| `t` | string[] | Yes | Personality traits (max 3) |
| `c` | string | Yes | Collaboration style |
| `w` | string | Yes | Work pace |
| `pp` | string | Yes | Peak project name |
| `pm` | number | Yes | Peak project messages |
| `ci` | number | Yes | Max concurrent instances |
| `ls` | number | Yes | Longest session (hours) |
| `a` | number[] | Yes | Monthly activity (12 values) |
| `tp` | array | Yes | Top projects (up to 3) |

### URL Encoding Strategy

1. JSON -> MessagePack (binary, ~40% smaller than JSON)
2. MessagePack -> Base64URL (URL-safe encoding)
3. Place in URL fragment (`#`) so it's never sent to server in logs

**Size budget**: ~2KB encoded = rich story that fits in any URL

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Cloudflare Workers                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Worker: wrapped.claude.codes                               ││
│  │  - Serves static HTML/JS/CSS (embedded or from R2)         ││
│  │  - No data processing - all client-side                    ││
│  │  - Returns same SPA for all routes                         ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Client-Side App                              │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────────┐ │
│  │  URL Decoder  │  │  Visualizer   │  │  Share Generator    │ │
│  │  (msgpack +   │  │  (Canvas/SVG  │  │  (Copy link,        │ │
│  │   base64url)  │  │   animations) │  │   social cards)     │ │
│  └───────────────┘  └───────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Cloudflare Services Used

| Service | Purpose |
|---------|---------|
| **Workers** | Serve the SPA, handle routing |
| **Pages** | Alternative: static site hosting |
| **R2** | Optional: store static assets |

**No KV, D1, or Durable Objects needed** - all data lives in the URL.

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
https://wrapped.claude.codes/2025#eyJuIjoiQWRld2FsZSI...

📋 Copied to clipboard!
```

## Web App Screens

### 1. Landing Page (no hash)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                   Claude Code Wrapped 2025                      │
│                                                                 │
│         Discover your coding journey with Claude Code           │
│                                                                 │
│    ┌─────────────────────────────────────────────────────┐     │
│    │                                                     │     │
│    │   To generate your Wrapped, run:                    │     │
│    │                                                     │     │
│    │   $ claude-history wrapped                          │     │
│    │                                                     │     │
│    │   Don't have it? pip install claude-history-explorer│     │
│    │                                                     │     │
│    └─────────────────────────────────────────────────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Wrapped Visualization (with hash)

A series of animated "cards" the user can tap/click through (Spotify-style):

**Card 1: The Hook**
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

**Card 2: Volume**
```
┌─────────────────────────────────────────┐
│                                         │
│         You exchanged                   │
│                                         │
│             5,316                       │
│            messages                     │
│                                         │
│    That's like reading War and Peace    │
│              1.5 times                  │
│                                         │
└─────────────────────────────────────────┘
```

**Card 3: Time**
```
┌─────────────────────────────────────────┐
│                                         │
│      You spent 312 hours coding         │
│           with Claude                   │
│                                         │
│        ▁▂▃▅▇█▇▅▃▂▁▃                     │
│        J F M A M J J A S O N D          │
│                                         │
│       Peak month: October               │
│                                         │
└─────────────────────────────────────────┘
```

**Card 4: Personality**
```
┌─────────────────────────────────────────┐
│                                         │
│        Your coding personality:         │
│                                         │
│          🤖 Agent-driven                │
│          🧘 Deep-work focused           │
│          ⚡ High-intensity              │
│                                         │
│   You like to delegate and go deep      │
│                                         │
└─────────────────────────────────────────┘
```

**Card 5: Top Project**
```
┌─────────────────────────────────────────┐
│                                         │
│         Your top project was            │
│                                         │
│             Keyboardia                  │
│                                         │
│       1,873 messages over 3 days        │
│                                         │
│    You were in the zone.                │
│                                         │
└─────────────────────────────────────────┘
```

**Card 6: Parallel Power** (if ci > 1)
```
┌─────────────────────────────────────────┐
│                                         │
│        You ran up to 3 Claude           │
│        instances at once                │
│                                         │
│           🤖  🤖  🤖                    │
│                                         │
│     A true parallel processing mind     │
│                                         │
└─────────────────────────────────────────┘
```

**Card 7: Share**
```
┌─────────────────────────────────────────┐
│                                         │
│       That's your 2025 Wrapped!         │
│                                         │
│    ┌─────────┐  ┌─────────┐            │
│    │  Share  │  │  Copy   │            │
│    │   X     │  │  Link   │            │
│    └─────────┘  └─────────┘            │
│                                         │
│    ┌─────────┐  ┌─────────┐            │
│    │ LinkedIn│  │Download │            │
│    │         │  │  Image  │            │
│    └─────────┘  └─────────┘            │
│                                         │
└─────────────────────────────────────────┘
```

## Technical Implementation

### Worker Code (Minimal)

```typescript
export default {
  async fetch(request: Request): Promise<Response> {
    // Serve the same SPA for all routes
    // The client JS handles URL parsing
    return new Response(HTML_CONTENT, {
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'public, max-age=3600',
      },
    });
  },
};
```

### Client-Side Decoder

```typescript
import { decode } from '@msgpack/msgpack';

function decodeWrapped(hash: string): WrappedStory | null {
  try {
    const base64 = hash.slice(1); // Remove #
    const binary = base64UrlDecode(base64);
    return decode(binary) as WrappedStory;
  } catch {
    return null;
  }
}

// On page load
const story = decodeWrapped(window.location.hash);
if (story) {
  renderVisualization(story);
} else {
  renderLandingPage();
}
```

### Social Card Generation

Generate OG image client-side using Canvas, then offer download:

```typescript
async function generateShareImage(story: WrappedStory): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = 1200;
  canvas.height = 630; // OG image dimensions
  
  const ctx = canvas.getContext('2d')!;
  
  // Draw branded background
  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, 1200, 630);
  
  // Draw stats
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 72px system-ui';
  ctx.fillText(`${story.m.toLocaleString()} messages`, 100, 200);
  
  // ... more drawing
  
  return new Promise(resolve => {
    canvas.toBlob(blob => resolve(blob!), 'image/png');
  });
}
```

## Privacy Considerations

| Concern | Mitigation |
|---------|------------|
| Data in URL visible to recipients | Only aggregate stats, no conversation content |
| Server logging | Data in fragment (#) never sent to server |
| Analytics tracking | No analytics, or privacy-respecting only |
| Name disclosure | Name field is optional |

## File Structure

```
claude-code-wrapped/
├── src/
│   ├── worker.ts          # Cloudflare Worker entry
│   └── index.html         # Embedded SPA (inline JS/CSS)
├── wrangler.toml          # Cloudflare config
├── package.json
└── README.md
```

## Future Enhancements

- **Year selector**: Support 2026+ when the time comes
- **Comparison mode**: "You coded 50% more than last year"
- **Badges/Achievements**: "Night Owl", "Weekend Warrior", "Agent Whisperer"
- **Audio**: Background music like Spotify Wrapped
- **Animation**: More sophisticated transitions (Framer Motion)
- **QR Code**: Generate QR for easy mobile sharing
- **Embeddable widget**: For blogs/READMEs

## Summary

| Aspect | Decision |
|--------|----------|
| **Storage** | None - all data in URL |
| **Privacy** | Maximum - no server-side data |
| **Complexity** | Minimal - single Worker + SPA |
| **Shareability** | Single URL contains everything |
| **Cost** | Near-zero (Workers free tier) |
