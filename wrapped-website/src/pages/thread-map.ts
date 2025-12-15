/**
 * Thread Map visualization page
 */

import { ThreadMap, ThreadNode } from '../decoder';
import { escapeHtml, formatNumber, formatTimestamp, formatDurationMinutes } from '../utils';

/**
 * Format duration from timestamps to readable string
 */
function formatDuration(startTs: number, endTs: number): string {
  if (!startTs || !endTs) return '?';
  const minutes = Math.round((endTs - startTs) / 60);
  return formatDurationMinutes(minutes);
}

/**
 * Calculate the time range for the visualization
 */
function getTimeRange(map: ThreadMap): { start: number; end: number; days: number } {
  const start = map.timespan[0];
  const end = map.timespan[1];
  const days = Math.max(1, Math.round((end - start) / 86400));
  return { start, end, days };
}

/**
 * Get pattern badge HTML
 */
function getPatternBadges(patterns: string[]): string {
  const patternInfo: Record<string, { icon: string; label: string; color: string }> = {
    'hub-and-spoke': { icon: '⚡', label: 'Hub', color: '#f59e0b' },
    'chain': { icon: '→', label: 'Chain', color: '#3b82f6' },
    'parallel': { icon: '∥', label: 'Parallel', color: '#8b5cf6' },
    'deep': { icon: '↓', label: 'Deep', color: '#10b981' },
  };

  return patterns.map(p => {
    const info = patternInfo[p] || { icon: '?', label: p, color: '#666' };
    return `<span class="pattern-badge" style="--badge-color: ${info.color}">${info.icon} ${info.label}</span>`;
  }).join('');
}

/**
 * Generate SVG for timeline visualization
 */
function generateTimelineSvg(map: ThreadMap): string {
  const { start, end } = getTimeRange(map);
  const totalDuration = end - start;
  if (totalDuration <= 0) return '<p class="empty-message">No timeline data available.</p>';

  // Handle empty roots case
  if (map.roots.length === 0 && map.orphans.length === 0) {
    return '<p class="empty-message">No sessions found in the data.</p>';
  }

  const width = 800;
  const height = Math.max(400, (map.roots.length + map.orphans.length) * 80 + 100);
  const padding = { top: 40, right: 20, bottom: 40, left: 20 };
  const usableWidth = width - padding.left - padding.right;

  // Calculate x position from timestamp
  const getX = (ts: number) => {
    const pct = (ts - start) / totalDuration;
    return padding.left + pct * usableWidth;
  };

  // Calculate bar width from duration
  const getBarWidth = (startTs: number, endTs: number) => {
    const duration = (endTs - startTs) / totalDuration;
    return Math.max(4, duration * usableWidth);
  };

  let elements: string[] = [];
  let yPos = padding.top + 30;

  // Render each root and its children
  map.roots.forEach((root) => {
    const rootX = getX(root.start);
    const rootWidth = getBarWidth(root.start, root.end || root.start + 3600);
    const barHeight = 24;
    const childBarHeight = 18;

    // Root session bar
    elements.push(`
      <g class="session-group" data-id="${escapeHtml(root.id)}">
        <rect
          x="${rootX}"
          y="${yPos}"
          width="${rootWidth}"
          height="${barHeight}"
          rx="4"
          class="session-bar main-session"
          fill="url(#mainGradient)"
        />
        <text x="${rootX + 8}" y="${yPos + 16}" class="session-label">${escapeHtml(root.slug || root.id)}</text>
        <text x="${rootX + rootWidth + 8}" y="${yPos + 16}" class="session-meta">${root.messages} msgs</text>
      </g>
    `);

    // Hub indicator
    if (root.children.length >= 3) {
      elements.push(`
        <text x="${rootX - 12}" y="${yPos + 17}" class="hub-indicator">⚡</text>
      `);
    }

    yPos += barHeight + 8;

    // Child sessions (agents)
    root.children.forEach((child) => {
      const childX = getX(child.start);
      const childWidth = getBarWidth(child.start, child.end || child.start + 1800);

      // Connector line
      elements.push(`
        <line
          x1="${rootX + 10}"
          y1="${yPos - 4}"
          x2="${childX}"
          y2="${yPos + childBarHeight / 2}"
          class="connector-line"
        />
      `);

      // Child bar
      elements.push(`
        <g class="session-group" data-id="${escapeHtml(child.id)}">
          <rect
            x="${childX}"
            y="${yPos}"
            width="${childWidth}"
            height="${childBarHeight}"
            rx="3"
            class="session-bar agent-session"
            fill="url(#agentGradient)"
          />
          <text x="${childX + 6}" y="${yPos + 13}" class="session-label small">${escapeHtml(child.slug || child.id)}</text>
        </g>
      `);

      yPos += childBarHeight + 4;

      // Nested children (depth 2+)
      if (child.children.length > 0) {
        child.children.forEach(nested => {
          const nestedX = getX(nested.start);
          const nestedWidth = getBarWidth(nested.start, nested.end || nested.start + 900);

          elements.push(`
            <line
              x1="${childX + 8}"
              y1="${yPos - 2}"
              x2="${nestedX}"
              y2="${yPos + 12}"
              class="connector-line nested"
            />
          `);

          elements.push(`
            <rect
              x="${nestedX}"
              y="${yPos}"
              width="${nestedWidth}"
              height="14"
              rx="2"
              class="session-bar nested-session"
              fill="url(#nestedGradient)"
            />
          `);

          yPos += 18;
        });
      }
    });

    yPos += 20; // Gap between root sessions
  });

  // Orphan agents
  if (map.orphans.length > 0) {
    yPos += 10;
    elements.push(`
      <text x="${padding.left}" y="${yPos}" class="orphan-label">Orphan agents</text>
    `);
    yPos += 20;

    map.orphans.forEach(orphan => {
      const orphanX = getX(orphan.start);
      const orphanWidth = getBarWidth(orphan.start, orphan.end || orphan.start + 1800);

      elements.push(`
        <rect
          x="${orphanX}"
          y="${yPos}"
          width="${orphanWidth}"
          height="16"
          rx="3"
          class="session-bar orphan-session"
          fill="url(#orphanGradient)"
        />
      `);
      yPos += 20;
    });
  }

  // Time axis
  const numTicks = Math.max(1, Math.min(8, Math.ceil((end - start) / 86400)));
  const tickInterval = totalDuration / numTicks;
  const axisY = yPos + 20;

  elements.push(`<line x1="${padding.left}" y1="${axisY}" x2="${width - padding.right}" y2="${axisY}" class="axis-line"/>`);

  for (let i = 0; i <= numTicks; i++) {
    const tickTime = start + i * tickInterval;
    const tickX = getX(tickTime);
    elements.push(`
      <line x1="${tickX}" y1="${axisY - 4}" x2="${tickX}" y2="${axisY + 4}" class="axis-tick"/>
      <text x="${tickX}" y="${axisY + 20}" class="axis-label">${formatTimestamp(tickTime)}</text>
    `);
  }

  const svgHeight = axisY + 40;

  return `
    <svg viewBox="0 0 ${width} ${svgHeight}" class="thread-map-svg">
      <defs>
        <linearGradient id="mainGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#d4a574"/>
          <stop offset="100%" stop-color="#c49464"/>
        </linearGradient>
        <linearGradient id="agentGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#6b7280"/>
          <stop offset="100%" stop-color="#4b5563"/>
        </linearGradient>
        <linearGradient id="nestedGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#4b5563"/>
          <stop offset="100%" stop-color="#374151"/>
        </linearGradient>
        <linearGradient id="orphanGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#9ca3af"/>
          <stop offset="100%" stop-color="#6b7280"/>
        </linearGradient>
      </defs>
      ${elements.join('')}
    </svg>
  `;
}

interface RenderOptions {
  map: ThreadMap;
  encodedData: string;
}

export function renderThreadMapPage({ map, encodedData }: RenderOptions): string {
  const pageUrl = `https://wrapped-claude-codes.adewale-883.workers.dev/thread-map?d=${encodedData}`;
  const { days } = getTimeRange(map);
  const stats = map.stats;
  const timelineSvg = generateTimelineSvg(map);

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Thread Map: ${escapeHtml(map.project)}</title>
  <meta name="description" content="Thread Map visualization for ${escapeHtml(map.project)}: ${stats.mainSessions} main sessions, ${stats.agentSessions} agents">

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Source+Sans+3:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
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
      --main-color: #d4a574;
      --agent-color: #6b7280;
      --font-display: 'Space Grotesk', -apple-system, sans-serif;
      --font-body: 'Source Sans 3', -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }

    body {
      font-family: var(--font-body);
      background: var(--bg-dark);
      color: var(--text-primary);
      min-height: 100vh;
      padding: 2rem;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
    }

    /* Header */
    .header {
      margin-bottom: 2rem;
    }

    .header-top {
      display: flex;
      align-items: center;
      gap: 1rem;
      margin-bottom: 0.5rem;
    }

    .header-icon {
      font-size: 2rem;
    }

    .header-title {
      font-family: var(--font-display);
      font-size: 2rem;
      font-weight: 700;
    }

    .header-project {
      color: var(--accent);
    }

    .header-meta {
      color: var(--text-secondary);
      font-size: 0.95rem;
    }

    /* Stats Bar */
    .stats-bar {
      display: flex;
      flex-wrap: wrap;
      gap: 1.5rem;
      padding: 1.25rem;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin-bottom: 2rem;
    }

    .stat-item {
      display: flex;
      flex-direction: column;
    }

    .stat-value {
      font-family: var(--font-display);
      font-size: 1.5rem;
      font-weight: 600;
      color: var(--accent);
    }

    .stat-label {
      font-size: 0.75rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    /* Patterns */
    .patterns-row {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1.5rem;
    }

    .patterns-label {
      font-size: 0.85rem;
      color: var(--text-muted);
    }

    .pattern-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.35rem 0.75rem;
      background: color-mix(in srgb, var(--badge-color) 20%, transparent);
      border: 1px solid var(--badge-color);
      border-radius: 20px;
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--badge-color);
    }

    /* Timeline Container */
    .timeline-container {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      overflow-x: auto;
    }

    .timeline-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }

    .timeline-title {
      font-family: var(--font-display);
      font-size: 1.1rem;
      font-weight: 600;
    }

    .timeline-legend {
      display: flex;
      gap: 1rem;
      font-size: 0.8rem;
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      color: var(--text-secondary);
    }

    .legend-dot {
      width: 12px;
      height: 12px;
      border-radius: 3px;
    }

    .legend-dot.main { background: var(--main-color); }
    .legend-dot.agent { background: var(--agent-color); }

    /* SVG Styles */
    .thread-map-svg {
      width: 100%;
      min-width: 600px;
      height: auto;
    }

    .session-bar {
      cursor: pointer;
      transition: opacity 0.2s;
    }

    .session-bar:hover {
      opacity: 0.8;
    }

    .session-label {
      font-family: var(--font-mono);
      font-size: 10px;
      fill: var(--text-primary);
      pointer-events: none;
    }

    .session-label.small {
      font-size: 9px;
    }

    .session-meta {
      font-family: var(--font-mono);
      font-size: 9px;
      fill: var(--text-muted);
    }

    .connector-line {
      stroke: var(--border);
      stroke-width: 1;
      stroke-dasharray: 3 2;
    }

    .connector-line.nested {
      stroke-dasharray: 2 2;
      opacity: 0.6;
    }

    .hub-indicator {
      font-size: 12px;
      fill: #f59e0b;
    }

    .orphan-label {
      font-family: var(--font-display);
      font-size: 11px;
      fill: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .empty-message {
      color: var(--text-muted);
      font-style: italic;
      text-align: center;
      padding: 3rem 1rem;
    }

    .axis-line {
      stroke: var(--border);
      stroke-width: 1;
    }

    .axis-tick {
      stroke: var(--text-muted);
      stroke-width: 1;
    }

    .axis-label {
      font-family: var(--font-mono);
      font-size: 10px;
      fill: var(--text-muted);
      text-anchor: middle;
    }

    /* Footer */
    .footer {
      margin-top: 2rem;
      padding-top: 1.5rem;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }

    .share-btn {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.6rem 1.25rem;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text-primary);
      font-size: 0.9rem;
      cursor: pointer;
      transition: all 0.2s;
    }

    .share-btn:hover {
      background: var(--bg-card-hover);
      border-color: var(--accent);
    }

    .privacy-note {
      font-size: 0.75rem;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }

    /* Mobile */
    @media (max-width: 640px) {
      body {
        padding: 1rem;
      }

      .header-title {
        font-size: 1.5rem;
      }

      .stats-bar {
        gap: 1rem;
      }

      .stat-value {
        font-size: 1.25rem;
      }

      .timeline-container {
        padding: 1rem;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <div class="header">
      <div class="header-top">
        <span class="header-icon">🗺️</span>
        <h1 class="header-title">Thread Map: <span class="header-project">${escapeHtml(map.project)}</span></h1>
      </div>
      <p class="header-meta">${formatTimestamp(map.timespan[0], 'long')} → ${formatTimestamp(map.timespan[1], 'long')} (${days} days)</p>
    </div>

    <!-- Stats Bar -->
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-value">${stats.mainSessions}</span>
        <span class="stat-label">Main Sessions</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">${stats.agentSessions}</span>
        <span class="stat-label">Agents</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">${formatNumber(stats.totalMessages)}</span>
        <span class="stat-label">Messages</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">${stats.totalHours.toFixed(1)}</span>
        <span class="stat-label">Hours</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">${stats.avgAgentsPerMain.toFixed(1)}</span>
        <span class="stat-label">Avg Agents/Main</span>
      </div>
      ${stats.maxConcurrent > 1 ? `
      <div class="stat-item">
        <span class="stat-value">${stats.maxConcurrent}</span>
        <span class="stat-label">Max Concurrent</span>
      </div>
      ` : ''}
    </div>

    <!-- Patterns -->
    ${map.patterns.length > 0 ? `
    <div class="patterns-row">
      <span class="patterns-label">Detected patterns:</span>
      ${getPatternBadges(map.patterns)}
    </div>
    ` : ''}

    <!-- Timeline -->
    <div class="timeline-container">
      <div class="timeline-header">
        <span class="timeline-title">Session Timeline</span>
        <div class="timeline-legend">
          <div class="legend-item">
            <div class="legend-dot main"></div>
            <span>Main</span>
          </div>
          <div class="legend-item">
            <div class="legend-dot agent"></div>
            <span>Agent</span>
          </div>
        </div>
      </div>
      ${timelineSvg}
    </div>

    <!-- Footer -->
    <div class="footer">
      <div class="privacy-note">
        🔒 All data encoded in URL — nothing stored on server
      </div>
      <button class="share-btn" onclick="copyUrl()">
        📋 Copy URL
      </button>
    </div>
  </div>

  <script>
    function copyUrl() {
      navigator.clipboard.writeText('${pageUrl}');
      const btn = document.querySelector('.share-btn');
      btn.textContent = '✓ Copied!';
      setTimeout(() => {
        btn.innerHTML = '📋 Copy URL';
      }, 2000);
    }
  </script>
</body>
</html>`;
}

export function renderThreadMapErrorPage(error: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Error - Thread Map</title>
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
    a { color: #d4a574; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="error-container">
    <div class="error-emoji">🗺️</div>
    <h1>Thread Map Error</h1>
    <p>${error}</p>
    <a href="/">← Back to home</a>
  </div>
</body>
</html>`;
}
