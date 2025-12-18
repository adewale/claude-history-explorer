/**
 * Print view - Clean, print-friendly single page layout
 * Tufte-inspired with high information density
 */

import { WrappedStory, WrappedStoryV3, formatNumber, isV3Story, getTraitDescription, TokenStats } from '../decoder';

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

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const cellSize = 10;
  const gap = 2;
  const labelWidth = 28;
  const width = labelWidth + 24 * (cellSize + gap);
  const height = 7 * (cellSize + gap) + 16;

  let cells = '';
  for (let d = 0; d < 7; d++) {
    cells += `<text x="0" y="${d * (cellSize + gap) + cellSize - 1}" fill="#333" font-size="8" font-family="sans-serif">${days[d]}</text>`;
    for (let h = 0; h < 24; h++) {
      const value = hm[d * 24 + h] || 0;
      const opacity = value / 15;
      const x = labelWidth + h * (cellSize + gap);
      const y = d * (cellSize + gap);
      cells += `<rect x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" rx="1" fill="#333" opacity="${Math.max(0.05, opacity)}"/>`;
    }
  }

  const hourLabels = [0, 6, 12, 18, 23].map(h =>
    `<text x="${labelWidth + h * (cellSize + gap) + cellSize/2}" y="${height - 3}" fill="#666" font-size="7" text-anchor="middle">${h}</text>`
  ).join('');

  return `<svg viewBox="0 0 ${width} ${height}" style="width: 100%; max-width: 320px;">
    ${cells}
    ${hourLabels}
  </svg>`;
}

function renderSparkline(data: number[]): string {
  if (!data || data.length === 0) return '';
  const width = 200;
  const height = 40;
  const max = Math.max(...data, 1);
  const barWidth = (width / data.length) - 2;

  const bars = data.map((val, i) => {
    const barHeight = Math.max((val / max) * height, 1);
    const x = i * (barWidth + 2);
    const y = height - barHeight;
    return `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" fill="#333"/>`;
  }).join('');

  return `<svg viewBox="0 0 ${width} ${height}" style="width: 100%; max-width: 200px; height: 40px;">
    ${bars}
  </svg>`;
}

interface RenderOptions {
  story: WrappedStory | WrappedStoryV3;
  year: number;
  encodedData: string;
}

export function renderPrintPage({ story, year, encodedData }: RenderOptions): string {
  const displayName = story.n || 'Developer';
  const monthlyActivity = isV3Story(story) ? story.ma : story.a;
  const isV3 = isV3Story(story);

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${displayName}'s Claude Code Wrapped ${year} - Print</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }

    :root {
      --text: #1a1a1a;
      --text-light: #666;
      --border: #ddd;
    }

    @page {
      size: A4;
      margin: 1.5cm;
    }

    body {
      font-family: 'Georgia', serif;
      color: var(--text);
      background: white;
      max-width: 800px;
      margin: 0 auto;
      padding: 2rem;
      font-size: 11pt;
      line-height: 1.5;
    }

    @media print {
      body { padding: 0; }
      .no-print { display: none !important; }
    }

    .header {
      border-bottom: 2px solid var(--text);
      padding-bottom: 1rem;
      margin-bottom: 1.5rem;
    }

    .header h1 {
      font-size: 1.75rem;
      font-weight: normal;
      margin-bottom: 0.25rem;
    }

    .header .subtitle {
      color: var(--text-light);
      font-style: italic;
    }

    .view-links {
      display: flex;
      gap: 1rem;
      margin-top: 1rem;
    }

    .view-links a {
      color: var(--text-light);
      text-decoration: none;
      font-size: 0.9rem;
    }

    .view-links a:hover {
      color: var(--text);
    }

    .view-links a.active {
      color: var(--text);
      font-weight: bold;
    }

    .summary {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1.5rem;
      margin-bottom: 2rem;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid var(--border);
    }

    .summary-item {
      text-align: center;
    }

    .summary-value {
      font-size: 2rem;
      font-weight: bold;
      line-height: 1;
    }

    .summary-label {
      font-size: 0.8rem;
      color: var(--text-light);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .section {
      margin-bottom: 1.5rem;
    }

    .section-title {
      font-size: 0.9rem;
      font-weight: bold;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--text-light);
      margin-bottom: 0.75rem;
      border-bottom: 1px solid var(--border);
      padding-bottom: 0.25rem;
    }

    .two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 2rem;
    }

    .three-col {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 1.5rem;
    }

    .project-table {
      width: 100%;
      border-collapse: collapse;
    }

    .project-table th,
    .project-table td {
      text-align: left;
      padding: 0.35rem 0;
      border-bottom: 1px solid var(--border);
      font-size: 0.9rem;
    }

    .project-table th {
      font-weight: normal;
      color: var(--text-light);
      font-size: 0.75rem;
      text-transform: uppercase;
    }

    .project-table td:last-child {
      text-align: right;
    }

    .trait-list {
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }

    .trait-row {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }

    .trait-name {
      width: 80px;
      font-size: 0.85rem;
    }

    .trait-bar-bg {
      flex: 1;
      height: 8px;
      background: #eee;
      border-radius: 4px;
    }

    .trait-bar-fill {
      height: 100%;
      background: #333;
      border-radius: 4px;
    }

    .trait-value {
      width: 24px;
      text-align: right;
      font-size: 0.8rem;
      color: var(--text-light);
    }

    .token-table {
      width: 100%;
    }

    .token-table td {
      padding: 0.25rem 0;
      font-size: 0.9rem;
    }

    .token-table td:last-child {
      text-align: right;
      font-weight: bold;
    }

    .streak-row {
      display: flex;
      justify-content: space-between;
      font-size: 0.9rem;
      padding: 0.25rem 0;
    }

    .months-label {
      display: flex;
      justify-content: space-between;
      font-size: 0.7rem;
      color: var(--text-light);
      margin-top: 0.25rem;
      max-width: 200px;
    }

    .footer {
      margin-top: 2rem;
      padding-top: 1rem;
      border-top: 1px solid var(--border);
      font-size: 0.8rem;
      color: var(--text-light);
      text-align: center;
    }

    /* Mobile responsiveness */
    @media (max-width: 600px) {
      body {
        padding: 1rem;
        font-size: 10pt;
      }

      .header h1 {
        font-size: 1.25rem;
      }

      .summary {
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
      }

      .summary-value {
        font-size: 1.5rem;
      }

      .two-col {
        grid-template-columns: 1fr;
        gap: 1rem;
      }

      .trait-name {
        width: 70px;
        font-size: 0.8rem;
      }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>Claude Code Wrapped ${year}</h1>
    <div class="subtitle">${escapeHtml(displayName)}'s Year in Review</div>
    <div class="view-links no-print">
      <a href="?d=${encodedData}">Bento</a>
      <a href="?view=print&d=${encodedData}" class="active">Print</a>
    </div>
  </div>

  <div class="summary">
    <div class="summary-item">
      <div class="summary-value">${formatNumber(story.m)}</div>
      <div class="summary-label">Messages</div>
    </div>
    <div class="summary-item">
      <div class="summary-value">${Math.round(story.h)}</div>
      <div class="summary-label">Hours</div>
    </div>
    <div class="summary-item">
      <div class="summary-value">${story.p}</div>
      <div class="summary-label">Projects</div>
    </div>
    <div class="summary-item">
      <div class="summary-value">${story.d}</div>
      <div class="summary-label">Days Active</div>
    </div>
  </div>

  <div class="two-col">
    <div>
      <div class="section">
        <div class="section-title">Monthly Activity</div>
        ${renderSparkline(monthlyActivity || [])}
        <div class="months-label">
          <span>J</span><span>F</span><span>M</span><span>A</span><span>M</span><span>J</span>
          <span>J</span><span>A</span><span>S</span><span>O</span><span>N</span><span>D</span>
        </div>
      </div>

      ${isV3 ? `
      <div class="section">
        <div class="section-title">Weekly Rhythm</div>
        ${renderHeatmapSvg((story as WrappedStoryV3).hm)}
      </div>
      ` : ''}

      <div class="section">
        <div class="section-title">Top Projects</div>
        <table class="project-table">
          <tr><th>Project</th><th>Messages</th></tr>
          ${story.tp.slice(0, 6).map((p: any) => `
            <tr>
              <td>${escapeHtml(p.n)}</td>
              <td>${formatNumber(p.m)}</td>
            </tr>
          `).join('')}
        </table>
      </div>
    </div>

    <div>
      ${isV3 ? `
      <div class="section">
        <div class="section-title">Coding Style</div>
        <div class="trait-list">
          ${[
            ['ad', 'Delegation'],
            ['sp', 'Deep Work'],
            ['fc', 'Focus'],
            ['bs', 'Burst'],
            ['ri', 'Intensity'],
          ].map(([key, label]) => {
            const value = ((story as WrappedStoryV3).ts as any)[key] || 50;
            return `
              <div class="trait-row">
                <span class="trait-name">${label}</span>
                <div class="trait-bar-bg"><div class="trait-bar-fill" style="width: ${value}%"></div></div>
                <span class="trait-value">${value}</span>
              </div>
            `;
          }).join('')}
        </div>
      </div>
      ` : ''}

      ${isV3 && (story as WrappedStoryV3).tk?.total > 0 ? `
      <div class="section">
        <div class="section-title">Token Usage</div>
        <table class="token-table">
          <tr><td>Total</td><td>${formatTokens((story as WrappedStoryV3).tk.total)}</td></tr>
          <tr><td>Input</td><td>${formatTokens((story as WrappedStoryV3).tk.input)}</td></tr>
          <tr><td>Output</td><td>${formatTokens((story as WrappedStoryV3).tk.output)}</td></tr>
          ${(story as WrappedStoryV3).tk.cache_read > 0 ? `<tr><td>Cache Read</td><td>${formatTokens((story as WrappedStoryV3).tk.cache_read)}</td></tr>` : ''}
          ${Object.entries((story as WrappedStoryV3).tk.models || {}).slice(0, 3).map(([model, count]) => `
            <tr><td>${getModelDisplayName(model)}</td><td>${formatTokens(count as number)}</td></tr>
          `).join('')}
        </table>
      </div>
      ` : ''}

      ${isV3 && (story as WrappedStoryV3).sk?.[0] > 0 ? `
      <div class="section">
        <div class="section-title">Streaks</div>
        <div class="streak-row"><span>Total Streaks</span><span>${(story as WrappedStoryV3).sk[0]}</span></div>
        <div class="streak-row"><span>Longest</span><span>${(story as WrappedStoryV3).sk[1]} days</span></div>
        <div class="streak-row"><span>Current</span><span>${(story as WrappedStoryV3).sk[2]} days</span></div>
        <div class="streak-row"><span>Average</span><span>${(story as WrappedStoryV3).sk[3]} days</span></div>
      </div>
      ` : ''}

      <div class="section">
        <div class="section-title">Session Stats</div>
        <div class="streak-row"><span>Total Sessions</span><span>${story.s}</span></div>
        <div class="streak-row"><span>Longest Session</span><span>${isV3 ? (story as WrappedStoryV3).ls.toFixed(1) : (story as WrappedStory).ls?.toFixed(1) || '0'}h</span></div>
        <div class="streak-row"><span>Avg per Day</span><span>${(story.h / (story.d || 1)).toFixed(1)}h</span></div>
      </div>
    </div>
  </div>

  <div class="footer">
    Claude Code Wrapped ${year} | Generated from local Claude Code history
  </div>
</body>
</html>`;
}
