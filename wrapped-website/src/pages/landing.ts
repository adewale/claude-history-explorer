/**
 * Landing page HTML for wrapped.claude.codes
 */

export function renderLandingPage(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Claude Code Wrapped</title>
  <meta name="description" content="Your year in code with Claude. Generate a shareable summary of your development journey.">
  <meta property="og:title" content="Claude Code Wrapped">
  <meta property="og:description" content="Your year in code with Claude. See your development journey.">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    :root {
      --bg-dark: #0a0a0a;
      --bg-card: #141414;
      --text-primary: #ffffff;
      --text-secondary: #a0a0a0;
      --accent: #d4a574;
      --accent-hover: #e5b889;
      --border: #2a2a2a;
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-dark);
      color: var(--text-primary);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 2rem;
    }

    .container {
      max-width: 600px;
      text-align: center;
    }

    .logo {
      font-size: 3rem;
      margin-bottom: 1rem;
    }

    h1 {
      font-size: 2.5rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
      background: linear-gradient(135deg, var(--accent), #fff);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }

    .subtitle {
      font-size: 1.25rem;
      color: var(--text-secondary);
      margin-bottom: 3rem;
    }

    .command-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 2rem;
      margin-bottom: 2rem;
    }

    .command-card h2 {
      font-size: 1rem;
      color: var(--text-secondary);
      margin-bottom: 1rem;
      font-weight: 500;
    }

    .command {
      background: #1a1a1a;
      border-radius: 8px;
      padding: 1rem 1.5rem;
      font-family: 'SF Mono', Monaco, 'Courier New', monospace;
      font-size: 1rem;
      color: var(--accent);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }

    .command code {
      flex: 1;
      text-align: left;
    }

    .copy-btn {
      background: none;
      border: none;
      color: var(--text-secondary);
      cursor: pointer;
      padding: 0.5rem;
      border-radius: 4px;
      transition: all 0.2s;
    }

    .copy-btn:hover {
      color: var(--text-primary);
      background: rgba(255, 255, 255, 0.1);
    }

    .features {
      display: grid;
      gap: 1rem;
      margin-bottom: 2rem;
    }

    .feature {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      color: var(--text-secondary);
      font-size: 0.95rem;
    }

    .feature-icon {
      width: 24px;
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .privacy-note {
      color: var(--text-secondary);
      font-size: 0.875rem;
      padding: 1rem;
      background: rgba(212, 165, 116, 0.1);
      border-radius: 8px;
      border: 1px solid rgba(212, 165, 116, 0.2);
    }

    .privacy-note strong {
      color: var(--accent);
    }

    footer {
      margin-top: 3rem;
      color: var(--text-secondary);
      font-size: 0.875rem;
    }

    footer a {
      color: var(--accent);
      text-decoration: none;
    }

    footer a:hover {
      text-decoration: underline;
    }

    @media (max-width: 640px) {
      h1 {
        font-size: 2rem;
      }
      .subtitle {
        font-size: 1rem;
      }
      .command {
        flex-direction: column;
        gap: 0.75rem;
      }
      .command code {
        text-align: center;
        font-size: 0.9rem;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">🎁</div>
    <h1>Claude Code Wrapped</h1>
    <p class="subtitle">Your year in code with Claude</p>

    <div class="command-card">
      <h2>Generate your wrapped</h2>
      <div class="command">
        <code>claude-history wrapped</code>
        <button class="copy-btn" onclick="copyCommand()" title="Copy to clipboard">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
        </button>
      </div>
    </div>

    <div class="features">
      <div class="feature">
        <span class="feature-icon">📊</span>
        <span>See your message count, hours coded, and projects</span>
      </div>
      <div class="feature">
        <span class="feature-icon">🎭</span>
        <span>Discover your coding personality traits</span>
      </div>
      <div class="feature">
        <span class="feature-icon">📈</span>
        <span>View your monthly activity sparkline</span>
      </div>
      <div class="feature">
        <span class="feature-icon">🔗</span>
        <span>Share your story with a unique URL</span>
      </div>
    </div>

    <div class="privacy-note">
      <strong>🔒 Privacy first:</strong> All data is encoded in the URL itself.
      We never see, store, or process your code or conversations.
    </div>

    <footer>
      Part of <a href="https://github.com/anthropics/claude-code" target="_blank" rel="noopener">Claude Code</a>
    </footer>
  </div>

  <script>
    function copyCommand() {
      navigator.clipboard.writeText('claude-history wrapped');
      const btn = document.querySelector('.copy-btn');
      btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>';
      setTimeout(() => {
        btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
      }, 2000);
    }
  </script>
</body>
</html>`;
}
