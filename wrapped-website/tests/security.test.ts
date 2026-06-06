import { describe, it, expect } from 'vitest';
import msgpack from 'msgpack-lite';

import app from '../src/index';
import { decodeWrappedStoryV3, validateStoryV3, type WrappedStoryV3 } from '../src/decoder';
import { renderPrintPage } from '../src/pages/print';

function base64UrlEncode(value: unknown): string {
  const packed = msgpack.encode(value);
  let binary = '';
  const bytes = new Uint8Array(packed);
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function validRawStory(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    v: 3,
    y: 2025,
    n: 'Tester',
    p: 1,
    s: 1,
    m: 10,
    h: 1,
    d: 1,
    hm: Array(168).fill(0),
    ma: Array(12).fill(0),
    mh: Array(12).fill(0),
    ms: Array(12).fill(0),
    sd: Array(10).fill(0),
    ar: Array(10).fill(0),
    ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [['Project', 10, 1, 1, 1, 0]],
    pc: [],
    te: [],
    sf: [],
    ls: 1,
    sk: [0, 0, 0, 0],
    tk: { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} },
    ...overrides,
  };
}

function validStory(overrides: Partial<WrappedStoryV3> = {}): WrappedStoryV3 {
  return decodeWrappedStoryV3(base64UrlEncode(validRawStory(overrides as Record<string, unknown>)));
}

describe('Wrapped URL security validation', () => {
  it('rejects non-numeric core fields instead of rendering them', () => {
    const story = validStory({ p: '<img src=x onerror=alert(1)>' as any });

    expect(validateStoryV3(story).valid).toBe(false);
  });

  it('rejects unknown future wire versions', () => {
    expect(() => decodeWrappedStoryV3(base64UrlEncode(validRawStory({ v: 4 })))).toThrow(/version/i);
  });

  it('rejects RLE heatmaps that expand beyond the fixed 168 cells', () => {
    expect(() => decodeWrappedStoryV3(base64UrlEncode(validRawStory({ hm: [0, 169], hm_rle: true })))).toThrow(/heatmap/i);
  });

  it('escapes and clamps rendered values defensively', () => {
    const story = validStory({
      p: '<script>alert(1)</script>' as any,
      d: '<img src=x onerror=alert(2)>' as any,
      ts: { ad: '0%;background:url(javascript:alert(3))' } as any,
      tk: { total: 1, input: 1, output: 1, cache_read: 0, cache_create: 0, models: { '<svg onload=alert(4)>': '<b>bad</b>' as any } },
    });

    const html = renderPrintPage({ story, year: 2025, encodedData: 'abc' });

    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).not.toContain('<img src=x onerror=alert(2)>');
    expect(html).not.toContain('javascript:alert(3)');
    expect(html).not.toContain('<svg onload=alert(4)>');
    expect(html).toContain('width: 50%');
  });
});

describe('Worker route hardening', () => {
  it('rejects invalid OG payloads before image generation', async () => {
    const encoded = base64UrlEncode(validRawStory({ p: '<script>alert(1)</script>' }));

    const response = await app.request(`/og/2025/${encoded}.svg`);

    expect(response.status).toBe(400);
  });

  it('does not serve SVG content from misleading .png OG URLs', async () => {
    const response = await app.request(`/og/2025/${base64UrlEncode(validRawStory())}.png`);

    expect(response.status).toBe(400);
  });

  it('rejects object-like top project names instead of stringifying them', async () => {
    const encoded = base64UrlEncode(validRawStory({ tp: [[["not", "a", "name"], 10, 1, 1, 1, 0]] }));
    const response = await app.request(`/wrapped?d=${encoded}`);

    expect(response.status).toBe(400);
  });

  it('sets privacy and browser-hardening headers on wrapped HTML', async () => {
    const response = await app.request(`/wrapped?d=${base64UrlEncode(validRawStory())}`);

    expect(response.status).toBe(200);
    expect(response.headers.get('cache-control')).toContain('no-store');
    expect(response.headers.get('referrer-policy')).toBe('no-referrer');
    expect(response.headers.get('x-content-type-options')).toBe('nosniff');
    expect(response.headers.get('content-security-policy')).toContain("default-src 'none'");
  });

  it('rejects malformed legacy years with trailing junk', async () => {
    const response = await app.request('/2025abc/not-real');

    expect(response.status).toBe(400);
  });
});
