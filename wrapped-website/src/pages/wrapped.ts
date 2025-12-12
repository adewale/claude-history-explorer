/**
 * Wrapped story page HTML
 */

import { WrappedStory, formatNumber, generateSparkline, getMessageDescriptor } from '../decoder';

interface RenderOptions {
  story: WrappedStory;
  year: number;
  encodedData: string;
  ogImageUrl: string;
}

export function renderWrappedPage({ story, year, encodedData, ogImageUrl }: RenderOptions): string {
  const pageUrl = `https://wrapped-claude-codes.adewale-883.workers.dev/${year}/${encodedData}`;
  const displayName = story.n || 'Someone';
  const sparkline = generateSparkline(story.a);
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
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
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
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-dark);
      color: var(--text-primary);
      min-height: 100vh;
      overflow-x: hidden;
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
      max-width: 400px;
      width: 100%;
      text-align: center;
    }

    /* Card Styles */
    .card-emoji {
      font-size: 4rem;
      margin-bottom: 1.5rem;
      animation: bounce 2s ease-in-out infinite;
    }

    @keyframes bounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-10px); }
    }

    .card-title {
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 1rem;
      line-height: 1.2;
    }

    .card-subtitle {
      font-size: 1.1rem;
      color: var(--text-secondary);
      margin-bottom: 2rem;
    }

    .big-number {
      font-size: 4rem;
      font-weight: 800;
      background: linear-gradient(135deg, var(--accent), var(--accent-light));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 0.5rem;
    }

    .big-number-label {
      font-size: 1.25rem;
      color: var(--text-secondary);
    }

    .sparkline {
      font-size: 2rem;
      letter-spacing: 2px;
      color: var(--accent);
      margin: 1.5rem 0;
    }

    .sparkline-labels {
      display: flex;
      justify-content: space-between;
      color: var(--text-muted);
      font-size: 0.75rem;
      padding: 0 0.25rem;
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
    }

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
    }

    .project-rank {
      font-size: 1.5rem;
      font-weight: 700;
      color: var(--accent);
      width: 2rem;
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

    /* Navigation */
    .nav-controls {
      display: flex;
      justify-content: space-between;
      padding: 1rem 2rem 2rem;
      background: linear-gradient(to top, rgba(0,0,0,0.8), transparent);
    }

    .nav-btn {
      background: var(--bg-card);
      border: 1px solid var(--border);
      color: var(--text-primary);
      padding: 0.75rem 1.5rem;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.9rem;
      transition: all 0.2s;
    }

    .nav-btn:hover {
      background: var(--bg-card-hover);
    }

    .nav-btn:disabled {
      opacity: 0.3;
      cursor: not-allowed;
    }

    .skip-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 0.875rem;
    }

    .skip-btn:hover {
      color: var(--text-secondary);
    }

    /* Privacy Footer */
    .privacy-footer {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      text-align: center;
      padding: 1rem;
      font-size: 0.75rem;
      color: var(--text-muted);
      background: linear-gradient(to top, var(--bg-dark), transparent);
      pointer-events: none;
    }

    .privacy-footer a {
      color: var(--text-secondary);
      text-decoration: none;
      pointer-events: auto;
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
        padding: 1rem;
      }
    }
  </style>
</head>
<body>
  <div class="story-container">
    <!-- Progress Bar -->
    <div class="progress-bar" id="progress">
      ${generateProgressSegments(8)}
    </div>

    <!-- Cards -->
    <div class="cards-viewport" id="viewport">
      ${renderCards(story, year, pageUrl)}
    </div>

    <!-- Navigation -->
    <div class="nav-controls">
      <button class="nav-btn" id="prevBtn" onclick="prevCard()" disabled>← Back</button>
      <button class="skip-btn" onclick="skipToSummary()">Skip to summary</button>
      <button class="nav-btn" id="nextBtn" onclick="nextCard()">Next →</button>
    </div>

    <!-- Privacy Footer -->
    <div class="privacy-footer">
      🔒 All data encoded in URL • <a href="javascript:void(0)" onclick="showPrivacyInfo()">Learn how</a>
    </div>
  </div>

  <script>
    let currentCard = 0;
    const totalCards = 8;
    let autoAdvanceTimer = null;

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
        if (i < currentCard) {
          seg.classList.add('completed');
        } else if (i === currentCard) {
          seg.classList.add('active');
        }
      });

      document.getElementById('prevBtn').disabled = currentCard === 0;
      document.getElementById('nextBtn').textContent = currentCard === totalCards - 1 ? 'Done' : 'Next →';

      // Auto-advance (except last card)
      clearTimeout(autoAdvanceTimer);
      if (currentCard < totalCards - 1) {
        autoAdvanceTimer = setTimeout(() => nextCard(), 5000);
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
      alert('All your wrapped data is encoded directly in the URL using MessagePack + Base64.\\n\\nWe never see, store, or process:\\n• Your code\\n• Your conversations\\n• File paths\\n• Project names (only shown if you share)\\n\\nYou can verify this by inspecting network requests.');
    }

    // Touch/swipe support
    let touchStartX = 0;
    document.addEventListener('touchstart', e => {
      touchStartX = e.touches[0].clientX;
    });

    document.addEventListener('touchend', e => {
      const touchEndX = e.changedTouches[0].clientX;
      const diff = touchStartX - touchEndX;
      if (Math.abs(diff) > 50) {
        if (diff > 0) nextCard();
        else prevCard();
      }
    });

    // Keyboard support
    document.addEventListener('keydown', e => {
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

function renderCards(story: WrappedStory, year: number, pageUrl: string): string {
  const displayName = story.n || 'You';
  const sparkline = generateSparkline(story.a);

  const cards = [
    // Card 1: Hook
    `<div class="card">
      <div class="card-content">
        <div class="card-emoji">🎁</div>
        <h1 class="card-title">${displayName} had ${getMessageDescriptor(story.m)} year with Claude</h1>
        <p class="card-subtitle">Let's unwrap ${year}...</p>
      </div>
    </div>`,

    // Card 2: Messages
    `<div class="card">
      <div class="card-content">
        <div class="card-emoji">💬</div>
        <div class="big-number">${formatNumber(story.m)}</div>
        <div class="big-number-label">messages exchanged</div>
        <p class="card-subtitle" style="margin-top: 1.5rem">That's ${Math.round(story.m / 365)} messages per day on average</p>
      </div>
    </div>`,

    // Card 3: Hours
    `<div class="card">
      <div class="card-content">
        <div class="card-emoji">⏱️</div>
        <div class="big-number">${Math.round(story.h)}</div>
        <div class="big-number-label">hours of development</div>
        <p class="card-subtitle" style="margin-top: 1.5rem">Across ${story.p} projects and ${story.s} sessions</p>
      </div>
    </div>`,

    // Card 4: Timeline
    `<div class="card">
      <div class="card-content">
        <div class="card-emoji">📈</div>
        <h2 class="card-title">Your Year in Motion</h2>
        <div class="sparkline">${sparkline}</div>
        <div class="sparkline-labels">
          <span>Jan</span><span>Feb</span><span>Mar</span><span>Apr</span><span>May</span><span>Jun</span>
          <span>Jul</span><span>Aug</span><span>Sep</span><span>Oct</span><span>Nov</span><span>Dec</span>
        </div>
      </div>
    </div>`,

    // Card 5: Personality
    `<div class="card">
      <div class="card-content">
        <div class="card-emoji">🎭</div>
        <h2 class="card-title">Your Coding Personality</h2>
        <p class="card-subtitle">${story.c} • ${story.w}</p>
        <div class="traits-list">
          ${story.t.map(trait => `<span class="trait-badge">${trait}</span>`).join('')}
        </div>
      </div>
    </div>`,

    // Card 6: Peak Project
    `<div class="card">
      <div class="card-content">
        <div class="card-emoji">🏆</div>
        <h2 class="card-title">Your Top Projects</h2>
        <div class="top-projects">
          ${story.tp.map((proj, i) => `
            <div class="project-item">
              <div class="project-rank">#${i + 1}</div>
              <div class="project-info">
                <div class="project-name">${proj.n}</div>
                <div class="project-stats">${formatNumber(proj.m)} messages • ${proj.d} days</div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>`,

    // Card 7: Parallel (conditional)
    story.ci > 1 ? `<div class="card">
      <div class="card-content">
        <div class="card-emoji">🔀</div>
        <div class="big-number">${story.ci}</div>
        <div class="big-number-label">Claude instances at once</div>
        <p class="card-subtitle" style="margin-top: 1.5rem">You're a parallel processing powerhouse!</p>
      </div>
    </div>` : `<div class="card">
      <div class="card-content">
        <div class="card-emoji">⏰</div>
        <div class="big-number">${story.ls.toFixed(1)}</div>
        <div class="big-number-label">hours longest session</div>
        <p class="card-subtitle" style="margin-top: 1.5rem">Deep work at its finest</p>
      </div>
    </div>`,

    // Card 8: Share
    `<div class="card">
      <div class="card-content">
        <div class="card-emoji">🎉</div>
        <h2 class="card-title">That's a wrap!</h2>
        <p class="card-subtitle">${formatNumber(story.m)} messages • ${story.p} projects • ${Math.round(story.h)} hours</p>
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
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', sans-serif;
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
    h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
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
