/**
 * Wrapped story page HTML
 */

import { WrappedStory, WrappedStoryV3, formatNumber, formatNumberCompact, getMessageDescriptor, isV3Story, TRAIT_LABELS, getTraitDescription, TokenStats } from '../decoder';

/**
 * Generate a tangible comparison for message count
 */
function getMessageComparison(messages: number): string {
  // Average novel is ~80,000 words, average message ~50 words
  const novelEquivalent = (messages * 50) / 80000;
  if (novelEquivalent >= 1) {
    return `That's roughly ${novelEquivalent.toFixed(1)} novels worth of conversation`;
  }
  // Average email is ~75 words
  const emailEquivalent = Math.round((messages * 50) / 75);
  return `Like writing ${formatNumber(emailEquivalent)} emails`;
}

/**
 * Generate a tangible comparison for hours
 */
function getHoursComparison(hours: number): string {
  if (hours >= 40) {
    const weeks = (hours / 40).toFixed(1);
    return `That's ${weeks} work weeks of pair programming`;
  }
  if (hours >= 8) {
    const days = Math.round(hours / 8);
    return `Like ${days} full workdays of collaboration`;
  }
  return `${Math.round(hours * 60)} minutes of focused development`;
}

/**
 * Find the peak month from activity data
 */
function getPeakMonth(activity: number[]): { name: string; value: number } {
  const months = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December'];
  if (!activity || activity.length === 0) {
    return { name: 'N/A', value: 0 };
  }
  let maxIndex = 0;
  let maxValue = activity[0] || 0;
  for (let i = 1; i < activity.length; i++) {
    if ((activity[i] || 0) > maxValue) {
      maxValue = activity[i];
      maxIndex = i;
    }
  }
  return { name: months[maxIndex] || 'N/A', value: maxValue };
}

/**
 * Determine user archetype based on their traits and style
 */
function getArchetype(story: WrappedStory | WrappedStoryV3): string {
  if (isV3Story(story)) {
    // V3: Use trait scores (0-100 integers)
    const ts = story.ts;
    if (ts.ad > 70) return 'Delegation Architect';
    if (ts.sp > 70) return 'Deep Work Specialist';
    if (ts.ri > 70) return 'Speed Demon';
    if (ts.ad > 40 && ts.ad < 60) return 'Pair Programming Pro';
    if (ts.ad < 30) return 'Hands-on Hacker';
    if (ts.bs < 30) return 'Steady Builder';
    if (ts.bs > 70) return 'Rapid Prototyper';
    return 'Code Craftsman';
  }

  // V1/V2: Use string traits
  const traits = story.t || [];
  const collab = story.c || '';
  const pace = story.w || '';

  if (traits.includes('Agent-driven') || collab === 'Heavy delegation') {
    return 'Delegation Architect';
  }
  if (traits.includes('Deep-work focused') || pace === 'Deliberate') {
    return 'Deep Work Specialist';
  }
  if (traits.includes('High-intensity') || pace === 'Rapid-fire') {
    return 'Speed Demon';
  }
  if (traits.includes('Collaborative') || collab === 'Balanced') {
    return 'Pair Programming Pro';
  }
  if (traits.includes('Hands-on') || collab === 'Hands-on') {
    return 'Hands-on Hacker';
  }
  if (traits.includes('Steady-paced') || pace === 'Steady') {
    return 'Steady Builder';
  }
  if (traits.includes('Quick-iterative')) {
    return 'Rapid Prototyper';
  }
  return 'Code Craftsman';
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(str: string): string {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Generate an SVG sparkline from monthly activity data
 */
function generateSvgSparkline(data: number[]): string {
  if (!data || data.length === 0) return '';

  const width = 320;
  const height = 60;
  const padding = 4;
  const max = Math.max(...data, 1);

  const barWidth = (width - padding * 2) / data.length - 2;
  const bars = data.map((val, i) => {
    const barHeight = Math.max((val / max) * (height - padding * 2), 2);
    const x = padding + i * ((width - padding * 2) / data.length);
    const y = height - padding - barHeight;
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="2" fill="url(#sparkGradient)" class="spark-bar" style="animation-delay: ${i * 50}ms"/>`;
  }).join('');

  return `<svg viewBox="0 0 ${width} ${height}" class="sparkline-svg">
    <defs>
      <linearGradient id="sparkGradient" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="var(--accent-light)"/>
        <stop offset="100%" stop-color="var(--accent)"/>
      </linearGradient>
    </defs>
    ${bars}
  </svg>`;
}

interface RenderOptions {
  story: WrappedStory | WrappedStoryV3;
  year: number;
  encodedData: string;
  ogImageUrl: string;
}

export function renderWrappedPage({ story, year, encodedData, ogImageUrl }: RenderOptions): string {
  const pageUrl = `https://wrapped-claude-codes.adewale-883.workers.dev/${year}/${encodedData}`;
  const displayName = story.n || 'Someone';
  const descriptor = getMessageDescriptor(story.m);

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${displayName}'s Claude Code Wrapped ${year}</title>
  <meta name="description" content="${displayName} had ${descriptor} year with Claude Code: ${formatNumber(story.m)} messages across ${story.p} projects.">

  <!-- Open Graph / Social Cards -->
  <meta property="og:type" content="website">
  <meta property="og:url" content="${pageUrl}">
  <meta property="og:title" content="${displayName}'s Claude Code Wrapped ${year}">
  <meta property="og:description" content="${formatNumber(story.m)} messages • ${story.p} projects • ${Math.round(story.h)} hours">
  <meta property="og:image" content="${ogImageUrl}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="${displayName}'s Claude Code Wrapped ${year}">
  <meta name="twitter:description" content="${formatNumber(story.m)} messages • ${story.p} projects • ${Math.round(story.h)} hours">
  <meta name="twitter:image" content="${ogImageUrl}">

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    :root {
      --bg-dark: #0a0a0a;
      --bg-card: #141414;
      --bg-card-hover: #1a1a1a;
      --text-primary: #ffffff;
      --text-secondary: #a0a0a0;
      --text-muted: #666666;
      --accent: #d4a574;
      --accent-light: #e5c9a8;
      --border: #2a2a2a;
      --success: #22c55e;
      --font-display: 'Space Grotesk', -apple-system, sans-serif;
      --font-body: 'Source Sans 3', -apple-system, sans-serif;
    }

    body {
      font-family: var(--font-body);
      background: var(--bg-dark);
      color: var(--text-primary);
      min-height: 100vh;
      overflow-x: hidden;
    }

    /* === AMBIENT BACKGROUND SYSTEM === */

    /* Layer 0: Card-Reactive Glow */
    .glow-layer {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 0;
      overflow: hidden;
    }

    .glow-orb {
      position: absolute;
      width: 140vw;
      height: 80vh;
      left: 50%;
      bottom: -20vh;
      /* Pre-blurred gradient - no runtime filter cost */
      background: radial-gradient(
        ellipse at center,
        rgba(212, 165, 116, 0.12) 0%,
        rgba(212, 165, 116, 0.06) 25%,
        rgba(212, 165, 116, 0.02) 50%,
        transparent 70%
      );
      transform: translate(var(--glow-x, -50%), var(--glow-y, 0%));
      transition: transform 1.2s cubic-bezier(0.4, 0, 0.2, 1),
                  opacity 0.8s ease-out;
      opacity: var(--glow-intensity, 1);
    }

    /* Secondary glow for depth */
    .glow-orb-secondary {
      position: absolute;
      width: 60vw;
      height: 40vh;
      left: 50%;
      top: 10%;
      background: radial-gradient(
        ellipse at center,
        rgba(139, 115, 85, 0.06) 0%,
        transparent 60%
      );
      transform: translate(var(--glow2-x, -50%), var(--glow2-y, 0%));
      transition: transform 1.5s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* Layer 1: Particle Canvas */
    .particle-layer {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 1;
    }

    .particle-layer canvas {
      width: 100%;
      height: 100%;
    }

    /* Layer 2: Film Grain (top) */
    .grain-layer {
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 9999;
      opacity: 0.06;
      mix-blend-mode: overlay;
    }

    .grain-layer canvas {
      width: 100%;
      height: 100%;
    }

    /* Mobile: Reduce effects */
    @media (max-width: 640px) {
      .glow-orb {
        opacity: 0.8;
        width: 160vw;
      }
      .glow-orb-secondary {
        display: none;
      }
      .grain-layer {
        opacity: 0.04;
      }
    }

    /* Reduced motion: Static glow only, no animation */
    @media (prefers-reduced-motion: reduce) {
      .particle-layer,
      .grain-layer {
        display: none;
      }
      .glow-orb,
      .glow-orb-secondary {
        transition: none;
      }
    }

    /* Story Mode Container */
    .story-container {
      position: fixed;
      inset: 0;
      display: flex;
      flex-direction: column;
    }

    /* Progress Bar */
    .progress-bar {
      display: flex;
      gap: 4px;
      padding: 16px;
      background: linear-gradient(to bottom, rgba(0,0,0,0.8), transparent);
      position: relative;
      z-index: 100;
    }

    .progress-segment {
      flex: 1;
      height: 3px;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 2px;
      overflow: hidden;
    }

    .progress-segment.active .progress-fill {
      animation: progress 5s linear forwards;
    }

    .progress-segment.completed .progress-fill {
      width: 100%;
    }

    .progress-fill {
      height: 100%;
      background: var(--accent);
      width: 0;
    }

    @keyframes progress {
      from { width: 0; }
      to { width: 100%; }
    }

    /* Cards Container */
    .cards-viewport {
      flex: 1;
      position: relative;
      overflow: hidden;
    }

    .card {
      position: absolute;
      inset: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      opacity: 0;
      transform: translateX(100%);
      transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .card.active {
      opacity: 1;
      transform: translateX(0);
    }

    .card.exiting {
      opacity: 0;
      transform: translateX(-100%);
    }

    .card-content {
      max-width: 600px;
      width: 90%;
      text-align: center;
    }

    /* Card Type: Hero (full-bleed intro) */
    .card-hero {
      justify-content: flex-end;
      padding-bottom: 10vh;
    }

    .card-hero .card-content {
      max-width: 800px;
    }

    .hero-year {
      font-family: var(--font-display);
      font-size: 8rem;
      font-weight: 700;
      color: var(--accent);
      opacity: 0.15;
      position: absolute;
      top: 15%;
      left: 50%;
      transform: translateX(-50%);
      letter-spacing: -0.05em;
    }

    .hero-title {
      font-family: var(--font-display);
      font-size: 2.5rem;
      font-weight: 700;
      line-height: 1.1;
      margin-bottom: 1rem;
    }

    .hero-name {
      color: var(--accent);
    }

    /* Card Type: Split (data on left, viz on right) */
    .card-split .card-content {
      max-width: 700px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 3rem;
      text-align: left;
    }

    .split-data {
      display: flex;
      flex-direction: column;
      justify-content: center;
    }

    .split-viz {
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .viz-circle {
      width: 180px;
      height: 180px;
      border-radius: 50%;
      border: 4px solid var(--accent);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-direction: column;
    }

    .viz-number {
      font-family: var(--font-display);
      font-size: 3rem;
      font-weight: 700;
      color: var(--accent);
    }

    .viz-label {
      font-size: 0.85rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    /* Card Type: Timeline (full-width) */
    .card-timeline .card-content {
      max-width: 90%;
      width: 100%;
    }

    .card-timeline .sparkline-svg {
      max-width: 100%;
      height: 100px;
    }

    .card-timeline .sparkline-labels {
      max-width: 100%;
    }

    .timeline-peak {
      margin-top: 1.5rem;
      padding: 1rem;
      background: var(--bg-card);
      border-radius: 12px;
      border: 1px solid var(--border);
    }

    .timeline-peak-label {
      font-size: 0.75rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.25rem;
    }

    .timeline-peak-value {
      font-family: var(--font-display);
      font-weight: 600;
      color: var(--accent);
    }

    /* Card Type: Radar (personality) */
    .card-radar .card-content {
      max-width: 650px;
    }

    .radar-container {
      position: relative;
      width: 200px;
      height: 200px;
      margin: 1.5rem auto;
    }

    .radar-bg {
      position: absolute;
      inset: 0;
      border: 1px solid var(--border);
      border-radius: 50%;
    }

    .radar-bg::before {
      content: '';
      position: absolute;
      inset: 25%;
      border: 1px solid var(--border);
      border-radius: 50%;
    }

    .radar-point {
      position: absolute;
      width: 10px;
      height: 10px;
      background: var(--accent);
      border-radius: 50%;
      transform: translate(-50%, -50%);
    }

    .radar-label {
      position: absolute;
      font-size: 0.7rem;
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .archetype-badge {
      display: inline-block;
      padding: 0.5rem 1.5rem;
      background: var(--accent);
      color: var(--bg-dark);
      font-family: var(--font-display);
      font-weight: 600;
      border-radius: 4px;
      margin-top: 1rem;
    }

    /* Card Type: Grid (projects) */
    .card-grid .card-content {
      max-width: 700px;
    }

    .project-cards {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.75rem;
      margin-top: 1.5rem;
    }

    .project-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem;
      text-align: center;
      opacity: 0;
      transform: scale(0.9);
    }

    .card.active .project-card {
      animation: scaleIn 0.4s ease-out forwards;
    }

    .card.active .project-card:nth-child(1) { animation-delay: 0.2s; }
    .card.active .project-card:nth-child(2) { animation-delay: 0.3s; }
    .card.active .project-card:nth-child(3) { animation-delay: 0.4s; }

    .project-card-rank {
      font-family: var(--font-display);
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--accent);
      margin-bottom: 0.5rem;
    }

    .project-card-name {
      font-weight: 600;
      font-size: 0.95rem;
      margin-bottom: 0.5rem;
      word-break: break-word;
      line-height: 1.2;
    }

    .project-card-stat {
      font-size: 0.75rem;
      color: var(--text-muted);
    }

    /* Card Type: Polaroid (summary) */
    .card-polaroid .card-content {
      max-width: 350px;
    }

    .polaroid-frame {
      background: #fafafa;
      padding: 1rem 1rem 3rem;
      border-radius: 4px;
      box-shadow: 0 10px 40px rgba(0,0,0,0.4);
      transform: rotate(-2deg);
    }

    .polaroid-inner {
      background: var(--bg-dark);
      padding: 1.5rem;
      aspect-ratio: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
    }

    .polaroid-stat {
      text-align: center;
    }

    .polaroid-stat-value {
      font-family: var(--font-display);
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--accent);
    }

    .polaroid-stat-label {
      font-size: 0.7rem;
      color: var(--text-muted);
      text-transform: uppercase;
    }

    .polaroid-caption {
      font-family: 'Courier New', monospace;
      color: #333;
      font-size: 0.9rem;
      text-align: center;
      margin-top: -2rem;
    }

    .polaroid-year {
      font-weight: bold;
    }

    /* V3 Heatmap Card */
    .card-heatmap .card-content {
      max-width: 600px;
    }

    .heatmap-svg {
      margin: 1rem auto;
    }

    .heatmap-title {
      font-size: 0.9rem;
      color: var(--text-secondary);
      margin-top: 1rem;
    }

    /* V3 Timeline Events Card */
    .timeline-events {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      margin-top: 1rem;
      text-align: left;
    }

    .timeline-event {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.5rem 0.75rem;
      background: var(--bg-card);
      border-radius: 8px;
      font-size: 0.9rem;
    }

    .event-icon {
      font-size: 1.2rem;
    }

    .event-label {
      flex: 1;
      color: var(--text-primary);
    }

    .event-date {
      color: var(--text-muted);
      font-size: 0.8rem;
    }

    .event-project {
      color: var(--accent);
      font-size: 0.8rem;
      max-width: 80px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* V3 Trait Bars Card */
    .trait-bars {
      width: 100%;
      max-width: 450px;
      margin: 1.5rem auto 0;
    }

    .trait-bar-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.75rem;
    }

    .trait-bar-label {
      width: 80px;
      font-size: 0.8rem;
      color: var(--text-secondary);
      text-align: right;
    }

    .trait-bar-container {
      flex: 1;
      height: 8px;
      background: var(--bg-card);
      border-radius: 4px;
      position: relative;
      overflow: visible;
    }

    .trait-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--accent-light));
      border-radius: 4px;
      transition: width 0.5s ease-out;
    }

    .trait-bar-marker {
      position: absolute;
      top: -3px;
      width: 4px;
      height: 14px;
      background: var(--accent-light);
      border-radius: 2px;
      transform: translateX(-50%);
    }

    .trait-bar-value {
      width: 24px;
      font-size: 0.75rem;
      color: var(--accent);
      text-align: left;
    }

    /* Stats Grid (for streaks, etc) */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 1rem;
      margin-top: 1.5rem;
    }

    .stat-item {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      text-align: center;
    }

    .stat-item.highlight {
      border-color: var(--accent);
      background: rgba(212, 165, 116, 0.1);
    }

    .stat-item.current {
      border-color: var(--success);
      background: rgba(34, 197, 94, 0.1);
    }

    .stat-value {
      font-family: var(--font-display);
      font-size: 2rem;
      font-weight: 700;
      color: var(--accent);
    }

    .stat-item.current .stat-value {
      color: var(--success);
    }

    .stat-label {
      font-size: 0.75rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-top: 0.25rem;
    }

    /* Token Stats */
    .token-stats {
      margin-top: 1rem;
      text-align: center;
    }

    .token-total {
      margin-bottom: 1.5rem;
    }

    .token-value {
      font-family: var(--font-display);
      font-size: 3rem;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), var(--accent-light));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .token-label {
      font-size: 0.9rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .token-breakdown {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
      margin-bottom: 1rem;
    }

    .token-row {
      display: flex;
      justify-content: space-between;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--border);
    }

    .token-row:last-child {
      border-bottom: none;
    }

    .token-row.cache {
      color: var(--success);
    }

    .token-type {
      color: var(--text-secondary);
    }

    .token-count {
      font-family: var(--font-display);
      font-weight: 600;
    }

    .model-breakdown {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
    }

    .model-header {
      font-size: 0.75rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.75rem;
      text-align: left;
    }

    .model-row {
      display: flex;
      justify-content: space-between;
      padding: 0.4rem 0;
    }

    .model-name {
      color: var(--text-secondary);
    }

    .model-count {
      font-family: var(--font-display);
      font-weight: 600;
      color: var(--accent);
    }

    /* Longest Session Card */
    .session-highlight {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1rem;
    }

    .session-big-number {
      font-family: var(--font-display);
      font-size: 5rem;
      font-weight: 700;
      color: var(--accent);
      line-height: 1;
    }

    .session-unit {
      font-size: 1.5rem;
      color: var(--text-secondary);
      margin-left: 0.25rem;
    }

    /* View toggle buttons */
    .view-toggle {
      display: flex;
      gap: 0.5rem;
    }

    .view-btn {
      padding: 0.5rem 1rem;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text-secondary);
      font-size: 0.8rem;
      cursor: pointer;
      transition: all 0.2s;
      text-decoration: none;
    }

    .view-btn:hover {
      background: var(--bg-card-hover);
      color: var(--text-primary);
    }

    .view-btn.active {
      background: var(--accent);
      color: var(--bg-dark);
      border-color: var(--accent);
    }

    /* Pause button */
    .pause-btn {
      background: none;
      border: none;
      color: var(--text-secondary);
      cursor: pointer;
      padding: 0.5rem;
      font-size: 1.2rem;
      transition: color 0.2s;
    }

    .pause-btn:hover {
      color: var(--text-primary);
    }

    .pause-btn.paused {
      color: var(--accent);
    }

    /* Hide elements on last card */
    .on-last-card .skip-btn,
    .on-last-card #nextBtn {
      display: none;
    }

    @media (max-width: 640px) {
      .card-content {
        width: 95%;
      }

      .card-split .card-content {
        grid-template-columns: 1fr;
        gap: 1.5rem;
        text-align: center;
      }

      .hero-year {
        font-size: 5rem;
      }

      .hero-title {
        font-size: 1.75rem;
      }

      .project-cards {
        grid-template-columns: 1fr;
      }

      .viz-circle {
        width: 150px;
        height: 150px;
      }

      .viz-number {
        font-size: 2.5rem;
      }

      .big-number {
        font-size: 3.5rem;
      }

      .view-toggle {
        flex-wrap: wrap;
        justify-content: center;
      }
    }

    /* Landscape mobile */
    @media (max-height: 500px) and (orientation: landscape) {
      .card {
        padding: 1rem;
      }

      .card-content {
        max-width: 90%;
      }

      .card-split .card-content {
        grid-template-columns: 1fr 1fr;
        gap: 2rem;
      }

      .big-number {
        font-size: 3rem;
      }

      .viz-circle {
        width: 100px;
        height: 100px;
      }

      .viz-number {
        font-size: 1.75rem;
      }

      .hero-year {
        font-size: 4rem;
        top: 5%;
      }

      .card-hero {
        padding-bottom: 5vh;
      }

      .progress-bar {
        padding: 8px;
      }

      .nav-controls {
        padding: 0.5rem 1rem;
      }
    }

    /* Card Styles */
    .card-emoji {
      font-size: 4rem;
      margin-bottom: 1.5rem;
      opacity: 0;
      transform: scale(0) rotate(-10deg);
    }

    .card.active .card-emoji {
      animation: emojiPop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
    }

    .card-title {
      font-family: var(--font-display);
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 1rem;
      line-height: 1.2;
      opacity: 0;
      transform: translateY(20px);
    }

    .card.active .card-title {
      animation: fadeSlideUp 0.5s ease-out 0.15s forwards;
    }

    .card-subtitle {
      font-size: 1.1rem;
      color: var(--text-secondary);
      margin-bottom: 2rem;
      opacity: 0;
    }

    .card.active .card-subtitle {
      animation: fadeIn 0.4s ease-out 0.4s forwards;
    }

    .big-number {
      font-family: var(--font-display);
      font-size: 5rem;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent), var(--accent-light));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 0.5rem;
      opacity: 0;
      transform: scale(0.8);
    }

    .card.active .big-number {
      animation: scaleIn 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) 0.2s forwards;
    }

    .big-number-label {
      font-size: 1.5rem;
      color: var(--text-secondary);
      opacity: 0;
    }

    .card.active .big-number-label {
      animation: fadeIn 0.4s ease-out 0.45s forwards;
    }

    /* Staggered entrance animations */
    @keyframes fadeSlideUp {
      from { opacity: 0; transform: translateY(20px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }

    @keyframes scaleIn {
      from { opacity: 0; transform: scale(0.8); }
      to { opacity: 1; transform: scale(1); }
    }

    @keyframes emojiPop {
      0% { opacity: 0; transform: scale(0) rotate(-10deg); }
      60% { transform: scale(1.2) rotate(5deg); }
      100% { opacity: 1; transform: scale(1) rotate(0); }
    }

    .sparkline-container {
      margin: 1.5rem 0;
      opacity: 0;
    }

    .card.active .sparkline-container {
      animation: fadeIn 0.5s ease-out 0.3s forwards;
    }

    .sparkline-svg {
      width: 100%;
      max-width: 320px;
      height: 60px;
      margin: 0 auto;
      display: block;
    }

    .spark-bar {
      opacity: 0;
      transform-origin: bottom;
    }

    .card.active .spark-bar {
      animation: barGrow 0.4s ease-out forwards;
    }

    @keyframes barGrow {
      from { opacity: 0; transform: scaleY(0); }
      to { opacity: 1; transform: scaleY(1); }
    }

    .sparkline-labels {
      display: flex;
      justify-content: space-between;
      color: var(--text-muted);
      font-size: 0.7rem;
      padding: 0.5rem 0.25rem 0;
      font-family: var(--font-display);
      max-width: 320px;
      margin: 0 auto;
    }

    .traits-list {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      justify-content: center;
      margin-top: 1.5rem;
    }

    .trait-badge {
      background: var(--bg-card);
      border: 1px solid var(--border);
      padding: 0.5rem 1rem;
      border-radius: 20px;
      font-size: 0.9rem;
      opacity: 0;
      transform: translateY(10px);
    }

    .card.active .trait-badge {
      animation: fadeSlideUp 0.4s ease-out forwards;
    }

    .card.active .trait-badge:nth-child(1) { animation-delay: 0.3s; }
    .card.active .trait-badge:nth-child(2) { animation-delay: 0.4s; }
    .card.active .trait-badge:nth-child(3) { animation-delay: 0.5s; }
    .card.active .trait-badge:nth-child(4) { animation-delay: 0.6s; }

    .top-projects {
      margin-top: 1.5rem;
      text-align: left;
    }

    .project-item {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border);
      opacity: 0;
      transform: translateX(-20px);
    }

    .card.active .project-item {
      animation: fadeSlideRight 0.4s ease-out forwards;
    }

    .card.active .project-item:nth-child(1) { animation-delay: 0.2s; }
    .card.active .project-item:nth-child(2) { animation-delay: 0.35s; }
    .card.active .project-item:nth-child(3) { animation-delay: 0.5s; }

    @keyframes fadeSlideRight {
      from { opacity: 0; transform: translateX(-20px); }
      to { opacity: 1; transform: translateX(0); }
    }

    .project-rank {
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--accent);
      width: 2rem;
      font-family: var(--font-display);
    }

    .project-info {
      flex: 1;
    }

    .project-name {
      font-weight: 600;
      margin-bottom: 0.25rem;
    }

    .project-stats {
      font-size: 0.875rem;
      color: var(--text-secondary);
    }

    /* Share Card */
    .share-buttons {
      display: flex;
      gap: 1rem;
      margin-top: 2rem;
      flex-wrap: wrap;
      justify-content: center;
    }

    .share-btn {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.75rem 1.5rem;
      border-radius: 8px;
      font-size: 0.95rem;
      font-weight: 500;
      text-decoration: none;
      transition: all 0.2s;
      cursor: pointer;
      border: none;
    }

    .share-btn.twitter {
      background: #1da1f2;
      color: white;
    }

    .share-btn.linkedin {
      background: #0077b5;
      color: white;
    }

    .share-btn.copy {
      background: var(--bg-card);
      color: var(--text-primary);
      border: 1px solid var(--border);
    }

    .share-btn:hover {
      transform: translateY(-2px);
      filter: brightness(1.1);
    }

    .share-btn:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }

    .nav-btn:focus-visible,
    .skip-btn:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }

    /* Navigation */
    .nav-controls {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 1.5rem 1rem;
      background: linear-gradient(to top, rgba(0,0,0,0.8), transparent);
      gap: 0.5rem;
    }

    .nav-center {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.25rem;
    }

    .nav-btn {
      background: var(--bg-card);
      border: 1px solid var(--border);
      color: var(--text-primary);
      padding: 1rem 1.75rem;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.9rem;
      transition: all 0.2s;
      min-height: 48px;
      min-width: 48px;
    }

    .nav-btn:hover {
      background: var(--bg-card-hover);
    }

    .nav-btn:disabled {
      opacity: 0.3;
      cursor: not-allowed;
      pointer-events: none;
    }

    .nav-btn:disabled:hover {
      background: var(--bg-card);
      transform: none;
    }

    .skip-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 0.875rem;
      padding: 0.75rem 1rem;
      min-height: 44px;
    }

    .skip-btn:hover {
      color: var(--text-secondary);
    }

    /* Privacy Footer - integrated into nav */
    .privacy-link {
      font-size: 0.65rem;
      color: var(--text-muted);
      text-decoration: none;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.25rem;
      padding: 0.5rem 0.75rem;
      min-height: 32px;
      white-space: nowrap;
    }

    .privacy-link:hover {
      color: var(--text-secondary);
    }

    /* Privacy Modal */
    .privacy-modal {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.8);
      backdrop-filter: blur(4px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 2000;
      opacity: 0;
      visibility: hidden;
      transition: opacity 0.3s, visibility 0.3s;
      padding: 1rem;
    }

    .privacy-modal.visible {
      opacity: 1;
      visibility: visible;
    }

    .privacy-modal-content {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 2rem;
      max-width: 400px;
      width: 100%;
      transform: translateY(20px);
      transition: transform 0.3s;
    }

    .privacy-modal.visible .privacy-modal-content {
      transform: translateY(0);
    }

    .privacy-modal-header {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1.5rem;
    }

    .privacy-modal-icon {
      font-size: 1.5rem;
    }

    .privacy-modal-title {
      font-family: var(--font-display);
      font-size: 1.25rem;
      font-weight: 600;
    }

    .privacy-modal-body {
      color: var(--text-secondary);
      font-size: 0.95rem;
      line-height: 1.6;
    }

    .privacy-modal-body p {
      margin-bottom: 1rem;
    }

    .privacy-modal-list {
      list-style: none;
      padding: 0;
      margin: 1rem 0;
    }

    .privacy-modal-list li {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--border);
    }

    .privacy-modal-list li:last-child {
      border-bottom: none;
    }

    .privacy-modal-check {
      color: var(--success);
    }

    .privacy-modal-close {
      width: 100%;
      padding: 0.75rem;
      margin-top: 1.5rem;
      background: var(--accent);
      color: var(--bg-dark);
      border: none;
      border-radius: 8px;
      font-family: var(--font-display);
      font-weight: 600;
      font-size: 0.95rem;
      cursor: pointer;
      transition: opacity 0.2s;
    }

    .privacy-modal-close:hover {
      opacity: 0.9;
    }

    /* Confetti Animation */
    .confetti-container {
      position: fixed;
      inset: 0;
      pointer-events: none;
      overflow: hidden;
      z-index: 1000;
    }

    .confetti {
      position: absolute;
      width: 10px;
      height: 10px;
      opacity: 0;
    }

    .confetti.active {
      animation: confettiFall 3s ease-out forwards;
    }

    @keyframes confettiFall {
      0% {
        opacity: 1;
        transform: translateY(-20px) rotate(0deg);
      }
      100% {
        opacity: 0;
        transform: translateY(100vh) rotate(720deg);
      }
    }

    /* Tangible comparison */
    .comparison-text {
      font-size: 0.9rem;
      color: var(--text-muted);
      margin-top: 0.75rem;
      font-style: italic;
      opacity: 0;
    }

    .card.active .comparison-text {
      animation: fadeIn 0.4s ease-out 0.6s forwards;
    }

    /* Mobile Touch */
    @media (max-width: 640px) {
      .card-title {
        font-size: 1.5rem;
      }
      .big-number {
        font-size: 3rem;
      }
      .nav-controls {
        padding: 0.5rem 0.5rem 0.75rem;
      }
      .nav-btn {
        padding: 0.875rem 1.25rem;
        font-size: 0.85rem;
        min-height: 48px;
        min-width: 80px;
      }
      .skip-btn {
        font-size: 0.75rem;
        padding: 0.625rem 0.75rem;
        min-height: 40px;
      }
      .privacy-link {
        font-size: 0.6rem;
        padding: 0.375rem 0.5rem;
        min-height: 28px;
      }
    }
  </style>
</head>
<body>
  <!-- Ambient Background System -->
  <div class="glow-layer" id="glowLayer">
    <div class="glow-orb" id="glowOrb"></div>
    <div class="glow-orb-secondary" id="glowOrb2"></div>
  </div>
  <div class="particle-layer" id="particleLayer"><canvas></canvas></div>
  <div class="grain-layer" id="grainLayer"><canvas></canvas></div>

  <div class="story-container">
    <!-- Progress Bar - segments generated by JS based on card count -->
    <div class="progress-bar" id="progress"></div>

    <!-- Cards -->
    <div class="cards-viewport" id="viewport">
      ${renderCards(story, year, pageUrl)}
    </div>

    <!-- Navigation -->
    <div class="nav-controls" id="navControls">
      <button class="nav-btn" id="prevBtn" onclick="prevCard()" disabled>← Back</button>
      <div class="nav-center">
        <div style="display: flex; align-items: center; gap: 1rem;">
          <button class="pause-btn" id="pauseBtn" onclick="togglePause()" title="Pause/Play">⏸</button>
          <button class="skip-btn" onclick="skipToSummary()">Skip to summary</button>
        </div>
        <div class="view-toggle">
          <a href="?view=bento&d=${encodedData}" class="view-btn" title="Bento grid view">📊 Bento</a>
          <a href="?view=print&d=${encodedData}" class="view-btn" title="Print-friendly view">🖨️ Print</a>
        </div>
        <a href="javascript:void(0)" class="privacy-link" onclick="showPrivacyInfo()">🔒 Data in URL only</a>
      </div>
      <button class="nav-btn" id="nextBtn" onclick="nextCard()">Next →</button>
    </div>

    <!-- Confetti Container -->
    <div class="confetti-container" id="confetti"></div>

    <!-- Privacy Modal -->
    <div class="privacy-modal" id="privacyModal" onclick="hidePrivacyModal(event)">
      <div class="privacy-modal-content" onclick="event.stopPropagation()">
        <div class="privacy-modal-header">
          <span class="privacy-modal-icon">🔒</span>
          <span class="privacy-modal-title">Your Data, Your Control</span>
        </div>
        <div class="privacy-modal-body">
          <p>All your Wrapped data is encoded directly in the URL using MessagePack + Base64. Nothing is sent to our servers.</p>
          <ul class="privacy-modal-list">
            <li><span class="privacy-modal-check">✓</span> We never see your code</li>
            <li><span class="privacy-modal-check">✓</span> We never store conversations</li>
            <li><span class="privacy-modal-check">✓</span> No file paths collected</li>
            <li><span class="privacy-modal-check">✓</span> Project names only shown if you share</li>
          </ul>
          <p style="font-size: 0.85rem; color: var(--text-muted);">Verify by checking the Network tab in DevTools — no data leaves your browser.</p>
        </div>
        <button class="privacy-modal-close" onclick="hidePrivacyModal()">Got it</button>
      </div>
    </div>
  </div>

  <script>
    // ============================================
    // AMBIENT BACKGROUND SYSTEM
    // Combines: Particles + Card-Reactive Glow + Grain
    // ============================================

    const AmbientSystem = {
      reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      isMobile: window.innerWidth <= 640,
      paused: false,

      // Glow positions for each card (main orb)
      glowPositions: [
        { x: '-50%', y: '0%', intensity: 1 },      // 0: Hero
        { x: '-55%', y: '-5%', intensity: 1 },    // 1: Messages
        { x: '-45%', y: '-5%', intensity: 1 },    // 2: Projects
        { x: '-50%', y: '-15%', intensity: 0.9 }, // 3: Timeline
        { x: '-50%', y: '-10%', intensity: 1 },   // 4: Personality
        { x: '-50%', y: '-8%', intensity: 0.9 },  // 5: Top projects
        { x: '-48%', y: '-12%', intensity: 1 },   // 6: Highlight
        { x: '-50%', y: '5%', intensity: 1.2 },   // 7: Final - brighter
      ],

      // Secondary glow positions (subtle, opposite movement)
      glow2Positions: [
        { x: '-50%', y: '0%' },
        { x: '-40%', y: '5%' },
        { x: '-60%', y: '5%' },
        { x: '-45%', y: '-5%' },
        { x: '-55%', y: '0%' },
        { x: '-50%', y: '5%' },
        { x: '-52%', y: '-5%' },
        { x: '-50%', y: '10%' },
      ],

      init() {
        this.initGlow();
        if (!this.reducedMotion) {
          this.initParticles();
          this.initGrain();
        }

        // Pause/resume on visibility change
        document.addEventListener('visibilitychange', () => {
          this.paused = document.hidden;
          if (!this.paused && !this.reducedMotion) {
            this.particles?.resume();
            this.grain?.resume();
          }
        });
      },

      // Update glow position based on current card
      updateGlow(cardIndex) {
        const orb = document.getElementById('glowOrb');
        const orb2 = document.getElementById('glowOrb2');
        const pos = this.glowPositions[cardIndex] || this.glowPositions[0];
        const pos2 = this.glow2Positions[cardIndex] || this.glow2Positions[0];

        if (orb) {
          orb.style.setProperty('--glow-x', pos.x);
          orb.style.setProperty('--glow-y', pos.y);
          orb.style.setProperty('--glow-intensity', pos.intensity);
        }
        if (orb2) {
          orb2.style.setProperty('--glow2-x', pos2.x);
          orb2.style.setProperty('--glow2-y', pos2.y);
        }
      },

      initGlow() {
        this.updateGlow(0);
      },

      // ---- PARTICLE SYSTEM ----
      initParticles() {
        const canvas = document.querySelector('#particleLayer canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const particleCount = this.isMobile ? 30 : 50;
        const fps = this.isMobile ? 20 : 30;
        const frameInterval = 1000 / fps;
        let particles = [];
        let lastTime = 0;
        let animationId;

        function resize() {
          canvas.width = window.innerWidth;
          canvas.height = window.innerHeight;
        }

        function createParticle(fromTop = false) {
          return {
            x: Math.random() * canvas.width,
            y: fromTop ? -20 : Math.random() * canvas.height,
            size: Math.random() * 2.5 + 0.5, // 0.5-3px (slightly larger for snow)
            speed: Math.random() * 15 + 10, // 10-25 px/sec (gentle fall)
            opacity: Math.random() * 0.5 + 0.2, // 0.2-0.7 (brighter for stars)
            wobblePhase: Math.random() * Math.PI * 2,
            wobbleSpeed: Math.random() * 0.4 + 0.3, // Slightly faster wobble
            wobbleAmp: Math.random() * 0.8 + 0.3, // Varying wobble width
            twinkle: Math.random() > 0.7, // 30% chance to twinkle
            twinkleSpeed: Math.random() * 2 + 1,
          };
        }

        function initParticles() {
          particles = [];
          for (let i = 0; i < particleCount; i++) {
            particles.push(createParticle(false));
          }
        }

        function update(deltaTime) {
          const dt = deltaTime / 1000;
          const time = Date.now() * 0.001;

          particles.forEach(p => {
            // Gentle downward drift (like snow)
            p.y += p.speed * dt;

            // Soft horizontal sway (snow-like)
            p.x += Math.sin(time * p.wobbleSpeed + p.wobblePhase) * p.wobbleAmp;

            // Respawn at top when off screen
            if (p.y > canvas.height + 20) {
              Object.assign(p, createParticle(true));
            }

            // Wrap horizontal
            if (p.x < -10) p.x = canvas.width + 10;
            if (p.x > canvas.width + 10) p.x = -10;
          });
        }

        function draw() {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          const time = Date.now() * 0.001;

          particles.forEach(p => {
            // Calculate opacity with optional twinkle
            let opacity = p.opacity;
            if (p.twinkle) {
              // Gentle pulsing for star-like twinkle
              opacity *= 0.6 + 0.4 * Math.sin(time * p.twinkleSpeed + p.wobblePhase);
            }

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            // Warm amber/white blend for snow-star effect
            ctx.fillStyle = \`rgba(230, 200, 160, \${opacity})\`;
            ctx.fill();
          });
        }

        function animate(currentTime) {
          animationId = requestAnimationFrame(animate);

          if (AmbientSystem.paused) return;

          const delta = currentTime - lastTime;
          if (delta < frameInterval) return;

          update(delta);
          draw();
          lastTime = currentTime;
        }

        // Initialize
        resize();
        initParticles();
        window.addEventListener('resize', () => {
          resize();
          initParticles();
        });

        animationId = requestAnimationFrame(animate);

        this.particles = {
          resume: () => {
            lastTime = 0;
            if (!animationId) animationId = requestAnimationFrame(animate);
          }
        };
      },

      // ---- GRAIN SYSTEM ----
      initGrain() {
        const canvas = document.querySelector('#grainLayer canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const fps = 24;
        const frameInterval = 1000 / fps;
        let lastTime = 0;
        let animationId;

        function resize() {
          // Low resolution for performance
          canvas.width = Math.ceil(window.innerWidth / 4);
          canvas.height = Math.ceil(window.innerHeight / 4);
        }

        function generateNoise() {
          const imageData = ctx.createImageData(canvas.width, canvas.height);
          const data = imageData.data;

          for (let i = 0; i < data.length; i += 4) {
            const value = Math.random() * 255;
            data[i] = value;
            data[i + 1] = value;
            data[i + 2] = value;
            data[i + 3] = 255;
          }

          ctx.putImageData(imageData, 0, 0);
        }

        function animate(currentTime) {
          animationId = requestAnimationFrame(animate);

          if (AmbientSystem.paused) return;

          if (currentTime - lastTime < frameInterval) return;
          lastTime = currentTime;

          generateNoise();
        }

        resize();
        window.addEventListener('resize', resize);
        animationId = requestAnimationFrame(animate);

        this.grain = {
          resume: () => {
            lastTime = 0;
            if (!animationId) animationId = requestAnimationFrame(animate);
          }
        };
      }
    };

    // Initialize ambient system
    AmbientSystem.init();

    // ============================================
    // STORY NAVIGATION
    // ============================================

    let currentCard = 0;
    let totalCards = 0;
    let autoAdvanceTimer = null;
    let confettiTriggered = false;
    let isPaused = false;

    // Initialize progress bar based on actual card count
    function initProgress() {
      const cards = document.querySelectorAll('.card');
      totalCards = cards.length;
      const progressBar = document.getElementById('progress');
      progressBar.innerHTML = Array(totalCards).fill(0).map(() =>
        '<div class="progress-segment"><div class="progress-fill"></div></div>'
      ).join('');
    }

    // Toggle pause state
    function togglePause() {
      isPaused = !isPaused;
      const pauseBtn = document.getElementById('pauseBtn');
      if (isPaused) {
        pauseBtn.textContent = '▶';
        pauseBtn.classList.add('paused');
        clearTimeout(autoAdvanceTimer);
        // Pause progress bar animation
        document.querySelectorAll('.progress-fill').forEach(el => {
          el.style.animationPlayState = 'paused';
        });
      } else {
        pauseBtn.textContent = '⏸';
        pauseBtn.classList.remove('paused');
        // Resume progress bar animation
        document.querySelectorAll('.progress-fill').forEach(el => {
          el.style.animationPlayState = 'running';
        });
        // Restart auto-advance
        if (currentCard < totalCards - 1) {
          autoAdvanceTimer = setTimeout(() => nextCard(), 5000);
        }
      }
    }

    // Call on load
    initProgress();

    function updateCard() {
      const cards = document.querySelectorAll('.card');
      const segments = document.querySelectorAll('.progress-segment');

      cards.forEach((card, i) => {
        card.classList.remove('active', 'exiting');
        if (i === currentCard) {
          card.classList.add('active');
        } else if (i < currentCard) {
          card.classList.add('exiting');
        }
      });

      segments.forEach((seg, i) => {
        seg.classList.remove('active', 'completed');
        // Force reflow to restart animation when going back
        const fill = seg.querySelector('.progress-fill');
        if (fill) {
          fill.style.animation = 'none';
          fill.offsetHeight; // Trigger reflow
          fill.style.animation = '';
        }
        if (i < currentCard) {
          seg.classList.add('completed');
        } else if (i === currentCard) {
          seg.classList.add('active');
        }
      });

      document.getElementById('prevBtn').disabled = currentCard === 0;

      // Handle last card - hide skip and next buttons
      const navControls = document.getElementById('navControls');
      if (currentCard === totalCards - 1) {
        navControls.classList.add('on-last-card');
      } else {
        navControls.classList.remove('on-last-card');
      }

      // Update ambient glow position
      AmbientSystem.updateGlow(currentCard);

      // Trigger confetti on final card
      if (currentCard === totalCards - 1 && !confettiTriggered) {
        confettiTriggered = true;
        triggerConfetti();
      }

      // Auto-advance (except last card, and not if paused)
      clearTimeout(autoAdvanceTimer);
      if (currentCard < totalCards - 1 && !isPaused) {
        autoAdvanceTimer = setTimeout(() => nextCard(), 5000);
      }
    }

    function triggerConfetti() {
      const container = document.getElementById('confetti');
      const colors = ['#d4a574', '#e5c9a8', '#22c55e', '#ffffff', '#fbbf24'];
      const shapes = ['square', 'circle'];

      for (let i = 0; i < 50; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.left = Math.random() * 100 + '%';
        confetti.style.background = colors[Math.floor(Math.random() * colors.length)];
        confetti.style.animationDelay = Math.random() * 0.5 + 's';
        confetti.style.animationDuration = (2 + Math.random() * 2) + 's';
        if (shapes[Math.floor(Math.random() * shapes.length)] === 'circle') {
          confetti.style.borderRadius = '50%';
        }
        container.appendChild(confetti);
        setTimeout(() => confetti.classList.add('active'), 10);
        setTimeout(() => confetti.remove(), 4000);
      }
    }

    function nextCard() {
      if (currentCard < totalCards - 1) {
        currentCard++;
        updateCard();
      }
    }

    function prevCard() {
      if (currentCard > 0) {
        currentCard--;
        updateCard();
      }
    }

    function skipToSummary() {
      currentCard = totalCards - 1;
      updateCard();
    }

    function copyUrl() {
      navigator.clipboard.writeText('${pageUrl}');
      const btn = document.querySelector('.share-btn.copy');
      btn.textContent = '✓ Copied!';
      setTimeout(() => {
        btn.textContent = '📋 Copy URL';
      }, 2000);
    }

    function showPrivacyInfo() {
      document.getElementById('privacyModal').classList.add('visible');
    }

    function hidePrivacyModal(event) {
      if (!event || event.target === event.currentTarget) {
        document.getElementById('privacyModal').classList.remove('visible');
      }
    }

    // Touch/swipe support
    let touchStartX = 0;
    let touchStartY = 0;
    document.addEventListener('touchstart', e => {
      touchStartX = e.touches[0].clientX;
      touchStartY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', e => {
      const touchEndX = e.changedTouches[0].clientX;
      const touchEndY = e.changedTouches[0].clientY;
      const diffX = touchStartX - touchEndX;
      const diffY = touchStartY - touchEndY;

      // Only trigger swipe if horizontal movement > vertical (not scrolling)
      if (Math.abs(diffX) > 50 && Math.abs(diffX) > Math.abs(diffY)) {
        if (diffX > 0) nextCard();
        else prevCard();
      }
    }, { passive: true });

    // Keyboard support
    document.addEventListener('keydown', e => {
      // Don't capture spacebar if focus is on a button or link
      if (e.key === ' ' && (e.target.tagName === 'BUTTON' || e.target.tagName === 'A')) {
        return;
      }
      if (e.key === 'ArrowRight' || e.key === ' ') nextCard();
      if (e.key === 'ArrowLeft') prevCard();
    });

    // Initialize
    updateCard();
  </script>
</body>
</html>`;
}

function generateProgressSegments(count: number): string {
  return Array(count).fill(0).map(() =>
    '<div class="progress-segment"><div class="progress-fill"></div></div>'
  ).join('');
}

// V3 Visualization helpers
function renderHeatmapSvg(hm: number[]): string {
  if (!hm || hm.length !== 168) return '';

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const cellSize = 12;
  const gap = 2;
  const labelWidth = 30;
  const width = labelWidth + 24 * (cellSize + gap);
  const height = 7 * (cellSize + gap) + 20;

  let cells = '';
  for (let d = 0; d < 7; d++) {
    // Day label
    cells += `<text x="0" y="${d * (cellSize + gap) + cellSize - 2}" fill="#666" font-size="10" font-family="sans-serif">${days[d]}</text>`;
    for (let h = 0; h < 24; h++) {
      const value = hm[d * 24 + h] || 0;
      const opacity = value / 15; // Values are 0-15
      const x = labelWidth + h * (cellSize + gap);
      const y = d * (cellSize + gap);
      cells += `<rect x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" rx="2" fill="var(--accent)" opacity="${Math.max(0.1, opacity)}"/>`;
    }
  }

  // Hour labels (every 6 hours)
  const hourLabels = [0, 6, 12, 18].map(h =>
    `<text x="${labelWidth + h * (cellSize + gap) + cellSize/2}" y="${height - 5}" fill="#666" font-size="9" text-anchor="middle">${h}:00</text>`
  ).join('');

  return `<svg viewBox="0 0 ${width} ${height}" class="heatmap-svg" style="width: 100%; max-width: 380px;">
    ${cells}
    ${hourLabels}
  </svg>`;
}

function renderTimelineEvents(te: any[], tp: any[]): string {
  if (!te || te.length === 0) return '<p style="color: var(--text-muted)">No notable events</p>';

  const eventIcons: Record<number, string> = {
    0: '🔥', // peak_day
    1: '🚀', // streak_start
    2: '✅', // streak_end
    3: '🆕', // new_project
    4: '🏆', // milestone
    5: '😴', // gap_start
    6: '💪', // gap_end
  };

  const eventLabels: Record<number, string> = {
    0: 'Peak day',
    1: 'Streak started',
    2: 'Streak ended',
    3: 'New project',
    4: 'Milestone',
    5: 'Break started',
    6: 'Back at it',
  };

  // Show top 5 most interesting events
  // te is array of TimelineEvent objects: { d: day, t: type, v?: value, p?: project_idx }
  const events = te.slice(0, 5).map((e: any) => {
    const day = e.d;
    const type = e.t;
    const value = e.v;
    const projIdx = e.p;
    const icon = eventIcons[type] || '📌';
    const label = eventLabels[type] || 'Event';
    const projectName = projIdx !== undefined && projIdx >= 0 && tp[projIdx] ? tp[projIdx].n : '';
    const valueStr = value !== undefined && value > 0 ? ` (${value})` : '';
    const monthDay = dayToMonthDay(day);

    return `<div class="timeline-event">
      <span class="event-icon">${icon}</span>
      <span class="event-label">${label}${valueStr}</span>
      <span class="event-date">${monthDay}</span>
      ${projectName ? `<span class="event-project">${projectName}</span>` : ''}
    </div>`;
  }).join('');

  return events;
}

function dayToMonthDay(dayOfYear: number): string {
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  let remaining = dayOfYear;
  for (let i = 0; i < 12; i++) {
    if (remaining <= daysInMonth[i]) {
      return `${months[i]} ${remaining}`;
    }
    remaining -= daysInMonth[i];
  }
  return `Dec ${remaining}`;
}

function renderTraitBars(ts: any): string {
  const traits = [
    { key: 'ad', label: 'Delegation', low: 'Hands-on', high: 'Delegates' },
    { key: 'sp', label: 'Session Depth', low: 'Quick', high: 'Marathon' },
    { key: 'fc', label: 'Focus', low: 'Multi-project', high: 'Laser' },
    { key: 'bs', label: 'Work Style', low: 'Steady', high: 'Burst' },
    { key: 'ri', label: 'Intensity', low: 'Light', high: 'Intense' },
  ];

  return traits.map(t => {
    const value = ts[t.key] || 50;
    return `<div class="trait-bar-row">
      <div class="trait-bar-label">${t.label}</div>
      <div class="trait-bar-container">
        <div class="trait-bar-fill" style="width: ${value}%"></div>
        <div class="trait-bar-marker" style="left: ${value}%"></div>
      </div>
      <div class="trait-bar-value">${value}</div>
    </div>`;
  }).join('');
}

/**
 * Format token count with appropriate units
 */
function formatTokens(tokens: number): string {
  if (tokens >= 1000000000) return (tokens / 1000000000).toFixed(1) + 'B';
  if (tokens >= 1000000) return (tokens / 1000000).toFixed(1) + 'M';
  if (tokens >= 1000) return (tokens / 1000).toFixed(1) + 'K';
  return tokens.toString();
}

/**
 * Get model display name (shorter version)
 */
function getModelDisplayName(model: string): string {
  if (model.includes('opus')) return 'Opus';
  if (model.includes('sonnet')) return 'Sonnet';
  if (model.includes('haiku')) return 'Haiku';
  return model.split('-')[0] || model;
}

/**
 * Render streak stats card content
 */
function renderStreakStats(sk: number[]): string {
  if (!sk || sk.length < 4) return '';
  const [count, longest, current, avg] = sk;

  return `
    <div class="stats-grid">
      <div class="stat-item">
        <div class="stat-value">${count}</div>
        <div class="stat-label">streaks</div>
      </div>
      <div class="stat-item highlight">
        <div class="stat-value">${longest}</div>
        <div class="stat-label">day longest</div>
      </div>
      ${current > 0 ? `
      <div class="stat-item current">
        <div class="stat-value">${current}</div>
        <div class="stat-label">day current</div>
      </div>` : ''}
      <div class="stat-item">
        <div class="stat-value">${avg}</div>
        <div class="stat-label">day avg</div>
      </div>
    </div>
  `;
}

/**
 * Render token stats card content
 */
function renderTokenStats(tk: TokenStats): string {
  if (!tk || !tk.total) return '';

  const modelEntries = Object.entries(tk.models || {}).sort((a, b) => b[1] - a[1]);
  const topModels = modelEntries.slice(0, 3);

  return `
    <div class="token-stats">
      <div class="token-total">
        <div class="token-value">${formatTokens(tk.total)}</div>
        <div class="token-label">total tokens</div>
      </div>
      <div class="token-breakdown">
        <div class="token-row">
          <span class="token-type">Input</span>
          <span class="token-count">${formatTokens(tk.input)}</span>
        </div>
        <div class="token-row">
          <span class="token-type">Output</span>
          <span class="token-count">${formatTokens(tk.output)}</span>
        </div>
        ${tk.cache_read > 0 ? `
        <div class="token-row cache">
          <span class="token-type">Cache Read</span>
          <span class="token-count">${formatTokens(tk.cache_read)}</span>
        </div>` : ''}
      </div>
      ${topModels.length > 0 ? `
      <div class="model-breakdown">
        <div class="model-header">By Model</div>
        ${topModels.map(([model, count]) => `
          <div class="model-row">
            <span class="model-name">${getModelDisplayName(model)}</span>
            <span class="model-count">${formatTokens(count)}</span>
          </div>
        `).join('')}
      </div>` : ''}
    </div>
  `;
}

function renderHighlightCard(story: WrappedStory | WrappedStoryV3): string {
  if (isV3Story(story)) {
    // V3: Show longest session
    const longestSession = story.ls || 0;
    const hours = Math.floor(longestSession);
    const minutes = Math.round((longestSession - hours) * 60);
    const displayTime = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;

    return `<div class="card card-split">
      <div class="card-content">
        <div class="split-viz">
          <div class="viz-circle">
            <div class="viz-number">🧘</div>
            <div class="viz-label">deep work</div>
          </div>
        </div>
        <div class="split-data">
          <div class="big-number">${displayTime}</div>
          <div class="big-number-label">longest session</div>
          <p class="comparison-text" style="margin-top: 1rem">Your marathon coding session</p>
        </div>
      </div>
    </div>`;
  }

  // V2: Show concurrent instances or longest session
  const v2Story = story as WrappedStory;
  if (v2Story.ci > 1) {
    return `<div class="card card-split">
      <div class="card-content">
        <div class="split-data">
          <div class="big-number">${v2Story.ci}</div>
          <div class="big-number-label">parallel instances</div>
          <p class="comparison-text" style="margin-top: 1rem">Multitasking master!</p>
        </div>
        <div class="split-viz">
          <div class="viz-circle">
            <div class="viz-number">⚡</div>
            <div class="viz-label">power user</div>
          </div>
        </div>
      </div>
    </div>`;
  }

  return `<div class="card card-split">
    <div class="card-content">
      <div class="split-viz">
        <div class="viz-circle">
          <div class="viz-number">🧘</div>
          <div class="viz-label">focused</div>
        </div>
      </div>
      <div class="split-data">
        <div class="big-number">${v2Story.ls?.toFixed(1) || '0'}</div>
        <div class="big-number-label">hour longest session</div>
        <p class="comparison-text" style="margin-top: 1rem">Deep work champion</p>
      </div>
    </div>
  </div>`;
}

function renderCards(story: WrappedStory | WrappedStoryV3, year: number, pageUrl: string): string {
  const displayName = story.n || 'You';
  // Handle V2 (story.a) vs V3 (story.ma) monthly activity
  const monthlyActivity = isV3Story(story) ? story.ma : story.a;
  const sparkline = generateSvgSparkline(monthlyActivity || []);
  const peakMonth = getPeakMonth(monthlyActivity || []);
  const archetype = getArchetype(story);

  const cards = [
    // Card 1: Hero - Full-bleed with giant year
    `<div class="card card-hero">
      <div class="hero-year">${year}</div>
      <div class="card-content">
        <h1 class="hero-title">
          <span class="hero-name">${escapeHtml(displayName)}</span> had ${getMessageDescriptor(story.m)} year with Claude
        </h1>
        <p class="card-subtitle">Tap to unwrap your story →</p>
      </div>
    </div>`,

    // Card 2: Messages - Split layout with circle viz
    `<div class="card card-split">
      <div class="card-content">
        <div class="split-data">
          <div class="big-number">${formatNumber(story.m)}</div>
          <div class="big-number-label">messages exchanged</div>
          <p class="comparison-text" style="margin-top: 1rem">${getMessageComparison(story.m)}</p>
        </div>
        <div class="split-viz">
          <div class="viz-circle">
            <div class="viz-number">${Math.round(story.m / (story.d || 365))}</div>
            <div class="viz-label">per day</div>
          </div>
        </div>
      </div>
    </div>`,

    // Card 3: Hours - Split layout with sessions circle
    `<div class="card card-split">
      <div class="card-content">
        <div class="split-viz">
          <div class="viz-circle">
            <div class="viz-number">${story.s}</div>
            <div class="viz-label">sessions</div>
          </div>
        </div>
        <div class="split-data">
          <div class="big-number">${Math.round(story.h)}</div>
          <div class="big-number-label">hours coding</div>
          <p class="comparison-text" style="margin-top: 1rem">${getHoursComparison(story.h)}</p>
        </div>
      </div>
    </div>`,

    // Card 4: Timeline - Full-width with peak callout
    `<div class="card card-timeline">
      <div class="card-content">
        <h2 class="card-title" style="margin-bottom: 1.5rem">Your Year in Motion</h2>
        <div class="sparkline-container">
          ${sparkline}
          <div class="sparkline-labels">
            <span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span><span>May</span><span>Jun</span>
            <span>Jul</span><span>Aug</span><span>Sep</span><span>Oct</span><span>Nov</span><span>Dec</span>
          </div>
        </div>
        <div class="timeline-peak">
          <div class="timeline-peak-label">Peak Month</div>
          <div class="timeline-peak-value">${peakMonth.name} — ${formatNumber(peakMonth.value)} messages</div>
        </div>
      </div>
    </div>`,

    // V3 Card: Heatmap - When you code
    ...(isV3Story(story) ? [`<div class="card card-heatmap">
      <div class="card-content">
        <h2 class="card-title">When You Code</h2>
        <p class="card-subtitle" style="margin-bottom: 1rem">Your weekly rhythm</p>
        ${renderHeatmapSvg(story.hm)}
        <p class="heatmap-title">Activity by day and hour</p>
      </div>
    </div>`] : []),

    // V3 Card: Key Moments - Timeline events
    ...(isV3Story(story) && story.te.length > 0 ? [`<div class="card card-events">
      <div class="card-content">
        <h2 class="card-title">Key Moments</h2>
        <p class="card-subtitle">Your milestones this year</p>
        <div class="timeline-events">
          ${renderTimelineEvents(story.te, story.tp)}
        </div>
      </div>
    </div>`] : []),

    // V3 Card: Your DNA - Trait bars
    ...(isV3Story(story) ? [`<div class="card card-traits">
      <div class="card-content">
        <h2 class="card-title">Your Coding DNA</h2>
        <p class="card-subtitle">How you work with Claude</p>
        <div class="trait-bars">
          ${renderTraitBars(story.ts)}
        </div>
      </div>
    </div>`] : []),

    // Card 5: Personality - Archetype reveal with traits
    `<div class="card card-radar">
      <div class="card-content">
        <p class="card-subtitle" style="margin-bottom: 0.5rem">You are a</p>
        <h2 class="card-title" style="margin-bottom: 0">${archetype}</h2>
        ${isV3Story(story)
          ? `<div class="traits-list" style="margin-top: 2rem">
              ${['ad', 'sp', 'fc', 'ri'].map(t => {
                const score = (story.ts as any)[t] || 50;
                return `<span class="trait-badge">${getTraitDescription(t, score)}</span>`;
              }).join('')}
            </div>`
          : `<div class="archetype-badge">${story.c} • ${story.w}</div>
            <div class="traits-list" style="margin-top: 2rem">
              ${story.t.map(trait => `<span class="trait-badge">${escapeHtml(trait)}</span>`).join('')}
            </div>`
        }
      </div>
    </div>`,

    // Card 6: Projects - Grid of mini-cards
    `<div class="card card-grid">
      <div class="card-content">
        <h2 class="card-title">Your Top Projects</h2>
        <div class="project-cards">
          ${story.tp.slice(0, 3).map((proj: any, i: number) => `
            <div class="project-card">
              <div class="project-card-rank">#${i + 1}</div>
              <div class="project-card-name" title="${escapeHtml(proj.n)}">${escapeHtml(proj.n)}</div>
              <div class="project-card-stat">${formatNumber(proj.m)} msgs</div>
              <div class="project-card-stat">${proj.d} days</div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>`,

    // Card 7: Highlight stat (longest session)
    renderHighlightCard(story),

    // V3 Card: Streaks
    ...(isV3Story(story) && story.sk && story.sk[0] > 0 ? [`<div class="card">
      <div class="card-content">
        <div class="card-emoji">🔥</div>
        <h2 class="card-title">Your Streaks</h2>
        <p class="card-subtitle">Consecutive days of coding</p>
        ${renderStreakStats(story.sk)}
      </div>
    </div>`] : []),

    // V3 Card: Token Usage
    ...(isV3Story(story) && story.tk && story.tk.total > 0 ? [`<div class="card">
      <div class="card-content">
        <h2 class="card-title">Token Usage</h2>
        <p class="card-subtitle">Your AI compute footprint</p>
        ${renderTokenStats(story.tk)}
      </div>
    </div>`] : []),

    // Final Card: Polaroid summary
    `<div class="card card-polaroid">
      <div class="card-content">
        <div class="polaroid-frame">
          <div class="polaroid-inner">
            <div class="polaroid-stat">
              <div class="polaroid-stat-value">${formatNumber(story.m)}</div>
              <div class="polaroid-stat-label">messages</div>
            </div>
            <div class="polaroid-stat">
              <div class="polaroid-stat-value">${story.p}</div>
              <div class="polaroid-stat-label">projects</div>
            </div>
            <div class="polaroid-stat">
              <div class="polaroid-stat-value">${Math.round(story.h)}</div>
              <div class="polaroid-stat-label">hours</div>
            </div>
          </div>
          <div class="polaroid-caption">
            <span class="polaroid-year">${year}</span> • ${escapeHtml(displayName)}
          </div>
        </div>
        <div class="share-buttons">
          <a href="https://twitter.com/intent/tweet?text=${encodeURIComponent(`My Claude Code Wrapped ${year}: ${formatNumber(story.m)} messages across ${story.p} projects! 🎁`)}&url=${encodeURIComponent(pageUrl)}" target="_blank" rel="noopener" class="share-btn twitter">
            𝕏 Share
          </a>
          <a href="https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(pageUrl)}" target="_blank" rel="noopener" class="share-btn linkedin">
            in Share
          </a>
          <button class="share-btn copy" onclick="copyUrl()">📋 Copy URL</button>
        </div>
      </div>
    </div>`,
  ];

  return cards.join('');
}

export function renderErrorPage(error: string, year?: number): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Error - Claude Code Wrapped</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Source Sans 3', -apple-system, sans-serif;
      background: #0a0a0a;
      color: #fff;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      text-align: center;
    }
    .error-container { max-width: 400px; }
    .error-emoji { font-size: 4rem; margin-bottom: 1rem; }
    h1 { font-family: 'Space Grotesk', sans-serif; font-size: 1.5rem; margin-bottom: 0.5rem; }
    p { color: #a0a0a0; margin-bottom: 2rem; }
    a {
      color: #d4a574;
      text-decoration: none;
    }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="error-container">
    <div class="error-emoji">😕</div>
    <h1>Something went wrong</h1>
    <p>${error}</p>
    <a href="/">← Back to home</a>
  </div>
</body>
</html>`;
}
