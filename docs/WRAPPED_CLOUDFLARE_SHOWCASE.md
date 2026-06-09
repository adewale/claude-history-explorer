# Claude Code Wrapped - Cloudflare Platform Showcase Spec

> **Note**: This file is a future/proposal showcase for Cloudflare primitives. The current Worker is a Wrangler-deployed Hono app and does not implement KV view counters, Durable Objects presence, Queues/R2 async image storage, Browser Rendering PDF export, or year-in-path canonical URLs. Current canonical URLs use `/wrapped?d=...`; `/:year/:data` is legacy redirect compatibility; social previews are SVG.

## Overview

Beyond being a fun year-in-review tool, Claude Code Wrapped can serve as an interactive explainer for Cloudflare's edge computing platform. Each feature demonstrates a specific primitive, with visible metrics and expandable explanations.

**Year-Aware Architecture**: All Cloudflare primitives are namespaced by year to support multi-year wrapped URLs (`/2024/`, `/2025/`, `/2026/`, etc.). This ensures clean separation of data and enables year-over-year comparisons in the future.

---

## Feature 1: Workers KV for Global View Counter

### What It Showcases
Workers KV's atomic increment operations and global read performance at the edge.

### User-Facing Display
On each Wrapped page, show (year-specific):
```
You're Wrapped #12,847 of 2025
        └── 847 people viewed in the last hour
```

For 2024 wrapped:
```
You're Wrapped #3,421 of 2024
        └── 12 people viewed in the last hour
```

### Implementation

```typescript
// Year-namespaced KV keys for clean multi-year support
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { year, wrappedId } = extractWrappedParams(request.url);

    // Year-namespaced keys prevent cross-year collisions
    const viewKey = `${year}:views:${wrappedId}`;
    const globalKey = `${year}:global:count`;

    // Atomic increment for this specific wrapped
    const viewCount = await env.WRAPPED_KV.get(viewKey, 'json') || 0;
    await env.WRAPPED_KV.put(viewKey, JSON.stringify(viewCount + 1));

    // Global counter for this year
    const globalCount = await env.WRAPPED_KV.get(globalKey, 'json') || 0;
    await env.WRAPPED_KV.put(globalKey, JSON.stringify(globalCount + 1));

    // Inject into response with year context
    return renderWithStats({ year, viewCount, globalCount });
  }
};

// Helper to extract year and data from URL
function extractWrappedParams(url: string): { year: number; wrappedId: string } {
  // URL format: /2025/eyJ5IjoyMDI1Li4u
  const match = url.match(/\/(\d{4})\/([^\/]+)/);
  if (!match) throw new Error('Invalid wrapped URL');

  return {
    year: parseInt(match[1]),
    wrappedId: match[2],
  };
}
```

### KV Key Namespace Design

```
KV Keys are namespaced by year:

2024:views:<wrappedId>     # Views for specific 2024 wrapped
2024:global:count          # Total 2024 wrapped views
2024:hourly:2024-12-15:14  # Hourly bucket for 2024

2025:views:<wrappedId>     # Views for specific 2025 wrapped
2025:global:count          # Total 2025 wrapped views
2025:hourly:2025-01-03:09  # Hourly bucket for 2025
```

This enables:
- Year-specific leaderboards ("Top 10 most-viewed 2024 wrappeds")
- Cross-year comparisons ("2025 had 3x more wrappeds than 2024")
- Clean data isolation

### Educational Callout
```
┌─────────────────────────────────────────────────────────────────┐
│ ℹ️  How this works                                              │
├─────────────────────────────────────────────────────────────────┤
│ This counter uses Cloudflare Workers KV—a global key-value     │
│ store replicated across 300+ edge locations.                    │
│                                                                 │
│ • Reads are fast (~10ms) from the nearest edge                 │
│ • Writes propagate globally within 60 seconds                  │
│ • Keys are namespaced by year (2024:*, 2025:*, etc.)           │
│ • Atomic increments prevent race conditions                    │
│                                                                 │
│ [Learn more about Workers KV →]                                │
└─────────────────────────────────────────────────────────────────┘
```

### KV Free Tier Limits
| Resource | Free Tier |
|----------|-----------|
| Reads | 100,000/day |
| Writes | 1,000/day |
| Storage | 1 GB |

**Consideration**: 1,000 writes/day is limiting for viral content. Options:
- Batch writes (aggregate in memory, flush periodically)
- Use Analytics Engine for counts instead (see Bonus section)
- Upgrade to paid if needed

---

## Feature 2: Durable Objects for Real-Time Presence

### What It Showcases
Durable Objects' unique per-resource coordination model with WebSocket support—without needing R2 or external storage.

### User-Facing Display
When viewing a Wrapped URL:
```
┌─────────────────────────────────────────┐
│                                         │
│          👁️ 3 viewing now               │
│                                         │
│   ● ● ●                                │
│   Live viewers (updated in real-time)   │
│                                         │
└─────────────────────────────────────────┘
```

### Implementation

Each Wrapped URL gets its own Durable Object instance, namespaced by year:

```typescript
// durable-object.ts
export class WrappedPresence {
  connections: Set<WebSocket> = new Set();
  year: number | null = null;

  async fetch(request: Request): Promise<Response> {
    // Extract year from request for logging/metrics
    const url = new URL(request.url);
    const yearMatch = url.pathname.match(/\/presence\/(\d{4})\//);
    if (yearMatch) {
      this.year = parseInt(yearMatch[1]);
    }

    if (request.headers.get('Upgrade') === 'websocket') {
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);

      this.connections.add(server);
      server.accept();

      // Broadcast current count to all
      this.broadcast();

      server.addEventListener('close', () => {
        this.connections.delete(server);
        this.broadcast();
      });

      return new Response(null, { status: 101, webSocket: client });
    }

    return new Response(JSON.stringify({
      viewers: this.connections.size,
      year: this.year,
    }));
  }

  broadcast() {
    const message = JSON.stringify({ viewers: this.connections.size });
    for (const conn of this.connections) {
      conn.send(message);
    }
  }
}

// worker.ts
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { year, wrappedId } = extractWrappedParams(request.url);

    // Namespace DO instance by year + wrappedId
    // This ensures 2024 and 2025 wrappeds with same data hash are separate
    const doName = `${year}:${wrappedId}`;
    const id = env.WRAPPED_PRESENCE.idFromName(doName);
    const stub = env.WRAPPED_PRESENCE.get(id);

    return stub.fetch(request);
  }
};
```

### Durable Object Naming Strategy

```
DO instances are namespaced by year:

"2024:eyJhIjoxMjM..."  → DO instance for 2024 wrapped
"2025:eyJhIjoxMjM..."  → Separate DO instance for 2025 wrapped

Even if the same user generates identical stats in 2024 and 2025,
they get separate presence tracking.
```

### Client-Side WebSocket

```typescript
// Connect to presence for this Wrapped URL (year-aware)
const year = 2025;
const wrappedId = 'eyJ5IjoyMDI1...';
const ws = new WebSocket(`wss://wrapped.claude.codes/presence/${year}/${wrappedId}`);

ws.onmessage = (event) => {
  const { viewers } = JSON.parse(event.data);
  document.getElementById('viewer-count').textContent = viewers;
};
```

### Educational Callout
```
┌─────────────────────────────────────────────────────────────────┐
│ ℹ️  How this works                                              │
├─────────────────────────────────────────────────────────────────┤
│ This real-time counter uses Cloudflare Durable Objects—        │
│ stateful compute instances that coordinate connections.         │
│                                                                 │
│ • Each Wrapped URL gets its own Durable Object instance        │
│ • Instances are namespaced by year (2024:*, 2025:*, etc.)      │
│ • WebSocket connections are held in memory (no database!)      │
│ • When you leave, your connection closes automatically         │
│ • State lives at the edge, not in a central server             │
│                                                                 │
│ Unlike traditional WebSocket servers, Durable Objects:         │
│ • Scale automatically (one instance per resource)              │
│ • Require no provisioning or server management                 │
│ • Hibernate when idle (cost-efficient)                         │
│                                                                 │
│ [Learn more about Durable Objects →]                           │
└─────────────────────────────────────────────────────────────────┘
```

### Durable Objects Free Tier Limits
| Resource | Free Tier |
|----------|-----------|
| Requests | 100,000/day |
| Duration | 13,000 GB-s/month |
| WebSocket messages | Included in requests |

**No R2 required**: Presence state is ephemeral (in-memory). When the last viewer leaves, the DO hibernates. Perfect for "who's viewing now" without persistence.

---

## Feature 5: Queues for Async Image Pre-Generation

### What It Showcases
Cloudflare Queues' async processing model—offloading expensive work from the request path.

### User-Facing Display
When a user first generates their Wrapped URL:

**Initial state:**
```
┌─────────────────────────────────────────┐
│                                         │
│   🎁 Your 2025 Wrapped is ready!        │
│                                         │
│   ┌─────────────────────────────────┐   │
│   │  ⏳ Preparing your social card... │   │
│   │     This takes a few seconds     │   │
│   └─────────────────────────────────┘   │
│                                         │
│   Share URL: [Copy]                     │
│                                         │
└─────────────────────────────────────────┘
```

**After processing (poll or WebSocket):**
```
┌─────────────────────────────────────────┐
│                                         │
│   🎁 Your 2025 Wrapped is ready!        │
│                                         │
│   ┌─────────────────────────────────┐   │
│   │  ✅ Social card ready!           │   │
│   │     Generated in 2.3 seconds     │   │
│   │                                  │   │
│   │  [Preview] [Download PNG]        │   │
│   └─────────────────────────────────┘   │
│                                         │
│   Share URL: [Copy]                     │
│                                         │
└─────────────────────────────────────────┘
```

### Implementation

**Producer (on Wrapped creation):**
```typescript
// When user visits a Wrapped URL
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { year, wrappedId } = extractWrappedParams(request.url);
    const story = decodeWrappedData(wrappedId);

    // Validate year matches
    if (story.y !== year) {
      return new Response('Year mismatch', { status: 400 });
    }

    // Year-namespaced image key
    const imageKey = `${year}:image:${wrappedId}`;

    // Check if image already exists
    const existing = await env.WRAPPED_KV.get(imageKey);
    if (existing) {
      return renderWithImage(year, story, existing);
    }

    // Queue image generation with year context
    await env.IMAGE_QUEUE.send({
      year,
      wrappedId,
      story,
      timestamp: Date.now(),
    });

    // Return immediately with "processing" state
    return renderWithPending(year, story, wrappedId);
  }
};
```

**Consumer (background worker):**
```typescript
interface ImageJob {
  year: number;
  wrappedId: string;
  story: WrappedStory;
  timestamp: number;
}

export default {
  async queue(batch: MessageBatch<ImageJob>, env: Env): Promise<void> {
    for (const message of batch.messages) {
      const { year, wrappedId, story } = message.body;

      try {
        // Generate image with year branding (expensive: 100-200ms CPU)
        const startTime = Date.now();
        const png = await generateOgImage(year, story);
        const duration = Date.now() - startTime;

        // Store in R2 with year prefix
        await env.WRAPPED_IMAGES.put(`${year}/${wrappedId}.png`, png);

        // Mark as complete in KV (year-namespaced)
        await env.WRAPPED_KV.put(`${year}:image:${wrappedId}`, JSON.stringify({
          ready: true,
          duration,
          generatedAt: Date.now(),
          year,
        }));

        message.ack();
      } catch (error) {
        message.retry();
      }
    }
  }
};
```

**Polling endpoint:**
```typescript
// GET /api/image-status/:year/:wrappedId
export async function onRequest({ params, env }) {
  const { year, wrappedId } = params;
  const status = await env.WRAPPED_KV.get(`${year}:image:${wrappedId}`, 'json');

  if (!status) {
    return Response.json({ ready: false, position: 'processing' });
  }

  return Response.json(status);
}
```

### R2 Storage Layout

```
R2 bucket structure (year-prefixed):

wrapped-images/
├── 2024/
│   ├── eyJhIjoxMjM.png
│   └── eyJiIjo0NTY.png
├── 2025/
│   ├── eyJhIjoxMjM.png    # Same hash, different year = different image
│   └── eyJjIjo3ODk.png
└── 2026/
    └── ...
```

This enables:
- Easy cleanup of old years
- Year-specific CDN caching rules
- Storage analytics by year

### Educational Callout
```
┌─────────────────────────────────────────────────────────────────┐
│ ℹ️  How this works                                              │
├─────────────────────────────────────────────────────────────────┤
│ Your social card is generated using Cloudflare Queues—         │
│ a way to process work in the background.                        │
│                                                                 │
│ Why not generate it immediately?                                │
│ • Image generation takes 2-3 seconds (too slow for a click)    │
│ • Queues let us return instantly and process async             │
│ • If generation fails, the queue retries automatically         │
│                                                                 │
│ The flow:                                                       │
│ 1. You click "Generate" → job added to queue → instant response│
│ 2. Background worker picks up job → generates PNG              │
│ 3. Image stored in R2 → status updated in KV                   │
│ 4. Your browser polls for completion → shows preview           │
│                                                                 │
│ [Learn more about Cloudflare Queues →]                         │
└─────────────────────────────────────────────────────────────────┘
```

### Queues Free Tier Limits
| Resource | Free Tier |
|----------|-----------|
| Messages | 100,000/month |
| Operations | Included |

**Benefits over synchronous generation:**
- User gets immediate feedback
- Request doesn't timeout
- Failed generations auto-retry
- Can batch multiple generations

---

## Feature 8: Browser Rendering for PDF Export

### What It Showcases
Cloudflare's Browser Rendering API—running headless Chrome at the edge without managing infrastructure.

### User-Facing Display
In the share section:
```
┌─────────────────────────────────────────┐
│                                         │
│       [Share X] [Share LinkedIn]        │
│                                         │
│       [Copy Link] [Download PNG]        │
│                                         │
│           [📄 Download PDF]             │
│                                         │
│   "Rendered in a headless browser       │
│    at the edge in 1.8 seconds"          │
│                                         │
└─────────────────────────────────────────┘
```

### Implementation

```typescript
import puppeteer from '@cloudflare/puppeteer';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Route: /pdf/:year/:wrappedId.pdf
    const pdfMatch = url.pathname.match(/^\/pdf\/(\d{4})\/([^\/]+)\.pdf$/);
    if (pdfMatch) {
      const year = parseInt(pdfMatch[1]);
      const wrappedId = pdfMatch[2];

      // Validate year
      if (year < 2024 || year > new Date().getFullYear()) {
        return new Response('Invalid year', { status: 400 });
      }

      const wrappedUrl = `https://wrapped.claude.codes/${year}/${wrappedId}?print=true`;

      const startTime = Date.now();

      // Launch browser from Cloudflare's pool
      const browser = await puppeteer.launch(env.BROWSER);
      const page = await browser.newPage();

      // Set viewport to match OG image dimensions
      await page.setViewport({ width: 1200, height: 630 });

      // Navigate to the Wrapped page (with print-friendly styling)
      await page.goto(wrappedUrl, { waitUntil: 'networkidle0' });

      // Generate PDF
      const pdf = await page.pdf({
        width: '1200px',
        height: '630px',
        printBackground: true,
        margin: { top: 0, right: 0, bottom: 0, left: 0 },
      });

      await browser.close();

      const duration = ((Date.now() - startTime) / 1000).toFixed(1);

      return new Response(pdf, {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename="wrapped-${year}.pdf"`,
          'X-Render-Time': `${duration}s`,
          'X-Wrapped-Year': `${year}`,
        },
      });
    }

    // ... rest of routing
  }
};
```

### Print-Friendly Page Variant

```typescript
// When ?print=true is present, render a clean version
function renderPrintVersion(story: WrappedStory): string {
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <style>
        body {
          margin: 0;
          width: 1200px;
          height: 630px;
          background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          font-family: 'Inter', system-ui, sans-serif;
          color: white;
        }
        /* ... clean, print-optimized styles ... */
      </style>
    </head>
    <body>
      <div class="wrapped-card">
        <!-- Rendered card content -->
      </div>
    </body>
    </html>
  `;
}
```

### Educational Callout
```
┌─────────────────────────────────────────────────────────────────┐
│ ℹ️  How this works                                              │
├─────────────────────────────────────────────────────────────────┤
│ This PDF was generated using Cloudflare Browser Rendering—     │
│ headless Chrome running at the edge.                            │
│                                                                 │
│ What just happened:                                             │
│ 1. Your request hit a Cloudflare Worker                        │
│ 2. Worker launched a headless browser (from a warm pool)       │
│ 3. Browser navigated to your Wrapped page                      │
│ 4. Page was rendered to PDF                                    │
│ 5. PDF sent back to you                                        │
│                                                                 │
│ No servers to manage. No Puppeteer infrastructure to maintain. │
│ Just an API call that returns a PDF.                           │
│                                                                 │
│ Render time: 1.8 seconds (including browser launch)            │
│                                                                 │
│ [Learn more about Browser Rendering →]                         │
└─────────────────────────────────────────────────────────────────┘
```

### Browser Rendering Pricing
| Resource | Included |
|----------|----------|
| Workers Paid | Required ($5/month) |
| Browser sessions | Billed per session |

**Note**: Browser Rendering is not free tier, but pairs naturally with Workers Paid (already needed for image generation).

---

## Bonus: Combined "How This Works" Architecture Diagram

### User-Facing Display

An expandable footer section on every Wrapped page:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  [▼ How This Works - Built on Cloudflare]                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

When expanded:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│              Your Request Journey (2025 Wrapped)                │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                                                          │  │
│  │   YOU ──→ [1] ──→ [2] ──→ [3] ──→ [4] ──→ RESPONSE      │  │
│  │                                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [1] Pages           Static HTML/JS from nearest edge (3ms)    │
│      └── Your browser loads the app instantly                  │
│                                                                 │
│  [2] Functions       Year validated, URL decoded (12ms)        │
│      └── /:year/<data> → validates year matches data.y         │
│                                                                 │
│  [3] Queues          Image generation queued (async)           │
│      └── Stored in R2 at /2025/<hash>.png                      │
│                                                                 │
│  [4] KV              View counter incremented (8ms)            │
│      └── Key: 2025:views:<hash> → You're #12,847 of 2025       │
│                                                                 │
│  [5] Durable Objects Real-time presence (WebSocket)            │
│      └── Instance: 2025:<hash> → "3 others viewing now"        │
│                                                                 │
│  ────────────────────────────────────────────────────────────  │
│                                                                 │
│  Total time: 23ms to first byte                                │
│  Edge location: San Francisco (SFO)                            │
│  Year: 2025 (namespaced across all primitives)                 │
│                                                                 │
│  [View source on GitHub] [Cloudflare Developer Docs]           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```typescript
interface RequestTiming {
  pages: number;
  functions: number;
  kv: number;
  total: number;
  colo: string;  // Edge location code
}

function renderArchitectureDiagram(timing: RequestTiming): string {
  return `
    <details class="architecture">
      <summary>How This Works - Built on Cloudflare</summary>
      
      <div class="journey">
        <h3>Your Request Journey</h3>
        
        <ol class="steps">
          <li data-time="${timing.pages}ms">
            <strong>Pages</strong>
            <span>Static HTML/JS from nearest edge</span>
            <a href="https://developers.cloudflare.com/pages/">Learn more →</a>
          </li>
          
          <li data-time="${timing.functions}ms">
            <strong>Functions</strong>
            <span>URL decoded, OG tags injected</span>
            <a href="https://developers.cloudflare.com/pages/functions/">Learn more →</a>
          </li>
          
          <li data-time="async">
            <strong>Queues</strong>
            <span>Image generation (background)</span>
            <a href="https://developers.cloudflare.com/queues/">Learn more →</a>
          </li>
          
          <li data-time="${timing.kv}ms">
            <strong>KV</strong>
            <span>View counter incremented</span>
            <a href="https://developers.cloudflare.com/kv/">Learn more →</a>
          </li>
          
          <li data-time="live">
            <strong>Durable Objects</strong>
            <span>Real-time presence via WebSocket</span>
            <a href="https://developers.cloudflare.com/durable-objects/">Learn more →</a>
          </li>
        </ol>
        
        <div class="summary">
          <p>Total time: <strong>${timing.total}ms</strong> to first byte</p>
          <p>Edge location: <strong>${timing.colo}</strong></p>
        </div>
      </div>
    </details>
  `;
}
```

### Collecting Timing Data

```typescript
export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const timing: RequestTiming = {
      pages: 0,
      functions: 0,
      kv: 0,
      total: 0,
      colo: request.cf?.colo || 'unknown',
    };
    
    const start = Date.now();
    
    // Time KV operations
    const kvStart = Date.now();
    const viewCount = await env.WRAPPED_KV.get('views:global');
    timing.kv = Date.now() - kvStart;
    
    // Time function logic
    const funcStart = Date.now();
    const story = decodeWrappedData(request.url);
    const html = renderPage(story, timing);
    timing.functions = Date.now() - funcStart;
    
    timing.total = Date.now() - start;
    
    // Inject timing into response
    return new Response(html, {
      headers: {
        'Server-Timing': `kv;dur=${timing.kv}, func;dur=${timing.functions}, total;dur=${timing.total}`,
      },
    });
  }
};
```

### Educational Value

Each step in the diagram:
1. **Is clickable** → expands to show more detail
2. **Shows real timing** → from the actual request
3. **Links to docs** → drives learning
4. **Shows edge location** → demonstrates global distribution

This turns every Wrapped view into a mini-lesson on edge computing.

---

## Summary

| Feature | Primitive | Free Tier? | Year Namespacing | Key Learning |
|---------|-----------|------------|------------------|--------------|
| View counter | Workers KV | Yes (1k writes/day) | `{year}:views:{id}` | Global key-value at edge |
| Live presence | Durable Objects | Yes | `{year}:{id}` | Stateful coordination without DB |
| Async image gen | Queues + R2 | Yes (100k/month) | `{year}/{id}.png` | Background processing |
| PDF export | Browser Rendering | No ($5/mo) | `/pdf/{year}/{id}` | Headless Chrome at edge |
| Architecture diagram | All combined | - | Year shown in UI | How primitives compose |

### Year-Aware Design Principles

1. **All keys/names include year**: Prevents cross-year collisions and enables clean data separation
2. **URL path includes year (proposal only)**: `/:year/<data>` for SEO and social sharing; current canonical URLs use `/wrapped?d=...` and keep `/:year/:data` only as a redirect
3. **Data includes year**: `story.y` is range-validated from the decoded payload; OG routes also require the path year to match `story.y`
4. **Storage prefixed by year**: R2 paths like `2025/hash.png` enable easy lifecycle management
5. **Metrics segmented by year**: Analytics can compare year-over-year engagement

---

## Next Steps

These are future/proposal steps. Current implementation notes and audit lessons live in [WRAPPED_ARCHITECTURE.md](WRAPPED_ARCHITECTURE.md), [WRAPPED_V3_SPEC.md](WRAPPED_V3_SPEC.md), and [LESSONS_LEARNED.md](LESSONS_LEARNED.md).

1. **CLI command first**: Implement `claude-history wrapped --year YYYY` (see [WRAPPED_V3_SPEC.md](WRAPPED_V3_SPEC.md))
2. **Basic website**: Continue the shipped Cloudflare Worker/Hono site with `/wrapped?d=...` routing, retaining `/:year/<data>` only as legacy redirect compatibility
3. **KV counter**: Add year-namespaced view counting (`{year}:views:{id}`)
4. **Durable Objects presence**: Real-time viewers with year-prefixed instances
5. **Queues + R2**: Async image generation with `{year}/` storage prefixes
6. **Browser Rendering**: PDF export at `/pdf/{year}/{id}.pdf`
7. **Architecture diagram**: Educational footer showing year-aware data flow
