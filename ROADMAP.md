# Claude Code Wrapped - Implementation Roadmap

This document breaks down the implementation of the "Claude Code Wrapped" feature into verifiable phases. Each phase has clear deliverables, acceptance criteria, and dependencies.

---

## Overview

```
Phase 1          Phase 2          Phase 3          Phase 4          Phase 5
CLI Command  ->  Basic Website -> Social Cards -> Polish & UX  -> Platform Features
   (2 parts)        (2 parts)       (1 part)       (2 parts)        (optional)
```

**Total: 7 sub-phases, each independently shippable and verifiable**

---

## Phase 1: CLI Command

The foundation. Everything starts with generating the wrapped data locally.

### Phase 1A: Core Data Collection & Encoding

**Goal**: Generate a `WrappedStory` from local history and encode it to a URL.

**Deliverables**:
1. `WrappedStory` dataclass in `history.py`
2. `filter_sessions_by_year()` function
3. `generate_wrapped_story()` function
4. MessagePack + Base64URL encoding/decoding utilities
5. Basic `wrapped` command that outputs a URL

**Implementation Details**:

```python
# New dataclass in history.py
@dataclass
class WrappedStory:
    y: int                    # year
    n: str | None = None      # display name
    p: int = 0                # projects
    s: int = 0                # sessions
    m: int = 0                # messages
    h: float = 0              # hours
    t: list[str] = field(default_factory=list)   # traits
    c: str = ""               # collaboration style
    w: str = ""               # work pace
    pp: str = ""              # peak project name
    pm: int = 0               # peak project messages
    ci: int = 0               # max concurrent instances
    ls: float = 0             # longest session hours
    a: list[int] = field(default_factory=list)   # monthly activity (12 values)
    tp: list[dict] = field(default_factory=list) # top 3 projects
```

**New dependency**: `msgpack` (add to pyproject.toml)

**Verification Criteria**:
- [ ] `claude-history wrapped --raw` outputs valid JSON matching the schema
- [ ] `claude-history wrapped` outputs a URL starting with `https://wrapped.claude.codes/YYYY/`
- [ ] Year filtering works (sessions outside year are excluded)
- [ ] Test: encode → decode round-trip preserves all data
- [ ] Test: sessions spanning year boundary assigned to start year
- [ ] Test: future year returns error
- [ ] Test: year before 2024 returns error

**Files to modify**:
- `pyproject.toml` (add msgpack dependency)
- `claude_history_explorer/history.py` (add WrappedStory, filter functions)
- `claude_history_explorer/cli.py` (add wrapped command)

---

### Phase 1B: CLI Polish & Decode

**Goal**: Complete CLI experience with name, decode, and clipboard support.

**Deliverables**:
1. `--name` option for display name
2. `--decode` option to inspect any URL
3. `--no-copy` flag
4. Clipboard integration (pyperclip)
5. Early-January year suggestion
6. Rich formatted output

**New dependency**: `pyperclip` (add to pyproject.toml)

**Verification Criteria**:
- [ ] `claude-history wrapped --name "Alice"` includes name in output
- [ ] `claude-history wrapped --decode <url>` shows decoded stats
- [ ] Can decode anyone's URL (not just your own)
- [ ] URL is copied to clipboard by default (unless `--no-copy`)
- [ ] In early January, suggests previous year if it has more data
- [ ] Output matches the styled format from WRAPPED_SPEC.md

**Files to modify**:
- `pyproject.toml` (add pyperclip dependency)
- `claude_history_explorer/cli.py` (enhance wrapped command)

---

## Phase 2: Basic Website

A minimal Cloudflare Pages site that renders wrapped URLs.

### Phase 2A: Static Site & Routing

**Goal**: Deploy a site that decodes and displays wrapped data.

**Deliverables**:
1. Cloudflare Pages project at `wrapped.claude.codes`
2. `/:year/<data>` route handling
3. Landing page with "Get your own" CTA
4. Client-side URL decoder (Base64URL → MessagePack → JSON)
5. Year validation (path year must match data.y)

**Tech Stack**:
- Cloudflare Workers
- Vanilla JS or lightweight framework (Preact/Solid)
- Hono or itty-router for routing

**Project Structure**:
```
wrapped-website/
├── src/
│   ├── index.ts            # Worker entry point + routing
│   ├── decoder.ts          # URL decoding logic
│   ├── renderer.ts         # Card rendering
│   └── pages/
│       ├── landing.ts      # Landing page HTML
│       └── wrapped.ts      # Wrapped card HTML
├── static/
│   └── styles.css          # Embedded or inlined
└── wrangler.toml
```

**Verification Criteria**:
- [ ] `wrapped.claude.codes/` shows landing page with CLI command
- [ ] `wrapped.claude.codes/2025/<valid-data>` renders the wrapped card
- [ ] Invalid year (e.g., 2030) shows error page
- [ ] Mismatched year (path vs data.y) shows error page
- [ ] Works on mobile browsers
- [ ] Page load < 2 seconds

---

### Phase 2B: Story Mode & Summary View

**Goal**: Interactive card-based story experience.

**Deliverables**:
1. Story mode (tap-through cards)
2. "Skip to summary" option
3. All card types from WRAPPED_UX.md:
   - Hook card ("had a big year")
   - Stats card (message count with comparison)
   - Timeline card (sparkline)
   - Personality card (archetype)
   - Peak project card
   - Parallel instances card (conditional)
   - Longest session card (conditional)
   - Summary & share card
4. Mobile swipe navigation
5. Share/copy buttons

**Verification Criteria**:
- [ ] Story mode works on desktop (click to advance)
- [ ] Story mode works on mobile (swipe to advance)
- [ ] "Skip to summary" jumps to final card
- [ ] Conditional cards only appear when relevant (ci > 1, ls > threshold)
- [ ] Copy button copies URL to clipboard
- [ ] Share buttons open correct URLs (Twitter, LinkedIn)
- [ ] Privacy footer visible on first and last cards

---

## Phase 3: Social Cards (Dynamic OG Images)

Make shared URLs look great in social feeds.

### Phase 3: OG Image Generation

**Goal**: Generate dynamic PNG images for social sharing.

**Deliverables**:
1. `/og/:year/<data>.png` route
2. Satori-based image generation
3. Resvg WASM for PNG conversion
4. Edge Cache for caching generated images
5. Dynamic `<meta>` tag injection in HTML

**Tech Stack**:
- Satori (React → SVG)
- @resvg/resvg-wasm (SVG → PNG)
- Edge Cache API (no R2 needed)

**Implementation**:
```typescript
// src/routes/og.ts
import satori from 'satori';
import { Resvg } from '@resvg/resvg-wasm';

export async function handleOgImage(request: Request, year: string, data: string) {
  const cacheKey = new Request(request.url, request);
  const cache = caches.default;

  // Check edge cache
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  // Decode and validate
  const story = decodeWrappedData(data);
  if (story.y !== parseInt(year)) {
    return new Response('Year mismatch', { status: 400 });
  }

  // Generate SVG with Satori
  const svg = await satori(<OgCard story={story} year={parseInt(year)} />, { width: 1200, height: 630 });

  // Convert to PNG
  const resvg = new Resvg(svg);
  const png = resvg.render().asPng();

  // Create response with cache headers
  const response = new Response(png, {
    headers: {
      'Content-Type': 'image/png',
      'Cache-Control': 'public, max-age=31536000, immutable', // 1 year - URL is content-addressed
    },
  });

  // Store in edge cache
  await cache.put(cacheKey, response.clone());

  return response;
}
```

**Verification Criteria**:
- [ ] `/og/2025/<data>.png` returns a valid PNG
- [ ] Image dimensions are 1200x630
- [ ] Image includes: year, message count, sparkline, archetype
- [ ] Name appears if provided in data
- [ ] Second request served from edge cache (check `cf-cache-status` header)
- [ ] HTML includes correct `og:image` meta tag
- [ ] Test with Twitter Card Validator
- [ ] Test with LinkedIn Post Inspector
- [ ] Test with Facebook Sharing Debugger

---

## Phase 4: Polish & UX

Refinements for production quality.

### Phase 4A: Animations & Mobile

**Goal**: Delightful, polished user experience.

**Deliverables**:
1. Card transitions with Framer Motion
2. Number counting animations
3. Sparkline drawing animation
4. Mobile touch gestures (swipe, tap)
5. Loading state ("Unwrapping 2025...")
6. Error states (invalid URL, year mismatch, future year)

**Verification Criteria**:
- [ ] Cards animate smoothly on transition
- [ ] Numbers count up on reveal
- [ ] Sparkline draws progressively
- [ ] Mobile swipe feels natural (spring physics)
- [ ] Loading state appears for < 500ms
- [ ] All error states render correctly

---

### Phase 4B: Privacy Messaging & Accessibility

**Goal**: Build trust and ensure accessibility.

**Deliverables**:
1. Privacy footer on first card ("We store nothing")
2. "How it works" expandable section
3. Share button tooltips (what gets shared)
4. "Learn how" modal with full privacy details
5. Keyboard navigation
6. Screen reader support
7. Reduced motion support

**Verification Criteria**:
- [ ] Privacy footer visible without scrolling on first card
- [ ] "How it works" expands to show data explanation
- [ ] Share button hover shows exactly what's shared
- [ ] Tab navigation works through all interactive elements
- [ ] Screen reader announces card transitions
- [ ] `prefers-reduced-motion` disables animations

---

## Phase 5: Platform Features (Optional, Post-Launch)

Advanced features using Cloudflare primitives. These showcase the platform but aren't required for launch. Implement after core experience is stable.

### Phase 5A: View Counter (Workers KV)

**Goal**: Show "You're Wrapped #N of YYYY"

**Deliverables**:
1. Year-namespaced KV keys (`{year}:views:{id}`, `{year}:global:count`)
2. Atomic increment on page view
3. Display count on summary card

**Verification Criteria**:
- [ ] View count increments on each unique visit
- [ ] Counter shows per-year statistics
- [ ] "You're #12,847 of 2025" displays correctly

---

### Phase 5B: Async Image Generation (Queues)

**Goal**: Non-blocking image generation for better UX.

**Deliverables**:
1. Queue job on first visit (if image not cached)
2. Consumer worker generates image
3. Polling endpoint for status
4. "Preparing your social card..." UI state

**Verification Criteria**:
- [ ] First visit returns immediately (no 3s wait)
- [ ] Polling shows "processing" → "ready" transition
- [ ] Preview appears when image is ready

---

### Phase 5C: PDF Export (Browser Rendering)

**Goal**: Download wrapped as PDF.

**Deliverables**:
1. `/pdf/:year/<data>.pdf` route
2. Puppeteer-based PDF generation
3. "Download PDF" button on summary card

**Verification Criteria**:
- [ ] PDF downloads with correct filename (`wrapped-2025.pdf`)
- [ ] PDF renders correctly (matches screen)
- [ ] Render time shown in response header

---

## Phase Dependencies

```
Phase 1A ──────────────────────────────────────────────────┐
    │                                                      │
    v                                                      │
Phase 1B ──────────────────────────────────────────────────┤
    │                                                      │
    v                                                      │
Phase 2A ─────────────────────────────────────────────┐    │
    │                                                 │    │
    v                                                 │    │
Phase 2B ────────────────────────────────────────┐    │    │
    │                                            │    │    │
    v                                            v    v    v
Phase 3 ─────────────────────> Phase 4A ──────> Phase 4B ──> LAUNCH
                                                       │
                                                       v
                                              Phase 5A-C (post-launch)
```

---

## Verification Checklist Summary

### Phase 1A: Core Data (CLI)
- [ ] `--raw` outputs valid JSON
- [ ] URL format is correct
- [ ] Year filtering works
- [ ] Encode/decode round-trip
- [ ] Edge cases handled (year boundary, future year, pre-2024)

### Phase 1B: CLI Polish
- [ ] `--name` works
- [ ] `--decode` works on any URL
- [ ] Clipboard works
- [ ] January year suggestion
- [ ] Rich output format

### Phase 2A: Static Site
- [ ] Landing page renders
- [ ] Valid URLs render cards
- [ ] Invalid years show errors
- [ ] Mobile works

### Phase 2B: Story Mode
- [ ] All cards render
- [ ] Navigation works (click, swipe, skip)
- [ ] Share buttons work
- [ ] Conditional cards appear correctly

### Phase 3: Social Cards
- [ ] PNG generates correctly
- [ ] R2 caching works
- [ ] OG tags inject correctly
- [ ] Social platforms preview correctly

### Phase 4A: Animations
- [ ] Transitions are smooth
- [ ] Mobile gestures work
- [ ] Loading/error states work

### Phase 4B: Privacy & A11y
- [ ] Privacy messaging visible
- [ ] Keyboard navigation works
- [ ] Screen reader works
- [ ] Reduced motion works

### Phase 5 (Post-Launch)
- [ ] View counter works (KV)
- [ ] Async images work (Queues)
- [ ] PDF export works (Browser Rendering)

---

## Tech Stack Summary

| Component | Technology |
|-----------|------------|
| CLI encoding | msgpack, base64 |
| CLI clipboard | pyperclip |
| Website hosting | Cloudflare Workers |
| Routing | Hono or itty-router |
| Image generation | Satori + resvg-wasm |
| Image cache | Edge Cache API |
| View counter | Cloudflare KV (Phase 5) |
| Async processing | Cloudflare Queues (Phase 5) |
| PDF generation | Cloudflare Browser Rendering (Phase 5) |
| Animations | Framer Motion |
| UI framework | Preact or Solid (lightweight) |

---

## Launch Criteria

Minimum for launch (Phases 1-4):
- [ ] CLI generates valid URLs
- [ ] Website renders all card types
- [ ] Social cards work on Twitter/LinkedIn/Facebook
- [ ] Privacy messaging is clear
- [ ] Mobile experience is polished
- [ ] No critical bugs

Post-launch enhancements (Phase 5):
- [ ] View counter (KV)
- [ ] Async image generation (Queues)
- [ ] PDF export (Browser Rendering)
