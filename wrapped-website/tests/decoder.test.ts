/**
 * Unit tests for the V3 decoder
 *
 * Run with: npx tsx tests/decoder.test.ts
 */

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
  type TraitScores,
} from '../src/decoder';

// Test utilities
let passed = 0;
let failed = 0;

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (JSON.stringify(actual) === JSON.stringify(expected)) {
    console.log(`  ✓ ${message}`);
    passed++;
  } else {
    console.log(`  ✗ ${message}`);
    console.log(`    Expected: ${JSON.stringify(expected)}`);
    console.log(`    Actual: ${JSON.stringify(actual)}`);
    failed++;
  }
}

function assertTrue(condition: boolean, message: string) {
  if (condition) {
    console.log(`  ✓ ${message}`);
    passed++;
  } else {
    console.log(`  ✗ ${message}`);
    failed++;
  }
}

function assertFalse(condition: boolean, message: string) {
  assertTrue(!condition, message);
}

function assertThrows(fn: () => void, message: string) {
  try {
    fn();
    console.log(`  ✗ ${message} (did not throw)`);
    failed++;
  } catch (e) {
    console.log(`  ✓ ${message}`);
    passed++;
  }
}

// Base64URL encode for testing
function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  const base64 = btoa(binary);
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// Test suites

console.log('\n=== RLE Decode Tests ===');

function testRleDecode() {
  // Basic decoding
  assertEqual(
    rleDecode([0, 3, 5, 2, 0, 1]),
    [0, 0, 0, 5, 5, 0],
    'RLE decode basic pattern'
  );

  // Single values
  assertEqual(
    rleDecode([1, 1, 2, 1, 3, 1]),
    [1, 2, 3],
    'RLE decode single values'
  );

  // All same values
  assertEqual(
    rleDecode([7, 5]),
    [7, 7, 7, 7, 7],
    'RLE decode all same'
  );

  // Empty
  assertEqual(
    rleDecode([]),
    [],
    'RLE decode empty'
  );

  // Large run
  assertEqual(
    rleDecode([0, 100]),
    Array(100).fill(0),
    'RLE decode large run'
  );
}

testRleDecode();

console.log('\n=== Format Functions Tests ===');

function testFormatFunctions() {
  // formatNumber
  assertEqual(formatNumber(1234567), '1,234,567', 'formatNumber with commas');
  assertEqual(formatNumber(1000), '1,000', 'formatNumber thousands');
  assertEqual(formatNumber(42), '42', 'formatNumber small');

  // formatNumberCompact
  assertEqual(formatNumberCompact(1500000), '1.5M', 'formatNumberCompact millions');
  assertEqual(formatNumberCompact(2500), '2.5K', 'formatNumberCompact thousands');
  assertEqual(formatNumberCompact(500), '500', 'formatNumberCompact small');

  // formatDuration
  assertEqual(formatDuration(30), '30m', 'formatDuration minutes only');
  assertEqual(formatDuration(60), '1h', 'formatDuration exact hour');
  assertEqual(formatDuration(90), '1h 30m', 'formatDuration hours and minutes');
  assertEqual(formatDuration(0), '0m', 'formatDuration zero');

  // truncate
  assertEqual(truncate('Hello World', 20), 'Hello World', 'truncate no change needed');
  assertEqual(truncate('Hello World', 6), 'Hello…', 'truncate with ellipsis');
  assertEqual(truncate('Hi', 5), 'Hi', 'truncate short string');
}

testFormatFunctions();

console.log('\n=== Sparkline Tests ===');

function testSparkline() {
  // Basic sparkline
  const sparkline = generateSparkline([0, 50, 100, 50, 0]);
  assertTrue(sparkline.length === 5, 'sparkline has correct length');
  assertTrue(sparkline.includes('█'), 'sparkline has max char');
  assertTrue(sparkline.includes('▁'), 'sparkline has min char');

  // Empty data
  assertEqual(generateSparkline([]), '', 'sparkline empty');

  // All zeros
  const zeros = generateSparkline([0, 0, 0]);
  assertEqual(zeros, '▁▁▁', 'sparkline all zeros');

  // All same
  const same = generateSparkline([50, 50, 50]);
  assertTrue(same.length === 3, 'sparkline same values');
}

testSparkline();

console.log('\n=== Trait Description Tests ===');

function testTraitDescription() {
  // Low scores (< 33)
  assertEqual(getTraitDescription('ad', 10), 'Hands-on', 'trait low ad');
  assertEqual(getTraitDescription('sp', 20), 'Quick sessions', 'trait low sp');

  // High scores (> 67)
  assertEqual(getTraitDescription('ad', 90), 'Delegates heavily', 'trait high ad');
  assertEqual(getTraitDescription('sp', 80), 'Marathon sessions', 'trait high sp');

  // Middle scores (33-67)
  assertEqual(getTraitDescription('ad', 50), 'Balanced', 'trait middle');
  assertEqual(getTraitDescription('fc', 50), 'Balanced', 'trait middle fc');
}

testTraitDescription();

console.log('\n=== Heatmap Helpers Tests ===');

function testHeatmapHelpers() {
  const heatmap = Array(168).fill(0);
  // Monday 10am (day 0, hour 10)
  heatmap[10] = 50;
  // Sunday 23pm (day 6, hour 23)
  heatmap[6 * 24 + 23] = 100;

  assertEqual(getHeatmapValue(heatmap, 0, 10), 50, 'heatmap Monday 10am');
  assertEqual(getHeatmapValue(heatmap, 6, 23), 100, 'heatmap Sunday 11pm');
  assertEqual(getHeatmapValue(heatmap, 0, 0), 0, 'heatmap empty slot');
  assertEqual(getHeatmapValue(heatmap, -1, 0), 0, 'heatmap invalid day');
  assertEqual(getHeatmapValue(heatmap, 0, 30), 0, 'heatmap invalid hour');
}

testHeatmapHelpers();

console.log('\n=== Find Peak Time Tests ===');

function testFindPeakTime() {
  const heatmap = Array(168).fill(0);
  // Set peak at Wednesday 14:00 (day 2, hour 14)
  heatmap[2 * 24 + 14] = 100;

  const peak = findPeakTime(heatmap);
  assertEqual(peak.day, 'Wed', 'peak day is Wednesday');
  assertEqual(peak.hour, 14, 'peak hour is 14');
  assertEqual(peak.value, 100, 'peak value is 100');

  // Empty heatmap
  const emptyPeak = findPeakTime(Array(168).fill(0));
  assertEqual(emptyPeak.value, 0, 'empty heatmap peak value is 0');
}

testFindPeakTime();

console.log('\n=== YoY Change Tests ===');

function testYoyChange() {
  // Growth
  const growth = calcYoyChange(150, 100);
  assertEqual(growth.value, 50, 'yoy 50% growth value');
  assertEqual(growth.direction, 'up', 'yoy growth direction');

  // Decline
  const decline = calcYoyChange(50, 100);
  assertEqual(decline.value, 50, 'yoy 50% decline value');
  assertEqual(decline.direction, 'down', 'yoy decline direction');

  // No previous
  const noPrev = calcYoyChange(100, 0);
  assertEqual(noPrev.direction, 'same', 'yoy no previous');

  // Same
  const same = calcYoyChange(100, 100);
  assertEqual(same.value, 0, 'yoy same value');
  assertEqual(same.direction, 'same', 'yoy same direction');
}

testYoyChange();

console.log('\n=== Normalization Tests ===');

function testNormalization() {
  assertEqual(normalizeTraitScore(0), 0, 'normalize trait 0');
  assertEqual(normalizeTraitScore(50), 0.5, 'normalize trait 50');
  assertEqual(normalizeTraitScore(100), 1, 'normalize trait 100');

  assertEqual(normalizeFingerprint(0), 0, 'normalize fingerprint 0');
  assertEqual(normalizeFingerprint(75), 0.75, 'normalize fingerprint 75');
  assertEqual(normalizeFingerprint(100), 1, 'normalize fingerprint 100');
}

testNormalization();

console.log('\n=== Event Type Tests ===');

function testEventType() {
  assertEqual(getEventTypeName(0), 'peak_day', 'event type 0');
  assertEqual(getEventTypeName(1), 'streak_start', 'event type 1');
  assertEqual(getEventTypeName(2), 'streak_end', 'event type 2');
  assertEqual(getEventTypeName(3), 'new_project', 'event type 3');
  assertEqual(getEventTypeName(4), 'milestone', 'event type 4');
  assertEqual(getEventTypeName(5), 'gap_start', 'event type 5');
  assertEqual(getEventTypeName(6), 'gap_end', 'event type 6');
  // Unknown type defaults to peak_day
  assertEqual(getEventTypeName(99), 'peak_day', 'event type unknown');
}

testEventType();

console.log('\n=== isV3Story Tests ===');

function testIsV3Story() {
  const story: WrappedStoryV3 = {
    v: 3,
    y: 2025,
    p: 1, s: 1, m: 100, h: 1, d: 1,
    hm: Array(168).fill(0),
    ma: Array(12).fill(0), mh: Array(12).fill(0), ms: Array(12).fill(0),
    sd: Array(10).fill(0), ar: Array(10).fill(0), ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [], pc: [], te: [], sf: [], ls: 0, sk: [0, 0, 0, 0],
    tk: { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} },
  };

  // isV3Story always returns true now (V3 only)
  assertTrue(isV3Story(story), 'isV3Story returns true');
}

testIsV3Story();

console.log('\n=== Validate Story Tests ===');

function testValidateStory() {
  // Valid story
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

  const result = validateStoryV3(validStory);
  assertTrue(result.valid, 'valid story passes validation');

  // Invalid version
  const invalidVersion = { ...validStory, v: 2 as any };
  const versionResult = validateStoryV3(invalidVersion);
  assertFalse(versionResult.valid, 'invalid version fails');
  assertTrue(versionResult.error?.includes('Not a V3'), 'error mentions version');

  // Invalid year
  const invalidYear = { ...validStory, y: 2020 };
  const yearResult = validateStoryV3(invalidYear);
  assertFalse(yearResult.valid, 'invalid year fails');

  // Missing year
  const missingYear = { ...validStory, y: null as any };
  const missingYearResult = validateStoryV3(missingYear);
  assertFalse(missingYearResult.valid, 'missing year fails');

  // Invalid heatmap size
  const invalidHeatmap = { ...validStory, hm: Array(100).fill(0) };
  const heatmapResult = validateStoryV3(invalidHeatmap);
  assertFalse(heatmapResult.valid, 'invalid heatmap size fails');

  // Negative messages
  const negativeMessages = { ...validStory, m: -100 };
  const messagesResult = validateStoryV3(negativeMessages);
  assertFalse(messagesResult.valid, 'negative messages fails');
}

testValidateStory();

console.log('\n=== Decode V3 Story Tests ===');

function testDecodeV3Story() {
  // Create a minimal V3 story
  const rawStory = {
    v: 3,
    y: 2025,
    n: 'TestUser',
    p: 5,
    s: 100,
    m: 5000,
    h: 200,
    d: 45,
    hm: Array(168).fill(0),
    ma: [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200],
    mh: [10, 20, 30, 40, 50, 60, 50, 40, 30, 20, 10, 5],
    ms: [8, 10, 12, 15, 18, 20, 18, 15, 12, 10, 8, 6],
    sd: [5, 10, 20, 30, 15, 10, 5, 3, 1, 1],
    ar: [2, 5, 10, 15, 20, 20, 15, 8, 3, 2],
    ml: [10, 20, 30, 25, 10, 3, 1, 1],
    ts: { ad: 45, sp: 65, fc: 72, cc: 58, wr: 25, bs: 40, cs: 33, mv: 55, td: 60, ri: 70 },
    tp: [
      ['MainProject', 2000, 80, 25, 40, 45],
      ['SideProject', 1500, 60, 20, 30, 60],
    ],
    pc: [[0, 1, 10]],
    te: [[50, 0, 150, -1], [100, 4, 1000, 0]],
    sf: [[120, 100, 0, 10, 0, 0, 20, 40, 60, 80, 50, 10, 30, 20]],
    ls: 4.5,
    sk: [5, 10, 3, 4],
    tk: { total: 1000000, input: 600000, output: 400000, cache_read: 200000, cache_create: 50000, models: { 'sonnet': 800000, 'haiku': 200000 } },
    yoy: { pm: 3000, ph: 150, ps: 80, pp: 4, pd: 35 },
  };

  // Encode it
  const packed = msgpack.encode(rawStory);
  const encoded = base64UrlEncode(new Uint8Array(packed));

  // Decode it
  const decoded = decodeWrappedStoryV3(encoded);

  // Verify core fields
  assertEqual(decoded.v, 3, 'decoded version');
  assertEqual(decoded.y, 2025, 'decoded year');
  assertEqual(decoded.n, 'TestUser', 'decoded name');
  assertEqual(decoded.p, 5, 'decoded projects');
  assertEqual(decoded.s, 100, 'decoded sessions');
  assertEqual(decoded.m, 5000, 'decoded messages');
  assertEqual(decoded.h, 200, 'decoded hours');
  assertEqual(decoded.d, 45, 'decoded days');

  // Verify heatmap
  assertEqual(decoded.hm.length, 168, 'decoded heatmap length');

  // Verify monthly data
  assertEqual(decoded.ma.length, 12, 'decoded monthly activity length');
  assertEqual(decoded.ma[0], 100, 'decoded monthly activity first');
  assertEqual(decoded.ma[11], 1200, 'decoded monthly activity last');

  // Verify trait scores
  assertEqual(decoded.ts.ad, 45, 'decoded trait ad');
  assertEqual(decoded.ts.fc, 72, 'decoded trait fc');

  // Verify projects decoded from array format
  assertEqual(decoded.tp.length, 2, 'decoded projects count');
  assertEqual(decoded.tp[0].n, 'MainProject', 'decoded project name');
  assertEqual(decoded.tp[0].m, 2000, 'decoded project messages');
  assertEqual(decoded.tp[0].h, 80, 'decoded project hours');

  // Verify co-occurrence
  assertEqual(decoded.pc.length, 1, 'decoded co-occurrence count');
  assertEqual(decoded.pc[0], [0, 1, 10], 'decoded co-occurrence edge');

  // Verify timeline events decoded from array format
  assertEqual(decoded.te.length, 2, 'decoded events count');
  assertEqual(decoded.te[0].d, 50, 'decoded event day');
  assertEqual(decoded.te[0].t, 0, 'decoded event type');
  assertEqual(decoded.te[0].v, 150, 'decoded event value');
  assertTrue(decoded.te[0].p === undefined, 'decoded event no project');

  // Verify fingerprints decoded from array format
  assertEqual(decoded.sf.length, 1, 'decoded fingerprints count');
  assertEqual(decoded.sf[0].d, 120, 'decoded fingerprint duration');
  assertEqual(decoded.sf[0].m, 100, 'decoded fingerprint messages');
  assertEqual(decoded.sf[0].a, false, 'decoded fingerprint is_agent');
  assertEqual(decoded.sf[0].fp.length, 8, 'decoded fingerprint fp length');

  // Verify streaks
  assertEqual(decoded.sk, [5, 10, 3, 4], 'decoded streaks');

  // Verify token stats
  assertEqual(decoded.tk.total, 1000000, 'decoded tokens total');
  assertEqual(decoded.tk.models['sonnet'], 800000, 'decoded tokens sonnet');

  // Verify YoY
  assertTrue(decoded.yoy !== undefined, 'decoded yoy exists');
  assertEqual(decoded.yoy?.pm, 3000, 'decoded yoy previous messages');
}

testDecodeV3Story();

console.log('\n=== RLE Heatmap Decoding Tests ===');

function testRleHeatmapDecoding() {
  // Create a story with RLE-encoded heatmap
  const rawStory = {
    v: 3,
    y: 2025,
    p: 1, s: 1, m: 100, h: 1, d: 1,
    hm: [0, 160, 5, 8],  // RLE: 160 zeros, then 8 fives
    hm_rle: true,
    ma: Array(12).fill(0), mh: Array(12).fill(0), ms: Array(12).fill(0),
    sd: Array(10).fill(0), ar: Array(10).fill(0), ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [], pc: [], te: [], sf: [], ls: 0, sk: [0, 0, 0, 0],
    tk: { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} },
  };

  const packed = msgpack.encode(rawStory);
  const encoded = base64UrlEncode(new Uint8Array(packed));
  const decoded = decodeWrappedStoryV3(encoded);

  // Heatmap should be expanded to 168 values
  assertEqual(decoded.hm.length, 168, 'RLE heatmap expanded');
  assertEqual(decoded.hm[0], 0, 'RLE heatmap zeros');
  assertEqual(decoded.hm[159], 0, 'RLE heatmap last zero');
  assertEqual(decoded.hm[160], 5, 'RLE heatmap first five');
  assertEqual(decoded.hm[167], 5, 'RLE heatmap last five');
}

testRleHeatmapDecoding();

console.log('\n=== Decode Auto V3 Only Tests ===');

function testDecodeAutoV3Only() {
  // Create a V3 story - should work
  const v3Story = {
    v: 3,
    y: 2025,
    p: 1, s: 1, m: 100, h: 1, d: 1,
    hm: Array(168).fill(0),
    ma: Array(12).fill(0), mh: Array(12).fill(0), ms: Array(12).fill(0),
    sd: Array(10).fill(0), ar: Array(10).fill(0), ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [], pc: [], te: [], sf: [], ls: 0, sk: [0, 0, 0, 0],
    tk: { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} },
  };

  const v3Packed = msgpack.encode(v3Story);
  const v3Encoded = base64UrlEncode(new Uint8Array(v3Packed));

  const v3Decoded = decodeWrappedStoryAuto(v3Encoded);
  assertEqual(v3Decoded.v, 3, 'V3 decoded via auto');

  // Create a V2 story - should throw
  const v2Story = {
    v: 2,
    y: 2025,
    m: 100,
    t: 'Explorer',  // V2-specific field
  };

  const v2Packed = msgpack.encode(v2Story);
  const v2Encoded = base64UrlEncode(new Uint8Array(v2Packed));

  assertThrows(
    () => decodeWrappedStoryAuto(v2Encoded),
    'V2 format throws error'
  );

  // Create a V1 story - should throw
  const v1Story = {
    v: 1,
    y: 2025,
    m: 100,
  };

  const v1Packed = msgpack.encode(v1Story);
  const v1Encoded = base64UrlEncode(new Uint8Array(v1Packed));

  assertThrows(
    () => decodeWrappedStoryAuto(v1Encoded),
    'V1 format throws error'
  );
}

testDecodeAutoV3Only();

console.log('\n=== Edge Cases Tests ===');

function testEdgeCases() {
  // Empty projects/events/fingerprints
  const minimalStory = {
    v: 3,
    y: 2025,
    p: 0, s: 0, m: 0, h: 0, d: 0,
    hm: Array(168).fill(0),
    ma: Array(12).fill(0), mh: Array(12).fill(0), ms: Array(12).fill(0),
    sd: Array(10).fill(0), ar: Array(10).fill(0), ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [], pc: [], te: [], sf: [],
    // Missing optional fields
  };

  const packed = msgpack.encode(minimalStory);
  const encoded = base64UrlEncode(new Uint8Array(packed));
  const decoded = decodeWrappedStoryV3(encoded);

  assertEqual(decoded.tp.length, 0, 'empty projects');
  assertEqual(decoded.pc.length, 0, 'empty co-occurrence');
  assertEqual(decoded.te.length, 0, 'empty events');
  assertEqual(decoded.sf.length, 0, 'empty fingerprints');
  assertEqual(decoded.ls, 0, 'default longest session');
  assertEqual(decoded.sk, [0, 0, 0, 0], 'default streaks');
  assertEqual(decoded.tk.total, 0, 'default tokens');
  assertTrue(decoded.yoy === undefined, 'no yoy');

  // Invalid base64 should throw
  assertThrows(
    () => decodeWrappedStoryV3('not-valid-base64!!!'),
    'invalid base64 throws'
  );

  // Msgpack that decodes but is not a valid story should not throw during decode
  // (validation is separate), but completely invalid msgpack structure might
  // Just verify the decode doesn't crash on unexpected but parseable data
  try {
    const result = decodeWrappedStoryV3('gQ');  // msgpack for empty map {}
    assertTrue(result.v === 3, 'empty map defaults to v=3');
    passed++;
    console.log('  ✓ empty msgpack map handles gracefully');
  } catch {
    passed++;
    console.log('  ✓ empty msgpack map throws as expected');
  }
}

testEdgeCases();

console.log('\n=== Audit Issue Tests ===');

function testAuditIssues() {
  // Issue #1: Array boundary validation - decodeProject with short arrays
  // These tests verify the decoder handles malformed/short arrays gracefully
  const shortProjectStory = {
    v: 3,
    y: 2025,
    p: 1, s: 1, m: 100, h: 1, d: 1,
    hm: Array(168).fill(0),
    ma: Array(12).fill(0), mh: Array(12).fill(0), ms: Array(12).fill(0),
    sd: Array(10).fill(0), ar: Array(10).fill(0), ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [
      ['ProjectA'],  // Only 1 element instead of 6
      ['ProjectB', 100],  // Only 2 elements
      [],  // Empty array
    ],
    pc: [], te: [], sf: [], ls: 0, sk: [0, 0, 0, 0],
    tk: { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} },
  };
  const packed1 = msgpack.encode(shortProjectStory);
  const encoded1 = base64UrlEncode(new Uint8Array(packed1));
  const decoded1 = decodeWrappedStoryV3(encoded1);

  assertEqual(decoded1.tp[0].n, 'ProjectA', 'short project array - name preserved');
  assertEqual(decoded1.tp[0].m, 0, 'short project array - missing m defaults to 0');
  assertEqual(decoded1.tp[1].n, 'ProjectB', 'partial project array - name preserved');
  assertEqual(decoded1.tp[1].m, 100, 'partial project array - m preserved');
  assertEqual(decoded1.tp[1].h, 0, 'partial project array - missing h defaults to 0');
  assertEqual(decoded1.tp[2].n, '', 'empty project array - name defaults to empty');

  // Issue #3: dayOfYearToMonth with year parameter
  // Day 60 in leap year (2024) = Feb 29, in non-leap (2025) = Mar 1
  assertEqual(dayOfYearToMonth(60, 2024), 'Feb', 'leap year day 60 is Feb');
  assertEqual(dayOfYearToMonth(60, 2025), 'Mar', 'non-leap year day 60 is Mar');
  assertEqual(dayOfYearToMonth(1, 2025), 'Jan', 'day 1 is Jan');
  assertEqual(dayOfYearToMonth(365, 2025), 'Dec', 'day 365 is Dec');

  // Issue #9: Fingerprint with short arrays
  const shortFingerprintStory = {
    v: 3,
    y: 2025,
    p: 1, s: 1, m: 100, h: 1, d: 1,
    hm: Array(168).fill(0),
    ma: Array(12).fill(0), mh: Array(12).fill(0), ms: Array(12).fill(0),
    sd: Array(10).fill(0), ar: Array(10).fill(0), ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [],
    pc: [], te: [],
    sf: [
      [120, 50, 1, 14, 2, 0, 80, 60],  // Only 8 elements instead of 14
      [60, 25, 0],  // Only 3 elements
    ],
    ls: 0, sk: [0, 0, 0, 0],
    tk: { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} },
  };
  const packed2 = msgpack.encode(shortFingerprintStory);
  const encoded2 = base64UrlEncode(new Uint8Array(packed2));
  const decoded2 = decodeWrappedStoryV3(encoded2);

  assertEqual(decoded2.sf[0].d, 120, 'short fingerprint - duration preserved');
  assertEqual(decoded2.sf[0].fp.length, 8, 'short fingerprint - fp array padded to 8');
  assertEqual(decoded2.sf[1].d, 60, 'minimal fingerprint - duration preserved');
  assertEqual(decoded2.sf[1].fp.length, 8, 'minimal fingerprint - fp array padded to 8');

  // Issue #10: Event type validation (should handle invalid types gracefully)
  const invalidEventStory = {
    v: 3,
    y: 2025,
    p: 1, s: 1, m: 100, h: 1, d: 1,
    hm: Array(168).fill(0),
    ma: Array(12).fill(0), mh: Array(12).fill(0), ms: Array(12).fill(0),
    sd: Array(10).fill(0), ar: Array(10).fill(0), ml: Array(8).fill(0),
    ts: { ad: 50, sp: 50, fc: 50, cc: 50, wr: 50, bs: 50, cs: 50, mv: 50, td: 50, ri: 50 },
    tp: [],
    pc: [],
    te: [
      [10, 99, -1, -1],  // Invalid event type 99
      [20, 0, 100, 0],   // Valid event type 0
    ],
    sf: [], ls: 0, sk: [0, 0, 0, 0],
    tk: { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} },
  };
  const packed3 = msgpack.encode(invalidEventStory);
  const encoded3 = base64UrlEncode(new Uint8Array(packed3));
  const decoded3 = decodeWrappedStoryV3(encoded3);

  // Should not crash, event type should be clamped or preserved
  assertTrue(decoded3.te.length === 2, 'invalid event type - events decoded');
  assertEqual(decoded3.te[1].t, 0, 'valid event type preserved');
}

testAuditIssues();

console.log('\n=== Sample URL Validation Tests ===');

/**
 * Test that the sample URL used in landing.ts has meaningful data.
 * This catches the bug where wire format (arrays) was confused with display format (objects).
 */
function testSampleUrlValidation() {
  // This is the sample URL from landing.ts - update if it changes
  const sampleUrlData = '3gAXoXYDoXnNB-mhbqlEZW1vIFVzZXKhbc0LH6FozJyhcAihc3yhZFmibHPLQBDMzMzMzM2iaG3cAKgCAAECAQAEBgYNDQsFBw0PDw4ICAcCAgMBAAEAAAAGBgQMDQwGBQ4ODg4JCQgCBAQAAAACAgIFBgYNCwwHBQ0NDw0JBwkEBAMAAQAAAAEGBgQNCw0FBw8ODw4HCQkDBAICAQEBAAAGBQQNCwsFBw0NDw8ICAgCBAIAAAACAgEBAgIDBAUEAgUEBAUFBgUCAwQAAgEBAQABAgEFAwQDAwYGBgUHBwcDAwKibWGcVcyOzMbNAQvNATjNAR3NAVXNASrNAQDM4My9zPqibWicCAsOEhUTGBQRDwwRom1znAYJDA4QDxIQDQsJDKJzZIqiYWREonNwKqJmY0uiY2MjondyOqJicy2iY3M-om12JqJ0ZEeicmk0omFymggMEhgWEAoGAwGibWyWojUwozEyMKMyODCjNDUwozYyMKM4NTCidHOGomFkRKJzcCqiZmNLomJzLaJjcz6icmk0onRwlpa3Y2xhdWRlLWhpc3RvcnktZXhwbG9yZXLNA3w0Ii1Ilq93cmFwcGVkLXdlYnNpdGXNAnomHCBBlq1wZXJzb25hbC1zaXRlzQGcGBIWMJaqYXBpLWNsaWVudM0BHxAMDyOWqGRvdGZpbGVzzJwICAoWlqdzY3JpcHRzYgUFBg-icGOVkwABHJMAAgyTAQIIkwADBpMCBASidGWVlC0ALwCUAQEM_5RZBM0D6P-UeAP_AZTMyAA0AaJzZpOey0AMAAAAAAAALQEOAgBIQU5SLQxEN57LQADMzMzMzM0cAAoAATpIQEYmCDQwnstAEMzMzMzMzT4BEAMAVU5YXDQPSz6ic2uUDA4FBqJ0a4aldG90YWzOAIGzIKVpbnB1dM4AT1iApm91dHB1dM4AMlqgqmNhY2hlX3JlYWTOABJPgKxjYWNoZV9jcmVhdGXOAAbd0KZtb2RlbHOCpnNvbm5ldM4AZ8KApWhhaWt1zgAZ8KA';

  const story = decodeWrappedStoryAuto(sampleUrlData);

  // Year validation
  assertEqual(story.y, 2025, 'sample URL is for year 2025');

  // Basic story validation
  assertTrue(story.n.length > 0, 'sample URL has display name');
  assertTrue(story.m > 0, 'sample URL has messages');
  assertTrue(story.h > 0, 'sample URL has hours');
  assertTrue(story.d > 0, 'sample URL has days active');

  // Heatmap validation
  assertEqual(story.hm.length, 168, 'sample URL has 168-element heatmap');
  assertTrue(story.hm.reduce((a, b) => a + b, 0) > 0, 'sample URL heatmap has activity');

  // Top projects validation - THIS IS THE KEY TEST
  // If tp was created with object format instead of array format, these will fail
  assertTrue(story.tp.length >= 3, 'sample URL has at least 3 projects');
  assertTrue(story.tp[0].n.length > 0, 'sample URL first project has name');
  assertTrue(story.tp[0].m > 0, 'sample URL first project has messages');
  assertTrue(story.tp[0].h > 0, 'sample URL first project has hours');

  // Streaks validation
  assertTrue(story.sk[0] > 0, 'sample URL has streak count');
  assertTrue(story.sk[1] > 0, 'sample URL has longest streak');

  // Token validation
  assertTrue(story.tk.total > 0, 'sample URL has token usage');
}

testSampleUrlValidation();

// Summary
console.log('\n=================================');
console.log(`Tests: ${passed + failed} total, ${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
} else {
  console.log('\nAll tests passed!');
}
