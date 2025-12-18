/**
 * Claude Code Wrapped - Cloudflare Worker
 *
 * Routes:
 * - GET /           - Landing page
 * - GET /:year/:data - Wrapped story page
 * - GET /og/:year/:data.png - Open Graph image
 */

import { Hono } from 'hono';
import { cache } from 'hono/cache';
import { renderLandingPage } from './pages/landing';
import { renderWrappedPage, renderErrorPage } from './pages/wrapped';
import { renderBentoPage } from './pages/bento';
import { renderPrintPage } from './pages/print';
import { decodeWrappedStoryAuto, validateStory, validateStoryV3, isV3Story } from './decoder';
import { generateOgImage, getOgImageContentType } from './og';

type Bindings = {
  // Add KV bindings here when needed for Phase 5
};

const app = new Hono<{ Bindings: Bindings }>();

// Landing page
app.get('/', (c) => {
  return c.html(renderLandingPage());
});

// Health check
app.get('/health', (c) => {
  return c.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Wrapped page with query parameter (supports /wrapped?d=encodedData&view=bento|print)
app.get('/wrapped', (c) => {
  const encodedData = c.req.query('d');
  const view = c.req.query('view');

  if (!encodedData) {
    return c.html(renderErrorPage('Missing data parameter. URL should include ?d=encodedData'), 400);
  }

  // Decode story (auto-detects version)
  let story;
  try {
    story = decodeWrappedStoryAuto(encodedData);
  } catch (error) {
    return c.html(renderErrorPage('Invalid Wrapped URL. The data could not be decoded.'), 400);
  }

  // Validate story based on version
  const validation = isV3Story(story) ? validateStoryV3(story) : validateStory(story);
  if (!validation.valid) {
    return c.html(renderErrorPage(validation.error || 'Invalid data'), 400);
  }

  const year = story.y;

  // Route to appropriate view
  if (view === 'bento') {
    return c.html(renderBentoPage({ story, year, encodedData }));
  }

  if (view === 'print') {
    return c.html(renderPrintPage({ story, year, encodedData }));
  }

  // Default: story view
  const ogImageUrl = `https://wrapped-claude-codes.adewale-883.workers.dev/og/${year}/${encodedData}.png`;

  return c.html(renderWrappedPage({
    story,
    year,
    encodedData,
    ogImageUrl,
  }));
});

// OG Image endpoint
app.get('/og/:year/:data', async (c) => {
  const year = parseInt(c.req.param('year'));
  const encodedData = c.req.param('data').replace(/\.png$/, '');

  // Validate year
  const currentYear = new Date().getFullYear();
  if (isNaN(year) || year < 2024 || year > currentYear + 1) {
    return c.text('Invalid year', 400);
  }

  // Decode story (auto-detects version)
  let story;
  try {
    story = decodeWrappedStoryAuto(encodedData);
  } catch (error) {
    return c.text('Invalid data', 400);
  }

  // Validate year matches
  if (story.y !== year) {
    return c.text('Year mismatch', 400);
  }

  // Check cache first
  const cacheKey = new Request(c.req.url);
  const cachedResponse = await caches.default.match(cacheKey);
  if (cachedResponse) {
    return cachedResponse;
  }

  try {
    // Generate image
    const png = await generateOgImage(story, year);

    const response = new Response(png, {
      headers: {
        'Content-Type': getOgImageContentType(),
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });

    // Cache the response
    c.executionCtx.waitUntil(caches.default.put(cacheKey, response.clone()));

    return response;
  } catch (error) {
    console.error('OG image generation failed:', error);
    return c.text('Failed to generate image', 500);
  }
});

// Wrapped story page
app.get('/:year/:data', (c) => {
  const year = parseInt(c.req.param('year'));
  const encodedData = c.req.param('data');

  // Validate year format
  const currentYear = new Date().getFullYear();
  if (isNaN(year) || year < 2024 || year > currentYear + 1) {
    return c.html(renderErrorPage(`Invalid year. Claude Code Wrapped is available for 2024-${currentYear}.`), 400);
  }

  // Decode story (auto-detects version)
  let story;
  try {
    story = decodeWrappedStoryAuto(encodedData);
  } catch (error) {
    return c.html(renderErrorPage('Invalid Wrapped URL. The data could not be decoded.'), 400);
  }

  // Validate story based on version
  const validation = isV3Story(story) ? validateStoryV3(story) : validateStory(story);
  if (!validation.valid) {
    return c.html(renderErrorPage(validation.error || 'Invalid data'), 400);
  }

  // Validate year matches data
  if (story.y !== year) {
    return c.html(
      renderErrorPage(`Year mismatch: URL says ${year} but data contains ${story.y}.`),
      400
    );
  }

  // Generate OG image URL
  const ogImageUrl = `https://wrapped-claude-codes.adewale-883.workers.dev/og/${year}/${encodedData}.png`;

  return c.html(renderWrappedPage({
    story,
    year,
    encodedData,
    ogImageUrl,
  }));
});

// 404 handler
app.notFound((c) => {
  return c.html(renderErrorPage('Page not found'), 404);
});

// Error handler
app.onError((err, c) => {
  console.error('Error:', err);
  return c.html(renderErrorPage('An unexpected error occurred'), 500);
});

export default app;
