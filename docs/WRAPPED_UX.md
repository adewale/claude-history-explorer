# Claude Code Wrapped - UX Specification

> **Note**: This document describes the original card-based Story Mode which has been removed.
> Current implementation is V3-only Print view at `/wrapped?d=...` on `wrapped-claude-codes.adewale-883.workers.dev`. The old `wrapped.claude.codes/{year}/{data}` path, Story Mode, Framer Motion transitions, and "no query params" decisions below are historical/proposal content, not current behavior.

## Overview

This document specifies the user experience for the Wrapped landing page—the critical conversion point where viewers become generators, and generators become sharers.

---

## The User Journey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  DISCOVERY                    CLICK                     LAND                │
│  ─────────                    ─────                     ────                │
│                                                                             │
│  "Whoa, what's this?"  →  "Let me see"  →  "This is cool, I want one"      │
│                                                                             │
│  ┌─────────────────┐      ┌─────────────┐      ┌─────────────────────────┐  │
│  │ Social Card     │      │ Anticipation│      │ Interactive Experience  │  │
│  │ in Timeline     │  →   │ (loading)   │  →   │ + Clear CTA             │  │
│  └─────────────────┘      └─────────────┘      └─────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Why Would They Click?

### Context A: Social Media Timeline

```
┌─────────────────────────────────────────────────────────────────┐
│  @adewale · 2h                                                  │
│                                                                 │
│  My Claude Code year in review                                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │         CLAUDE CODE WRAPPED 2025                        │   │
│  │                                                         │   │
│  │              5,316 messages                             │   │
│  │         4 projects · 312 hours                          │   │
│  │                                                         │   │
│  │         ▁▂▃▅▇█▇▅▃▂▁▃                                   │   │
│  │                                                         │   │
│  │            THE ARCHITECT                                │   │
│  │                                                         │   │
│  │         wrapped.claude.codes                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  💬 12   🔁 45   ❤️ 234                                         │
└─────────────────────────────────────────────────────────────────┘
```

**Click motivations:**
- **Social proof**: "234 people liked this"
- **Curiosity**: "5,316 messages?!"
- **Comparison**: "How does mine compare?"
- **Identity**: "What's MY archetype?"
- **FOMO**: "Everyone's sharing these"

### Context B: Direct Message / Slack

```
Sarah: Check out my Claude Code stats
       https://wrapped.claude.codes/2025/eyJ5Ijoy...
```

**Click motivations:**
- Personal connection from a friend
- Conversation starter
- Trust in the sender

### Context C: Blog / Newsletter

**Click motivations:**
- Context provided by the article
- Learning how others use the tool

---

## Part 2: The URL

### Visible Structure

```
https://wrapped.claude.codes/2025/eyJ5IjoyMDI1LCJuIjoiQWRld2FsZSI...
        └──────────┬──────────┘ └─┬─┘ └──────────────┬──────────────┘
              Domain           Year         Encoded data
```

### Design Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Domain | `wrapped.claude.codes` | Memorable, clearly Claude-related |
| Year in path | `/2025/` | Human-readable, SEO-friendly |
| Data encoding | Base64URL | Compact, URL-safe, **no server storage** |
| No query params | Path only | Cleaner sharing, better caching |

---

## Part 3: The Landing Experience

### Phase 1: Loading State (0-500ms)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│                         ◐                                       │
│                                                                 │
│                   Unwrapping 2025...                            │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2: Story Mode (Default)

Users tap/click through animated cards. A "Skip to summary →" link appears in the corner.

#### Card 1: The Hook

```
┌─────────────────────────────────────────────────────────────────┐
│                                          [Skip to summary →]    │
│                                                                 │
│                                                                 │
│                        Adewale                                  │
│                           &                                     │
│                      Claude Code                                │
│                                                                 │
│                     had a big year.                             │
│                                                                 │
│                                                                 │
│                       [Tap to begin]                            │
│                                                                 │
│  ────────────────────────────────────────────────────────────   │
│  🔒 Your stats stay in this URL. We store nothing.              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Card 2: The Mind-Bending Stat

```
┌─────────────────────────────────────────────────────────────────┐
│                                          [Skip to summary →]    │
│                                                                 │
│                                                                 │
│                      You exchanged                              │
│                                                                 │
│                         5,316                                   │
│                        messages                                 │
│                                                                 │
│                  That's longer than                             │
│                   The Great Gatsby.                             │
│                                                                 │
│                   You wrote a novel.                            │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Comparison thresholds:**
- < 500: "A solid short story"
- 500-2000: "Longer than a PhD thesis"
- 2000-5000: "The Great Gatsby territory"
- 5000-10000: "War and Peace vibes"
- 10000+: "You could fill a bookshelf"

#### Card 3: The Timeline

```
┌─────────────────────────────────────────────────────────────────┐
│                                          [Skip to summary →]    │
│                                                                 │
│                      Your year in code                          │
│                                                                 │
│                 ▁▂▃▅▇█▇▅▃▂▁▃                                    │
│                 J F M A M J J A S O N D                         │
│                           ↑                                     │
│                         July                                    │
│                                                                 │
│                     was your peak.                              │
│                 Something big shipped.                          │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Pattern-based copy:**
- Steady: "Consistent builder. You showed up every month."
- End-loaded: "Late bloomer. You found your flow in Q4."
- Start-loaded: "Strong start. Hit the ground running."
- Spiky: "Burst worker. When you ship, you ship hard."

#### Card 4: The Personality

```
┌─────────────────────────────────────────────────────────────────┐
│                                          [Skip to summary →]    │
│                                                                 │
│                 Your Claude Code personality:                   │
│                                                                 │
│                    ╔════════════════════╗                       │
│                    ║   THE ARCHITECT    ║                       │
│                    ╚════════════════════╝                       │
│                                                                 │
│                      Agent-driven                               │
│                    Deep-work focused                            │
│                     High-intensity                              │
│                                                                 │
│                     You don't code.                             │
│                     You orchestrate.                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Archetypes:**
- **The Architect**: Agent-driven + Deep-work
- **The Sprinter**: High-intensity + Burst
- **The Collaborator**: Hands-on + Iterative
- **The Craftsperson**: Deliberate + Solo

#### Card 5: The Peak Project

```
┌─────────────────────────────────────────────────────────────────┐
│                                          [Skip to summary →]    │
│                                                                 │
│                      Your #1 project                            │
│                                                                 │
│                       ┌──────────┐                              │
│                       │Keyboardia│                              │
│                       └──────────┘                              │
│                                                                 │
│                  1,873 messages · 3 days                        │
│                                                                 │
│                     You were locked in.                         │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Card 6: Parallel Power (conditional, if ci > 1)

```
┌─────────────────────────────────────────────────────────────────┐
│                                          [Skip to summary →]    │
│                                                                 │
│                At your peak, you were running                   │
│                                                                 │
│                      🤖  🤖  🤖                                 │
│                                                                 │
│               3 Claude instances at once                        │
│                                                                 │
│                   You don't multitask.                          │
│                    You parallelize.                             │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Card 7: Longest Session (conditional, if notable)

```
┌─────────────────────────────────────────────────────────────────┐
│                                          [Skip to summary →]    │
│                                                                 │
│                   Your longest session:                         │
│                                                                 │
│                        50.5 hours                               │
│                                                                 │
│                                                                 │
│                     That's over 2 days.                         │
│                  Please tell us you slept.                      │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Duration-based copy:**
- < 2h: "Quick and focused. In and out."
- 2-4h: "A proper deep work session."
- 4-8h: "Full day energy."
- 8-24h: "Marathon mode. Respect."
- 24h+: "...are you okay? We're concerned."

#### Final Card: The Summary & Share

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                 CLAUDE CODE WRAPPED 2025                        │
│                                                                 │
│                        Adewale                                  │
│                                                                 │
│               5,316 messages · 312 hours                        │
│                                                                 │
│                    ▁▂▃▅▇█▇▅▃▂▁▃                                 │
│                                                                 │
│                     THE ARCHITECT                               │
│                Agent-driven · Deep-work                         │
│                                                                 │
│     ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│     │  Share X   │  │  LinkedIn  │  │    Copy    │             │
│     └────────────┘  └────────────┘  └────────────┘             │
│                                                                 │
│                ┌────────────────────────┐                       │
│                │  🎁 Get your own       │                       │
│                └────────────────────────┘                       │
│                                                                 │
│  ────────────────────────────────────────────────────────────   │
│  🔒 Privacy: All data lives in the URL. No accounts, no        │
│     tracking, no server storage. [Learn how →]                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Signaling Privacy Throughout

Privacy is a key differentiator. Users should feel safe sharing without worrying about data exposure. We signal this at multiple touchpoints:

### Strategy: Progressive Privacy Disclosure

Don't front-load a privacy policy. Instead, weave trust signals throughout the experience.

### Touchpoint 1: First Card Footer

Subtle, non-intrusive, sets the tone:

```
────────────────────────────────────────────────────────────────
🔒 Your stats stay in this URL. We store nothing.
```

### Touchpoint 2: "How it works" Expandable (Optional)

For curious users, available on any card:

```
┌─────────────────────────────────────────────────────────────────┐
│  [?] How does this work?                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Everything you see is encoded in the URL itself.               │
│                                                                 │
│  • No account required                                          │
│  • No data stored on our servers                                │
│  • No cookies or tracking                                       │
│  • Delete the URL, delete the data                              │
│                                                                 │
│  The URL IS the data. We just render it beautifully.            │
│                                                                 │
│  [View the source code →]                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Touchpoint 3: Share Button Reassurance

When hovering/tapping share buttons:

```
┌────────────────────────────────────────┐
│  Share on X                            │
│                                        │
│  Shares: aggregate counts, short       │
│  project names, and style metrics.     │
│                                        │
│  Never shares: file contents, full     │
│  paths, tool inputs, or conversations. │
└────────────────────────────────────────┘
```

### Touchpoint 4: Final Card Footer

More detailed, for those who made it through:

```
────────────────────────────────────────────────────────────────
🔒 Privacy: All data lives in the URL. No accounts, no tracking,
   no server storage. [Learn how →]
```

### Touchpoint 5: "Learn How" Modal/Page

For the deeply curious:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    How Wrapped Protects Your Privacy            │
│                                                                 │
│  ═══════════════════════════════════════════════════════════   │
│                                                                 │
│  THE URL IS THE DATABASE                                        │
│                                                                 │
│  Your Wrapped URL looks like this:                              │
│  https://wrapped.claude.codes/2025/eyJ5IjoyMDI1LCJwIjo0...     │
│                                                                 │
│  That long string? It's your entire story, encoded.             │
│  When you visit the URL, we decode it and show it to you.       │
│  We never store it. We never see it. We just render it.         │
│                                                                 │
│  ───────────────────────────────────────────────────────────    │
│                                                                 │
│  WHAT'S IN THE DATA                                             │
│                                                                 │
│  ✓ Message counts (not messages)                                │
│  ✓ Session counts and durations                                 │
│  ✓ Project counts (not names, unless you choose)                │
│  ✓ Activity patterns (monthly totals)                           │
│  ✓ Your display name (only if you add it)                       │
│                                                                 │
│  ✗ Actual conversations                                         │
│  ✗ Code you wrote                                               │
│  ✗ File paths or contents                                       │
│  ✗ Anything that could identify your work                       │
│                                                                 │
│  ───────────────────────────────────────────────────────────    │
│                                                                 │
│  THE TECHNICAL DETAILS                                          │
│                                                                 │
│  1. You run `claude-history wrapped` on YOUR machine            │
│  2. It reads YOUR local files (~/.claude/projects/)             │
│  3. It computes aggregate stats (counts, not content)           │
│  4. It encodes them as JSON → MessagePack → Base64URL           │
│  5. You get a URL. That's it. Nothing leaves your machine       │
│     except what you choose to share.                            │
│                                                                 │
│  ───────────────────────────────────────────────────────────    │
│                                                                 │
│  WHAT ABOUT THE SOCIAL PREVIEW IMAGE?                           │
│                                                                 │
│  When you share on Twitter/LinkedIn, they fetch an image.       │
│  We generate that image on-the-fly by reading the URL data.     │
│  We don't log it. We don't store it. We render and forget.      │
│                                                                 │
│  ───────────────────────────────────────────────────────────    │
│                                                                 │
│  VERIFY IT YOURSELF                                             │
│                                                                 │
│  • Decode any URL with the CLI:                                 │
│    $ claude-history wrapped --decode "https://wrapped..."       │
│                                                                 │
│  • View source: [GitHub repo]                                   │
│  • Check network tab: No analytics, no tracking pixels          │
│                                                                 │
│                        [Close]                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Touchpoint 6: OG Image Privacy Badge

The social card itself can subtly signal privacy:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│              CLAUDE CODE WRAPPED 2025                           │
│                                                                 │
│                   5,316 messages                                │
│              4 projects · 312 hours                             │
│                                                                 │
│                  ▁▂▃▅▇█▇▅▃▂▁▃                                   │
│                                                                 │
│                   THE ARCHITECT                                 │
│                                                                 │
│              wrapped.claude.codes                               │
│                                                           🔒    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

Small lock icon in corner signals "this is privacy-conscious" without being preachy.

### Touchpoint 7: CLI Decode Command

Users can verify any URL before sharing—or inspect anyone else's:

```bash
$ claude-history wrapped --decode "https://wrapped.claude.codes/2025/eyJ5IjoyMDI1..."

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

Monthly Activity:
  ▁▂▃▅▇█▇▅▃▂▁▃
  J F M A M J J A S O N D

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✓ This URL contains only aggregate statistics.
  No conversation content, code, or file paths.
```

This serves multiple trust functions:
- **Pre-share verification**: "Let me see exactly what I'm about to share"
- **Curiosity satisfaction**: "What's actually in that URL my friend shared?"
- **Architecture proof**: Demonstrates the data is just counts, not content
- **Empowerment**: Users aren't dependent on trusting us—they can verify

### Privacy Messaging Principles

| Principle | Implementation |
|-----------|----------------|
| **Show, don't tell** | "The URL IS the data" is more powerful than "we respect privacy" |
| **Be specific** | List exactly what IS and ISN'T shared |
| **Offer proof** | CLI decode command, source code, network tab |
| **Don't be preachy** | Subtle indicators > privacy policy walls |
| **Reassure at share time** | When anxiety is highest (about to share), provide comfort |
| **Make it verifiable** | `--decode` flag empowers users to inspect any URL |

---

## Part 5: The Critical CTA - "Get Your Own"

### For Users with Claude Code

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                   🎁 Get your own Wrapped                       │
│                                                                 │
│   Run this in your terminal:                                    │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  $ claude-history wrapped                         [Copy]│  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   Add your name:                                                │
│   $ claude-history wrapped --name "Your Name"                   │
│                                                                 │
│   ──────────────────────────────────────────────────────────   │
│   🔒 Runs locally. Only you see your data until you share.     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### For Users Without Claude Code

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                   🎁 Get your own Wrapped                       │
│                                                                 │
│   1. Install the history explorer:                              │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  $ uv tool install claude-history-explorer        [Copy]│  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   2. Generate your Wrapped:                                     │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  $ claude-history wrapped                         [Copy]│  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ──────────────────────────────────────────────────────────   │
│   Requires Claude Code usage history in ~/.claude/projects/     │
│                                                                 │
│   [What is Claude Code?]                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 6: Mobile Experience

Most social clicks are mobile. Design mobile-first:

```
┌──────────────────────┐
│                      │
│  CLAUDE CODE         │
│  WRAPPED 2025        │
│                      │
│      Adewale         │
│                      │
│  ────────────────    │
│                      │
│      5,316           │
│     messages         │
│                      │
│   ▁▂▃▅▇█▇▅▃▂▁▃       │
│                      │
│  ────────────────    │
│                      │
│   THE ARCHITECT      │
│                      │
│   Agent-driven       │
│   Deep-work          │
│   High-intensity     │
│                      │
│  ────────────────    │
│                      │
│  [Share]  [Copy]     │
│                      │
│  ┌────────────────┐  │
│  │ Get your own   │  │
│  └────────────────┘  │
│                      │
│  ────────────────    │
│  🔒 No data stored   │
│                      │
└──────────────────────┘
```

### Mobile Story Mode

Cards are full-screen, swipe to advance:

```
┌──────────────────────┐
│           [Skip →]   │
│                      │
│                      │
│                      │
│     You exchanged    │
│                      │
│        5,316         │
│       messages       │
│                      │
│    That's longer     │
│        than          │
│   The Great Gatsby   │
│                      │
│                      │
│                      │
│     [Swipe →]        │
│                      │
│  ────────────────    │
│  🔒 URL = database   │
└──────────────────────┘
```

---

## Part 7: Error States

### Invalid/Corrupted URL

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                         Hmm...                                  │
│                                                                 │
│          We couldn't unwrap this URL.                           │
│                                                                 │
│    The data might be corrupted or from an old version.          │
│                                                                 │
│    ┌──────────────────────────────────────────────────────┐    │
│    │         🎁 Generate a fresh Wrapped                   │    │
│    └──────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Year Mismatch

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    Something's not right                        │
│                                                                 │
│     This URL says 2025, but the data inside says 2024.          │
│                                                                 │
│          Someone might have edited the URL.                     │
│                                                                 │
│    ┌──────────────────────────────────────────────────────┐    │
│    │         🎁 Generate your own Wrapped                  │    │
│    └──────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Future Year

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    🔮 From the future?                          │
│                                                                 │
│            We can't show a 2030 Wrapped yet.                    │
│                                                                 │
│                  Check back in 5 years!                         │
│                                                                 │
│    ┌──────────────────────────────────────────────────────┐    │
│    │         🎁 Generate your 2025 Wrapped                 │    │
│    └──────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 8: The Psychological Flow

| Stage | User Feeling | Design Goal | Privacy Signal |
|-------|-------------|-------------|----------------|
| **See in feed** | Curiosity | OG image intrigues | 🔒 badge in corner |
| **Click** | Anticipation | Fast load | — |
| **First card** | Connection | Use their name | "We store nothing" footer |
| **Middle cards** | Delight | Surprising comparisons | — |
| **Personality** | Identity | Aspirational archetype | — |
| **Share card** | Pride | Easy share buttons | "What gets shared" tooltip |
| **CTA** | "I want one" | Frictionless path | "Runs locally" note |

---

## Part 9: Technical Implementation Notes

### Animation Library

Recommend **Framer Motion** for card transitions:
- Swipe gestures on mobile
- Spring physics for satisfying feel
- Exit animations when skipping

### Font

**Inter** for body, **Space Grotesk** or **JetBrains Mono** for stats/code.

### Color Palette

Dark mode default (matches developer aesthetic):
- Background: `#0a0a0f` → `#1a1a2e` gradient
- Accent: `#6366f1` (indigo)
- Text: `#ffffff` primary, `#a1a1aa` secondary
- Privacy badge: `#22c55e` (green lock)

### Performance Budget

- First contentful paint: < 1s
- Time to interactive: < 2s
- Total JS bundle: < 100KB gzipped

---

## Summary

| Decision | Choice |
|----------|--------|
| **Default mode** | Story Mode with "Skip to summary" |
| **Privacy approach** | Progressive disclosure, not policy walls |
| **Key privacy touchpoints** | First card footer, share tooltips, final card, learn more modal |
| **Trust signals** | Specific claims, source code links, verifiable architecture |
| **CTA placement** | Final card + sticky on summary view |
| **Mobile** | Full-screen swipeable cards |

The page exists to convert viewers → generators → sharers, while making everyone feel safe about what they're sharing.
