/**
 * Claude Code Wrapped - Cloudflare Worker
 *
 * Routes:
 * - GET /           - Landing page
 * - GET /wrapped?d= - Wrapped page (Print view)
 * - GET /og/:year/:data.svg - Open Graph SVG image
 */

import { Hono } from 'hono';
import { renderLandingPage } from './pages/landing';
import { renderPrintPage, renderErrorPage } from './pages/print';
import { decodeWrappedStoryAuto, validateStoryV3 } from './decoder';
import { generateOgImage, getOgImageContentType } from './og';

type Bindings = {
  // Add KV bindings here when needed for Phase 5
};

const app = new Hono<{ Bindings: Bindings }>();

const BASE64URL_RE = /^[A-Za-z0-9_-]+$/;
const SECURITY_HEADERS = {
  'Cache-Control': 'no-store',
  'Referrer-Policy': 'no-referrer',
  'X-Content-Type-Options': 'nosniff',
  'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
};

function withSecurityHeaders(response: Response, extra: Record<string, string> = {}): Response {
  for (const [key, value] of Object.entries({ ...SECURITY_HEADERS, ...extra })) {
    response.headers.set(key, value);
  }
  return response;
}

function parseStrictYear(value: string): number | null {
  if (!/^\d{4}$/.test(value)) return null;
  const year = Number(value);
  const currentYear = new Date().getFullYear();
  return year >= 2024 && year <= currentYear ? year : null;
}

function isBase64Url(value: string): boolean {
  return BASE64URL_RE.test(value);
}

// Landing page
app.get('/', (c) => {
  return withSecurityHeaders(c.html(renderLandingPage()));
});

// Health check
app.get('/health', (c) => {
  return withSecurityHeaders(c.json({ status: 'ok', timestamp: new Date().toISOString() }));
});

// Wrapped page with query parameter
app.get('/wrapped', (c) => {
  const encodedData = c.req.query('d');

  if (!encodedData || !isBase64Url(encodedData)) {
    return withSecurityHeaders(c.html(renderErrorPage('Missing or invalid data parameter. URL should include ?d=encodedData'), 400));
  }

  // Decode story (auto-detects version)
  let story;
  try {
    story = decodeWrappedStoryAuto(encodedData);
  } catch (error) {
    return withSecurityHeaders(c.html(renderErrorPage('Invalid Wrapped URL. The data could not be decoded.'), 400));
  }

  const validation = validateStoryV3(story);
  if (!validation.valid) {
    return withSecurityHeaders(c.html(renderErrorPage(validation.error || 'Invalid data'), 400));
  }

  const year = story.y;
  const origin = new URL(c.req.url).origin;

  return withSecurityHeaders(c.html(renderPrintPage({ story, year, encodedData, origin })));
});

// OG Image endpoint
app.get('/og/:year/:data', async (c) => {
  const year = parseStrictYear(c.req.param('year'));
  const dataParam = c.req.param('data');
  if (dataParam.endsWith('.png')) {
    return withSecurityHeaders(c.text('OG previews are SVG; use .svg', 400));
  }
  const encodedData = dataParam.replace(/\.svg$/, '');

  if (year === null) {
    return withSecurityHeaders(c.text('Invalid year', 400));
  }
  if (!isBase64Url(encodedData)) {
    return withSecurityHeaders(c.text('Invalid data', 400));
  }

  // Decode story (auto-detects version)
  let story;
  try {
    story = decodeWrappedStoryAuto(encodedData);
  } catch (error) {
    return withSecurityHeaders(c.text('Invalid data', 400));
  }

  const validation = validateStoryV3(story);
  if (!validation.valid) {
    return withSecurityHeaders(c.text(validation.error || 'Invalid data', 400));
  }

  // Validate year matches
  if (story.y !== year) {
    return withSecurityHeaders(c.text('Year mismatch', 400));
  }

  try {
    const svg = await generateOgImage(story, year);
    return withSecurityHeaders(new Response(svg, {
      headers: {
        'Content-Type': getOgImageContentType(),
      },
    }), {
      'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox",
    });
  } catch (error) {
    console.error('OG image generation failed:', error);
    return withSecurityHeaders(c.text('Failed to generate image', 500));
  }
});

// Legacy route - redirect to /wrapped with query param
app.get('/:year/:data', (c) => {
  const year = parseStrictYear(c.req.param('year'));
  const encodedData = c.req.param('data');

  if (year === null) {
    const currentYear = new Date().getFullYear();
    return withSecurityHeaders(c.html(renderErrorPage(`Invalid year. Claude Code Wrapped is available for 2024-${currentYear}.`), 400));
  }
  if (!isBase64Url(encodedData)) {
    return withSecurityHeaders(c.html(renderErrorPage('Invalid data parameter.'), 400));
  }

  // Redirect to new URL format
  return c.redirect(`/wrapped?d=${encodeURIComponent(encodedData)}`);
});

// 404 handler
app.notFound((c) => {
  return withSecurityHeaders(c.html(renderErrorPage('Page not found'), 404));
});

// Error handler
app.onError((err, c) => {
  console.error('Error:', err);
  return withSecurityHeaders(c.html(renderErrorPage('An unexpected error occurred'), 500));
});

export default app;
