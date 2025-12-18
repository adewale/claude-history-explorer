/**
 * OG Image Generator
 *
 * Generates SVG images for social sharing.
 * The SVG is returned as a PNG-compatible format that social platforms can render.
 */

import { WrappedStory, WrappedStoryV3, formatNumber, generateSparkline, isV3Story, getTraitDescription } from './decoder';

/**
 * Generate an OG image as SVG (social platforms will render it)
 */
export async function generateOgImage(story: WrappedStoryV3, year: number): Promise<Uint8Array> {
  const displayName = story.n || 'Someone';
  // V3 uses story.ma for monthly activity
  const monthlyActivity = story.ma;
  const sparkline = generateSparkline(monthlyActivity || []);

  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#0a0a0a"/>
      <stop offset="100%" style="stop-color:#1a1a1a"/>
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#d4a574"/>
      <stop offset="100%" style="stop-color:#e5c9a8"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="1200" height="630" fill="url(#bg)"/>

  <!-- Year Badge -->
  <rect x="530" y="60" width="140" height="40" rx="20" fill="rgba(212, 165, 116, 0.2)" stroke="rgba(212, 165, 116, 0.4)" stroke-width="1"/>
  <text x="600" y="88" fill="#d4a574" font-family="Inter, sans-serif" font-size="24" text-anchor="middle">${year}</text>

  <!-- Title -->
  <text x="600" y="160" fill="#ffffff" font-family="Inter, sans-serif" font-size="42" font-weight="700" text-anchor="middle">
    ${story.n ? `${escapeXml(displayName)}'s Claude Code Wrapped` : 'Claude Code Wrapped'}
  </text>

  <!-- Stats Row -->
  <!-- Messages -->
  <text x="300" y="270" fill="#d4a574" font-family="Inter, sans-serif" font-size="56" font-weight="700" text-anchor="middle">${formatNumber(story.m)}</text>
  <text x="300" y="305" fill="#a0a0a0" font-family="Inter, sans-serif" font-size="20" text-anchor="middle">messages</text>

  <!-- Projects -->
  <text x="600" y="270" fill="#d4a574" font-family="Inter, sans-serif" font-size="56" font-weight="700" text-anchor="middle">${story.p}</text>
  <text x="600" y="305" fill="#a0a0a0" font-family="Inter, sans-serif" font-size="20" text-anchor="middle">projects</text>

  <!-- Hours -->
  <text x="900" y="270" fill="#d4a574" font-family="Inter, sans-serif" font-size="56" font-weight="700" text-anchor="middle">${Math.round(story.h)}</text>
  <text x="900" y="305" fill="#a0a0a0" font-family="Inter, sans-serif" font-size="20" text-anchor="middle">hours</text>

  <!-- Sparkline -->
  <text x="600" y="390" fill="#d4a574" font-family="Inter, sans-serif" font-size="36" text-anchor="middle" letter-spacing="4">${sparkline}</text>

  <!-- Month Labels -->
  <text x="600" y="420" fill="#666666" font-family="Inter, sans-serif" font-size="12" text-anchor="middle" letter-spacing="28">J F M A M J J A S O N D</text>

  <!-- Traits -->
  ${renderTraitsV3(story.ts, 460)}

  <!-- Footer -->
  <text x="600" y="600" fill="#666666" font-family="Inter, sans-serif" font-size="16" text-anchor="middle">wrapped-claude-codes.adewale-883.workers.dev</text>
</svg>`;

  // Return as UTF-8 encoded bytes
  return new TextEncoder().encode(svg);
}

function escapeXml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

import { TraitScores } from './decoder';

function renderTraitsV3(ts: TraitScores, y: number): string {
  // Pick 4 key traits for the OG image
  const traitKeys = ['ad', 'sp', 'fc', 'ri'] as const;
  const traits = traitKeys.map(k => getTraitDescription(k, ts[k]));

  const totalWidth = traits.reduce((sum, t) => sum + t.length * 10 + 32, 0) + (traits.length - 1) * 12;
  let x = 600 - totalWidth / 2;

  return traits.map(trait => {
    const width = trait.length * 10 + 32;
    const result = `
      <rect x="${x}" y="${y}" width="${width}" height="36" rx="18" fill="#1a1a1a" stroke="#333333" stroke-width="1"/>
      <text x="${x + width / 2}" y="${y + 24}" fill="#ffffff" font-family="Inter, sans-serif" font-size="16" text-anchor="middle">${escapeXml(trait)}</text>
    `;
    x += width + 12;
    return result;
  }).join('');
}

/**
 * Get content type for the OG image
 */
export function getOgImageContentType(): string {
  return 'image/svg+xml';
}
