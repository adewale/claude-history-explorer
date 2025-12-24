/**
 * Vitest wrapper for existing decoder tests.
 * Runs the original test suite and captures coverage via Istanbul.
 */
import { describe, it, expect } from 'vitest';
import msgpack from 'msgpack-lite';

import {
  rleDecode,
  decodeWrappedStoryV3,
  decodeWrappedStoryAuto,
  validateStoryV3,
  formatNumber,
  formatNumberCompact,
  formatDuration,
  getTraitDescription,
  truncate,
  generateSparkline,
  findPeakTime,
  calcYoyChange,
  isV3Story,
  normalizeTraitScore,
  normalizeFingerprint,
  getHeatmapValue,
  getEventTypeName,
  dayOfYearToMonth,
  type WrappedStoryV3,
} from '../src/decoder';
import * as constants from '../src/constants';

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  const base64 = btoa(binary);
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

describe('RLE Decode', () => {
  it('decodes basic pattern', () => {
    expect(rleDecode([0, 3, 5, 2, 0, 1])).toEqual([0, 0, 0, 5, 5, 0]);
  });
  it('decodes single values', () => {
    expect(rleDecode([1, 1, 2, 1, 3, 1])).toEqual([1, 2, 3]);
  });
  it('decodes all same', () => {
    expect(rleDecode([7, 5])).toEqual([7, 7, 7, 7, 7]);
  });
  it('decodes empty', () => {
    expect(rleDecode([])).toEqual([]);
  });
});

describe('Format Functions', () => {
  it('formatNumber with commas', () => {
    expect(formatNumber(1234567)).toBe('1,234,567');
  });
  it('formatNumberCompact millions', () => {
    expect(formatNumberCompact(1500000)).toBe('1.5M');
  });
  it('formatDuration', () => {
    expect(formatDuration(90)).toBe('1h 30m');
  });
  it('truncate', () => {
    expect(truncate('Hello World', 6)).toBe('Hello…');
  });
});

describe('Sparkline', () => {
  it('generates sparkline', () => {
    const sparkline = generateSparkline([0, 50, 100, 50, 0]);
    expect(sparkline.length).toBe(5);
  });
  it('handles empty', () => {
    expect(generateSparkline([])).toBe('');
  });
});

describe('Trait Description', () => {
  it('low score', () => {
    expect(getTraitDescription('ad', 10)).toBe('Hands-on');
  });
  it('high score', () => {
    expect(getTraitDescription('ad', 90)).toBe('Delegates heavily');
  });
  it('middle score', () => {
    expect(getTraitDescription('ad', 50)).toBe('Balanced');
  });
});

describe('Heatmap Helpers', () => {
  it('gets heatmap value', () => {
    const heatmap = Array(168).fill(0);
    heatmap[10] = 50;
    expect(getHeatmapValue(heatmap, 0, 10)).toBe(50);
  });
  it('handles invalid', () => {
    expect(getHeatmapValue(Array(168).fill(0), -1, 0)).toBe(0);
  });
});

describe('Find Peak Time', () => {
  it('finds peak', () => {
    const heatmap = Array(168).fill(0);
    heatmap[2 * 24 + 14] = 100;
    const peak = findPeakTime(heatmap);
    expect(peak.day).toBe('Wed');
    expect(peak.hour).toBe(14);
  });
});

describe('YoY Change', () => {
  it('calculates growth', () => {
    expect(calcYoyChange(150, 100)).toEqual({ value: 50, direction: 'up' });
  });
  it('calculates decline', () => {
    expect(calcYoyChange(50, 100)).toEqual({ value: 50, direction: 'down' });
  });
});

describe('Normalization', () => {
  it('normalizes trait', () => {
    expect(normalizeTraitScore(50)).toBe(0.5);
  });
  it('normalizes fingerprint', () => {
    expect(normalizeFingerprint(75)).toBe(0.75);
  });
});

describe('Event Types', () => {
  it('gets event type name', () => {
    expect(getEventTypeName(0)).toBe('peak_day');
    expect(getEventTypeName(4)).toBe('milestone');
  });
});

describe('Day of Year', () => {
  it('handles leap year', () => {
    expect(dayOfYearToMonth(60, 2024)).toBe('Feb');
    expect(dayOfYearToMonth(60, 2025)).toBe('Mar');
  });
});

describe('Validate Story', () => {
  const validStory: WrappedStoryV3 = {
    v: 3,
    y: 2025,
    p: 5, s: 100, m: 5000, h: 200, d: 45,
    hm: Array(168).fill(0),
    ma: Array(12).fill(0), mh: Array(12).fill(0), ms: Array(12).fill(0),
    sd: Array(10).fill(0), ar: Array(10).fill(0), ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [], pc: [], te: [], sf: [], ls: 0, sk: [0, 0, 0, 0],
    tk: { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} },
  };

  it('validates valid story', () => {
    expect(validateStoryV3(validStory).valid).toBe(true);
  });
  it('rejects invalid version', () => {
    expect(validateStoryV3({ ...validStory, v: 2 as any }).valid).toBe(false);
  });
  it('rejects invalid year', () => {
    expect(validateStoryV3({ ...validStory, y: 2020 }).valid).toBe(false);
  });
  it('rejects invalid heatmap', () => {
    expect(validateStoryV3({ ...validStory, hm: Array(100).fill(0) }).valid).toBe(false);
  });
});

describe('Decode V3 Story', () => {
  it('decodes full story', () => {
    const rawStory = {
      v: 3, y: 2025, n: 'TestUser', p: 5, s: 100, m: 5000, h: 200, d: 45,
      hm: Array(168).fill(0),
      ma: [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
      mh: [10, 20, 30, 40, 50, 60, 50, 40, 30, 20, 10, 5],
      ms: [8, 10, 12, 15, 18, 20, 18, 15, 12, 10, 8, 6],
      sd: [5, 10, 20, 30, 15, 10, 5, 3, 1, 1],
      ar: [2, 5, 10, 15, 20, 20, 15, 8, 3, 2],
      ml: [10, 20, 30, 25, 10, 3, 1, 1],
      ts: { ad: 45, sp: 65, fc: 72, cc: 58, wr: 25, bs: 40, cs: 33, mv: 55, td: 60, ri: 70 },
      tp: [['MainProject', 2000, 80, 25, 40, 45]],
      pc: [[0, 1, 10]], te: [[50, 0, 150, -1]], sf: [[120, 100, 0, 10, 0, 0, 20, 40, 60, 80, 50, 10, 30, 20]],
      ls: 4.5, sk: [5, 10, 3, 4],
      tk: { total: 1000000, input: 600000, output: 400000, cache_read: 200000, cache_create: 50000, models: { 'sonnet': 800000 } },
    };
    const packed = msgpack.encode(rawStory);
    const encoded = base64UrlEncode(new Uint8Array(packed));
    const decoded = decodeWrappedStoryV3(encoded);

    expect(decoded.v).toBe(3);
    expect(decoded.y).toBe(2025);
    expect(decoded.n).toBe('TestUser');
    expect(decoded.tp[0].n).toBe('MainProject');
  });
});

describe('Constants', () => {
  it('has correct heatmap size', () => {
    expect(constants.HEATMAP_SIZE).toBe(168);
  });
});
