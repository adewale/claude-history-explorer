/**
 * Bento view - Dense grid layout showing all stats at once
 */

import { WrappedStoryV3, formatNumber, getTraitDescription, TokenStats } from '../decoder';

function escapeHtml(str: string): string {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000000000) return (tokens / 1000000000).toFixed(1) + 'B';
  if (tokens >= 1000000) return (tokens / 1000000).toFixed(1) + 'M';
  if (tokens >= 1000) return (tokens / 1000).toFixed(1) + 'K';
  return tokens.toString();
}

function getModelDisplayName(model: string): string {
  if (model.includes('opus')) return 'Opus';
  if (model.includes('sonnet')) return 'Sonnet';
  if (model.includes('haiku')) return 'Haiku';
  return model.split('-')[0] || model;
}

function renderHeatmapSvg(hm: number[]): string {
  if (!hm || hm.length !== 168) return '';

  const days = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
  const cellSize = 8;
  const gap = 1;
  const labelWidth = 12;
  const width = labelWidth + 24 * (cellSize + gap);
  const height = 7 * (cellSize + gap) + 14;

  let cells = '';
  for (let d = 0; d < 7; d++) {
    cells += `<text x="0" y="${d * (cellSize + gap) + cellSize - 1}" fill="#666" font-size="7" font-family="sans-serif">${days[d]}</text>`;
    for (let h = 0; h < 24; h++) {
      const value = hm[d * 24 + h] || 0;
      const opacity = value / 15;
      const x = labelWidth + h * (cellSize + gap);
      const y = d * (cellSize + gap);
      cells += `<rect x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" rx="1" fill="#d4a574" opacity="${Math.max(0.1, opacity)}"/>`;
    }
  }

  const hourLabels = [0, 6, 12, 18].map(h =>
    `<text x="${labelWidth + h * (cellSize + gap) + cellSize/2}" y="${height - 2}" fill="#666" font-size="6" text-anchor="middle">${h}</text>`
  ).join('');

  return `<svg viewBox="0 0 ${width} ${height}" style="width: 100%; max-width: 240px;">
    ${cells}
    ${hourLabels}
  </svg>`;
}

function renderSparkline(data: number[]): string {
  if (!data || data.length === 0) return '';
  const width = 120;
  const height = 30;
  const max = Math.max(...data, 1);
  const barWidth = (width / data.length) - 1;

  const bars = data.map((val, i) => {
    const barHeight = Math.max((val / max) * height, 1);
    const x = i * (barWidth + 1);
    const y = height - barHeight;
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" fill="#d4a574"/>`;
  }).join('');

  return `<svg viewBox="0 0 ${width} ${height}" style="width: 100%; max-width: 120px; height: 30px;">
    ${bars}
  </svg>`;
}

interface RenderOptions {
  story: WrappedStoryV3;
  year: number;
  encodedData: string;
}

export function renderBentoPage({ story, year, encodedData }: RenderOptions): string {
  const displayName = story.n || 'Developer';
  const monthlyActivity = story.ma;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${displayName}'s Claude Code Wrapped ${year} - Bento</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Source+Sans+3:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
      --bg-dark: #0a0a0a;
      --bg-card: #141414;
      --text-primary: #ffffff;
      --text-secondary: #a0a0a0;
      --text-muted: #666666;
      --accent: #d4a574;
      --accent-light: #e5c9a8;
      --border: #2a2a2a;
      --font-display: 'Space Grotesk', sans-serif;
      --font-body: 'Source Sans 3', sans-serif;
    }

    body {
      font-family: var(--font-body);
      background: var(--bg-dark);
      color: var(--text-primary);
      min-height: 100vh;
      padding: 1rem;
    }

    .header {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border);
    }

    .header h1 {
      font-family: var(--font-display);
      font-size: 1.25rem;
      font-weight: 600;
    }

    .header .year {
      color: var(--accent);
    }

    .view-links {
      display: flex;
      gap: 0.5rem;
    }

    .view-links a {
      padding: 0.4rem 0.8rem;
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 4px;
      color: var(--text-secondary);
      text-decoration: none;
      font-size: 0.8rem;
    }

    .view-links a:hover {
      color: var(--text-primary);
    }

    .view-links a.active {
      background: var(--accent);
      color: var(--bg-dark);
      border-color: var(--accent);
    }

    @media (max-width: 480px) {
      .header {
        flex-direction: column;
        align-items: flex-start;
      }

      .header h1 {
        font-size: 1rem;
      }
    }

    .bento-grid {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 0.75rem;
      max-width: 1400px;
      margin: 0 auto;
    }

    .bento-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
    }

    /* Card sizes */
    .span-3 { grid-column: span 3; }
    .span-4 { grid-column: span 4; }
    .span-6 { grid-column: span 6; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }

    .card-label {
      font-size: 0.7rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.5rem;
    }

    .card-value {
      font-family: var(--font-display);
      font-size: 2rem;
      font-weight: 700;
      color: var(--accent);
      line-height: 1;
    }

    .card-value.small {
      font-size: 1.5rem;
    }

    .card-subtext {
      font-size: 0.8rem;
      color: var(--text-secondary);
      margin-top: 0.25rem;
    }

    .project-list {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .project-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--border);
    }

    .project-item:last-child {
      border-bottom: none;
    }

    .project-name {
      font-weight: 500;
      font-size: 0.85rem;
    }

    .project-stats {
      font-size: 0.75rem;
      color: var(--text-muted);
    }

    .trait-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.4rem;
    }

    .trait-label {
      width: 70px;
      font-size: 0.7rem;
      color: var(--text-secondary);
    }

    .trait-bar {
      flex: 1;
      height: 6px;
      background: var(--border);
      border-radius: 3px;
      overflow: hidden;
    }

    .trait-fill {
      height: 100%;
      background: var(--accent);
      border-radius: 3px;
    }

    .trait-value {
      width: 24px;
      font-size: 0.7rem;
      color: var(--accent);
      text-align: right;
    }

    .token-row {
      display: flex;
      justify-content: space-between;
      font-size: 0.8rem;
      padding: 0.25rem 0;
    }

    .token-type {
      color: var(--text-secondary);
    }

    .token-count {
      color: var(--text-primary);
      font-family: var(--font-display);
    }

    .streak-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.5rem;
    }

    .streak-item {
      text-align: center;
      padding: 0.5rem;
      background: var(--bg-dark);
      border-radius: 6px;
    }

    .streak-value {
      font-family: var(--font-display);
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--accent);
    }

    .streak-label {
      font-size: 0.65rem;
      color: var(--text-muted);
      text-transform: uppercase;
    }

    @media (max-width: 900px) {
      .span-3 { grid-column: span 6; }
      .span-4 { grid-column: span 6; }
      .span-6 { grid-column: span 12; }
      .span-8 { grid-column: span 12; }
    }

    @media (max-width: 600px) {
      .span-3, .span-4, .span-6, .span-8 { grid-column: span 12; }
      .bento-grid { gap: 0.5rem; }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1><span class="year">${year}</span> ${escapeHtml(displayName)}'s Claude Code Wrapped</h1>
    <div class="view-links">
      <a href="?d=${encodedData}" class="active">Bento</a>
      <a href="?view=print&d=${encodedData}">Print</a>
    </div>
  </div>

  <div class="bento-grid">
    <!-- Messages -->
    <div class="bento-card span-3">
      <div class="card-label">Messages</div>
      <div class="card-value">${formatNumber(story.m)}</div>
      <div class="card-subtext">${Math.round(story.m / (story.d || 365))}/day</div>
    </div>

    <!-- Hours -->
    <div class="bento-card span-3">
      <div class="card-label">Hours</div>
      <div class="card-value">${Math.round(story.h)}</div>
      <div class="card-subtext">${story.s} sessions</div>
    </div>

    <!-- Projects -->
    <div class="bento-card span-3">
      <div class="card-label">Projects</div>
      <div class="card-value">${story.p}</div>
      <div class="card-subtext">${story.d} days active</div>
    </div>

    <!-- Longest Session -->
    <div class="bento-card span-3">
      <div class="card-label">Longest Session</div>
      <div class="card-value small">${story.ls.toFixed(1)}h</div>
    </div>

    <!-- Monthly Activity -->
    <div class="bento-card span-6">
      <div class="card-label">Monthly Activity</div>
      <div style="display: flex; align-items: center; gap: 1rem; margin-top: 0.5rem;">
        ${renderSparkline(monthlyActivity || [])}
        <div style="display: flex; gap: 0.5rem; font-size: 0.65rem; color: var(--text-muted);">
          <span>J</span><span>F</span><span>M</span><span>A</span><span>M</span><span>J</span>
          <span>J</span><span>A</span><span>S</span><span>O</span><span>N</span><span>D</span>
        </div>
      </div>
    </div>

    <!-- Heatmap -->
    <div class="bento-card span-6">
      <div class="card-label">Activity Heatmap</div>
      <div style="margin-top: 0.5rem;">
        ${renderHeatmapSvg(story.hm)}
      </div>
    </div>

    <!-- Top Projects -->
    <div class="bento-card span-4">
      <div class="card-label">Top Projects</div>
      <div class="project-list">
        ${story.tp.slice(0, 5).map((p: any, i: number) => `
          <div class="project-item">
            <span class="project-name">${i + 1}. ${escapeHtml(p.n)}</span>
            <span class="project-stats">${formatNumber(p.m)} msgs</span>
          </div>
        `).join('')}
      </div>
    </div>

    <!-- Traits -->
    <div class="bento-card span-4">
      <div class="card-label">Coding Style</div>
      <div style="margin-top: 0.5rem;">
        ${['ad', 'sp', 'fc', 'bs', 'ri'].map(t => {
          const value = (story.ts as any)[t] || 50;
          const labels: Record<string, string> = { ad: 'Delegation', sp: 'Deep Work', fc: 'Focus', bs: 'Burst', ri: 'Intensity' };
          return `
            <div class="trait-row">
              <span class="trait-label">${labels[t]}</span>
              <div class="trait-bar"><div class="trait-fill" style="width: ${value}%"></div></div>
              <span class="trait-value">${value}</span>
            </div>
          `;
        }).join('')}
      </div>
    </div>

    <!-- Token Stats -->
    ${story.tk?.total > 0 ? `
    <div class="bento-card span-4">
      <div class="card-label">Token Usage</div>
      <div class="card-value small" style="margin-bottom: 0.5rem;">${formatTokens(story.tk.total)}</div>
      <div class="token-row">
        <span class="token-type">Input</span>
        <span class="token-count">${formatTokens(story.tk.input)}</span>
      </div>
      <div class="token-row">
        <span class="token-type">Output</span>
        <span class="token-count">${formatTokens(story.tk.output)}</span>
      </div>
      ${Object.entries(story.tk.models || {}).slice(0, 3).map(([model, count]) => `
        <div class="token-row">
          <span class="token-type">${getModelDisplayName(model)}</span>
          <span class="token-count">${formatTokens(count as number)}</span>
        </div>
      `).join('')}
    </div>
    ` : ''}

    <!-- Streaks -->
    ${story.sk?.[0] > 0 ? `
    <div class="bento-card span-4">
      <div class="card-label">Streaks</div>
      <div class="streak-grid">
        <div class="streak-item">
          <div class="streak-value">${story.sk[0]}</div>
          <div class="streak-label">Total</div>
        </div>
        <div class="streak-item">
          <div class="streak-value">${story.sk[1]}</div>
          <div class="streak-label">Longest</div>
        </div>
        <div class="streak-item">
          <div class="streak-value">${story.sk[2]}</div>
          <div class="streak-label">Current</div>
        </div>
        <div class="streak-item">
          <div class="streak-value">${story.sk[3]}</div>
          <div class="streak-label">Avg Days</div>
        </div>
      </div>
    </div>
    ` : ''}
  </div>
</body>
</html>`;
}

export function renderErrorPage(error: string): string {
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
    a { color: #d4a574; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="error-container">
    <div class="error-emoji">😕</div>
    <h1>Something went wrong</h1>
    <p>${escapeHtml(error)}</p>
    <a href="/">← Back to home</a>
  </div>
</body>
</html>`;
}
