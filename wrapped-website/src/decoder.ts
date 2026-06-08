/**
 * Decoder for Wrapped story data.
 * Decodes MessagePack + Base64URL encoded data from URLs.
 *
 * Only V3 (Tufte edition) format is supported.
 */

import msgpack from 'msgpack-lite';

// Re-export shared constants for backwards compatibility
export {
  EVENT_TYPES,
  EventType,
  TRAIT_LABELS,
  MOBILE_TRAITS,
  ALL_TRAITS,
  SESSION_DURATION_LABELS,
  AGENT_RATIO_LABELS,
  HEATMAP_QUANT_SCALE,
  TRAIT_LOW_THRESHOLD,
  TRAIT_HIGH_THRESHOLD,
  TRAIT_LOW_DESCRIPTIONS,
  TRAIT_HIGH_DESCRIPTIONS,
} from './constants';

import {
  EVENT_TYPES,
  type EventType,
  TRAIT_LOW_THRESHOLD,
  TRAIT_HIGH_THRESHOLD,
  TRAIT_LOW_DESCRIPTIONS,
  TRAIT_HIGH_DESCRIPTIONS,
  HEATMAP_QUANT_SCALE,
  HEATMAP_SIZE,
  HEATMAP_DAYS,
  HEATMAP_HOURS,
  MONTHS_SHORT,
  MAX_PROJECTS,
  MAX_COOCCURRENCE_EDGES,
  MAX_TIMELINE_EVENTS,
  MAX_SESSION_FINGERPRINTS,
  MAX_PROJECT_NAME_LENGTH,
  MAX_DISPLAY_NAME_LENGTH,
  TRAIT_CODES,
} from './constants';

const MAX_ENCODED_LENGTH = 100_000;
const MAX_DECODED_BYTES = 75_000;
const BASE64URL_RE = /^[A-Za-z0-9_-]+$/;

/**
 * Decode Base64URL string (without padding) to Uint8Array
 */
function base64UrlDecode(str: string): Uint8Array {
  if (!str || str.length > MAX_ENCODED_LENGTH || !BASE64URL_RE.test(str)) {
    throw new Error('Invalid or oversized encoded data');
  }

  // Add padding if needed
  const paddingNeeded = (4 - (str.length % 4)) % 4;
  const padded = str + '='.repeat(paddingNeeded);

  // Convert Base64URL to Base64
  const base64 = padded.replace(/-/g, '+').replace(/_/g, '/');

  // Decode
  const binaryString = atob(base64);
  if (binaryString.length > MAX_DECODED_BYTES) {
    throw new Error('Decoded data is too large');
  }
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

/**
 * Validate that the story data is well-formed (V3 format)
 * @deprecated Use validateStoryV3 instead
 */
export function validateStory(story: WrappedStoryV3): { valid: boolean; error?: string } {
  return validateStoryV3(story);
}

/**
 * Format a number with commas
 */
export function formatNumber(num: number): string {
  return num.toLocaleString('en-US');
}

/**
 * Get a descriptor for message count
 */
export function getMessageDescriptor(count: number): string {
  if (count > 50000) return "an extraordinary";
  if (count > 20000) return "a remarkable";
  if (count > 10000) return "an impressive";
  if (count > 5000) return "a substantial";
  if (count > 1000) return "a solid";
  return "a growing";
}

/**
 * Generate a sparkline from monthly data
 */
export function generateSparkline(data: number[]): string {
  if (!data || data.length === 0) return '';

  const chars = '▁▂▃▄▅▆▇█';
  const max = Math.max(...data);
  if (max === 0) return chars[0].repeat(data.length);

  return data.map(val => {
    const index = Math.round((val / max) * (chars.length - 1));
    return chars[index];
  }).join('');
}

// =============================================================================
// V3 Types and Interfaces
// =============================================================================

/**
 * V3 Top Project (decoded from compact array format)
 * Wire format: [name, messages, hours, days, sessions, agent_ratio]
 */
export interface TopProjectV3 {
  n: string;   // name
  m: number;   // messages
  h: number;   // hours (integer)
  d: number;   // days active
  s: number;   // sessions
  ar: number;  // agent ratio (0-100)
}

/**
 * V3 Timeline Event (decoded from compact array format)
 * Wire format: [day, type, value, project_idx] (-1 for missing values)
 */
export interface TimelineEvent {
  d: number;   // day of year (1-366)
  t: number;   // event type index
  v?: number;  // optional value (-1 means not present)
  p?: number;  // optional project index (-1 means not present)
}

/**
 * V3 Session Fingerprint (decoded from compact array format)
 * Wire format: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
 */
export interface SessionFingerprint {
  d: number;     // duration minutes
  m: number;     // message count
  a: boolean;    // is agent session
  h: number;     // start hour (0-23)
  w: number;     // day of week (0-6)
  pi: number;    // project index
  fp: number[];  // fingerprint (8 integers 0-100, quantized from 0.0-1.0)
}

/**
 * V3 Trait Scores (integers 0-100, quantized from 0.0-1.0)
 */
export interface TraitScores {
  ad: number;  // agent delegation (0=hands-on, 100=heavy delegation)
  sp: number;  // session depth (0=quick, 100=marathon)
  fc: number;  // focus concentration (0=scattered, 100=single-project)
  cc: number;  // circadian consistency (0=chaotic, 100=regular)
  wr: number;  // weekend ratio (0=weekday-only, 100=weekend-heavy)
  bs: number;  // burst vs steady (0=steady, 100=burst)
  cs: number;  // context-switching (0=focused, 100=switches often)
  mv: number;  // message verbosity (0=terse, 100=verbose)
  td: number;  // tool diversity (0=minimal, 100=many tools)
  ri: number;  // response intensity (0=light, 100=intense)
}

/**
 * V3 Year-over-Year comparison
 */
export interface YearOverYear {
  pm: number;  // previous year messages
  ph: number;  // previous year hours
  ps: number;  // previous year sessions
  pp: number;  // previous year projects
  pd: number;  // previous year days active
}

/**
 * V3 Wrapped Story with rich visualization data
 */
export interface WrappedStoryV3 {
  v: 3;           // version
  y: number;      // year
  n?: string;     // display name

  // Core counts
  p: number;      // total projects
  s: number;      // total sessions
  m: number;      // total messages
  h: number;      // total hours (integer)
  d: number;      // days active

  // Temporal data
  hm: number[];   // 7×24 heatmap (168 values)
  hm_rle?: boolean; // RLE flag (removed after decoding)
  ma: number[];   // monthly activity (12 values)
  mh: number[];   // monthly hours (12 integer values)
  ms: number[];   // monthly sessions (12 values)

  // Distributions
  sd: number[];   // session duration distribution (10 buckets)
  ar: number[];   // agent ratio distribution (10 buckets)
  ml: number[];   // message length distribution (8 buckets)

  // Trait scores
  ts: TraitScores;

  // Project data
  tp: TopProjectV3[];  // top projects (max 12)

  // Co-occurrence graph
  pc: [number, number, number][];  // [proj_a, proj_b, days]

  // Timeline events
  te: TimelineEvent[];

  // Session fingerprints
  sf: SessionFingerprint[];

  // Longest session (hours)
  ls: number;

  // Streak stats: [count, longest_days, current_days, avg_days]
  sk: number[];

  // Token stats
  tk: TokenStats;

  // Year-over-year (optional)
  yoy?: YearOverYear;
}

// Legacy type alias for backwards compatibility
// All new code should use WrappedStoryV3 directly
export type WrappedStory = WrappedStoryV3;

// Token usage statistics
export interface TokenStats {
  total: number;
  input: number;
  output: number;
  cache_read: number;
  cache_create: number;
  models: Record<string, number>;  // model name -> total tokens
}

// =============================================================================
// V3 Decoding Functions
// =============================================================================

/**
 * Decode run-length encoded data
 */
export function rleDecode(encoded: number[], maxOutput = Number.POSITIVE_INFINITY): number[] {
  if (!Array.isArray(encoded)) {
    throw new Error('Invalid RLE data');
  }
  const result: number[] = [];
  for (let i = 0; i < encoded.length; i += 2) {
    const value = encoded[i];
    const count = encoded[i + 1] ?? 1;
    if (!Number.isFinite(value) || !Number.isInteger(count) || count < 0) {
      throw new Error('Invalid RLE value or count');
    }
    if (result.length + count > maxOutput) {
      throw new Error('RLE heatmap exceeds expected size');
    }
    for (let j = 0; j < count; j++) {
      result.push(value);
    }
  }
  return result;
}

/**
 * Decode project array to object
 *
 * WIRE FORMAT: Array of 6 values [name, messages, hours, days, sessions, agent_ratio]
 * Example: ["my-project", 500, 40, 15, 20, 60]
 *
 * NOT objects! If you're creating test data manually, use arrays not {n: "...", m: ...}
 * The Python encoder (wrapped.py) creates this compact format for URL efficiency.
 */
function decodeProject(value: unknown): TopProjectV3 {
  // Validate input is actually an array (catches common mistake of using object format)
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const obj = value as Record<string, unknown>;
    return { n: (obj.n || '') as string, m: (obj.m || 0) as number, h: (obj.h || 0) as number, d: (obj.d || 0) as number, s: (obj.s || 0) as number, ar: (obj.ar || 0) as number };
  }
  const arr = Array.isArray(value) ? value : [];
  return {
    n: (arr[0] || '') as string,
    m: (arr[1] || 0) as number,
    h: (arr[2] || 0) as number,
    d: (arr[3] || 0) as number,
    s: (arr[4] || 0) as number,
    ar: (arr[5] || 0) as number,
  };
}

/**
 * Decode timeline event array to object
 *
 * WIRE FORMAT: Array of 4 values [day, type, value, project_idx] (-1 for missing)
 * Example: [45, 0, 47, 0] means "peak_day on day 45, value 47, project index 0"
 *
 * Types: 0=peak_day, 1=streak_start, 2=streak_end, 3=new_project, 4=milestone, 5=gap_start, 6=gap_end
 */
function decodeEvent(value: unknown): TimelineEvent {
  // Handle object format gracefully (for manually created test data)
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as TimelineEvent;
  }
  const arr = Array.isArray(value) ? value : [];
  const event: TimelineEvent = {
    d: (arr[0] || 0) as number,
    t: (arr[1] || 0) as number,
  };
  if (arr[2] !== -1 && arr[2] !== undefined) event.v = arr[2] as number;
  if (arr[3] !== -1 && arr[3] !== undefined) event.p = arr[3] as number;
  return event;
}

/**
 * Decode fingerprint array to object
 *
 * WIRE FORMAT: Array of 14 values [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
 * Example: [3.5, 45, 1, 14, 2, 0, 72, 65, 78, 82, 45, 12, 68, 55]
 *
 * fp0-fp7 are the session "shape" fingerprint values (0-100 each)
 */
function decodeFingerprint(value: unknown): SessionFingerprint {
  // Handle object format gracefully (for manually created test data)
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as SessionFingerprint;
  }
  const arr = Array.isArray(value) ? value : [];
  // Get fingerprint values, pad to 8 elements if needed
  const rawFp = arr.slice(6, 14) as number[];
  const fp = rawFp.length >= 8 ? rawFp : [...rawFp, ...Array(8 - rawFp.length).fill(0)];

  return {
    d: (arr[0] || 0) as number,
    m: (arr[1] || 0) as number,
    a: arr[2] === 1,
    h: (arr[3] || 0) as number,
    w: (arr[4] || 0) as number,
    pi: (arr[5] || 0) as number,
    fp,
  };
}

/**
 * Decode a V3 wrapped story from URL-safe encoded string
 */
export function decodeWrappedStoryV3(encoded: string): WrappedStoryV3 {
  try {
    const bytes = base64UrlDecode(encoded);
    const raw = msgpack.decode(bytes) as Record<string, unknown>;
    if (!raw || typeof raw !== 'object' || raw.v !== 3) {
      throw new Error(`Unsupported Wrapped version: ${raw?.v ?? 'missing'}`);
    }

    // RLE decode heatmap if flagged. Heatmaps are fixed 7×24 grids, so reject
    // compressed payloads that expand beyond or below that size.
    let heatmap = (Array.isArray(raw.hm) ? raw.hm : []) as number[];
    if (raw.hm_rle && raw.hm) {
      heatmap = rleDecode(raw.hm as number[], HEATMAP_SIZE);
    }
    if (heatmap.length !== HEATMAP_SIZE) {
      throw new Error(`Invalid heatmap size: ${heatmap.length}`);
    }

    // Decode compact array formats to objects
    const tp = (Array.isArray(raw.tp) ? raw.tp : []).map((item) => decodeProject(item));
    const te = (Array.isArray(raw.te) ? raw.te : []).map((item) => decodeEvent(item));
    const sf = (Array.isArray(raw.sf) ? raw.sf : []).map((item) => decodeFingerprint(item));

    return {
      v: raw.v,
      y: raw.y as number,
      n: typeof raw.n === 'string' ? raw.n : undefined,
      p: (raw.p || 0) as number,
      s: (raw.s || 0) as number,
      m: (raw.m || 0) as number,
      h: (raw.h || 0) as number,
      d: (raw.d || 0) as number,
      hm: heatmap,
      ma: (Array.isArray(raw.ma) ? raw.ma : []) as number[],
      mh: (Array.isArray(raw.mh) ? raw.mh : []) as number[],
      ms: (Array.isArray(raw.ms) ? raw.ms : []) as number[],
      // Early V3 sample URLs used legacy shapes for some optional visualization
      // fields (for example sd as a trait-score object and ml as string labels).
      // Normalize those unused legacy shapes to bounded defaults before the
      // strict runtime validator runs, matching the Python decoder.
      sd: numericArrayOrDefault(raw.sd, 10),
      ar: numericArrayOrDefault(raw.ar, 10),
      ml: numericArrayOrDefault(raw.ml, 8),
      ts: traitScoresOrDefault(raw.ts),
      tp,
      pc: (Array.isArray(raw.pc) ? raw.pc : []) as [number, number, number][],
      te,
      sf,
      ls: (raw.ls || 0) as number,
      sk: (Array.isArray(raw.sk) ? raw.sk : [0, 0, 0, 0]) as number[],
      tk: (raw.tk || { total: 0, input: 0, output: 0, cache_read: 0, cache_create: 0, models: {} }) as TokenStats,
      yoy: raw.yoy as YearOverYear | undefined,
    };
  } catch (error) {
    throw new Error(`Failed to decode V3 wrapped story: ${error}`);
  }
}

/**
 * Decode wrapped story (V3 format only)
 * Legacy V1/V2 formats are no longer supported.
 */
export function decodeWrappedStoryAuto(encoded: string): WrappedStoryV3 {
  try {
    return decodeWrappedStoryV3(encoded);
  } catch (error) {
    throw new Error(`Failed to decode wrapped story: ${error}`);
  }
}

/**
 * Check if a story is V3 format.
 * Since only V3 is now supported, this always returns true.
 * Kept for backwards compatibility with existing code.
 */
export function isV3Story(story: WrappedStoryV3): story is WrappedStoryV3 {
  return true;
}

/**
 * Get event type name from index
 */
export function getEventTypeName(typeIndex: number): EventType {
  return EVENT_TYPES[typeIndex] || 'peak_day';
}

// =============================================================================
// V3 Helper Functions
// =============================================================================

/**
 * Truncate string with ellipsis
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 1) + '…';
}

/**
 * Format a number with K/M suffix
 */
export function formatNumberCompact(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return n.toString();
}

/**
 * Format duration in minutes to human readable
 */
export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
}

/**
 * Get trait description for a score (0-100 integer scale)
 */
export function getTraitDescription(trait: string, score: number): string {
  // Uses shared constants from constants.ts
  if (score < TRAIT_LOW_THRESHOLD) {
    return TRAIT_LOW_DESCRIPTIONS[trait as keyof typeof TRAIT_LOW_DESCRIPTIONS] || 'Low';
  }
  if (score > TRAIT_HIGH_THRESHOLD) {
    return TRAIT_HIGH_DESCRIPTIONS[trait as keyof typeof TRAIT_HIGH_DESCRIPTIONS] || 'High';
  }
  return 'Balanced';
}

/**
 * Convert day of year to month name
 * @param dayOfYear - Day of year (1-366)
 * @param year - Year to use for leap year calculation (default: current year)
 */
export function dayOfYearToMonth(dayOfYear: number, year: number = new Date().getFullYear()): string {
  const date = new Date(year, 0, dayOfYear);
  return MONTHS_SHORT[date.getMonth()];
}

/**
 * Get heatmap value for a specific day and hour
 */
export function getHeatmapValue(heatmap: number[], day: number, hour: number): number {
  if (day < 0 || day >= HEATMAP_DAYS || hour < 0 || hour >= HEATMAP_HOURS) return 0;
  return heatmap[day * HEATMAP_HOURS + hour] || 0;
}

/**
 * Normalize a quantized fingerprint value (0-100) to 0.0-1.0 range
 */
export function normalizeFingerprint(value: number): number {
  return value / 100;
}

/**
 * Normalize all fingerprint values in a session fingerprint
 */
export function normalizeSessionFingerprint(fp: number[]): number[] {
  return fp.map(v => v / 100);
}

/**
 * Normalize a trait score (0-100) to 0.0-1.0 range
 */
export function normalizeTraitScore(value: number): number {
  return value / 100;
}

/**
 * Normalize all trait scores to 0.0-1.0 range
 */
export function normalizeTraitScores(ts: TraitScores): Record<string, number> {
  const result: Record<string, number> = {};
  for (const [key, value] of Object.entries(ts)) {
    result[key] = value / 100;
  }
  return result;
}

/**
 * Find peak time from heatmap
 */
export function findPeakTime(heatmap: number[]): { day: string; hour: number; value: number } {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  let maxValue = 0;
  let maxDay = 0;
  let maxHour = 0;

  for (let d = 0; d < 7; d++) {
    for (let h = 0; h < 24; h++) {
      const value = heatmap[d * 24 + h] || 0;
      if (value > maxValue) {
        maxValue = value;
        maxDay = d;
        maxHour = h;
      }
    }
  }

  return {
    day: days[maxDay],
    hour: maxHour,
    value: maxValue,
  };
}

/**
 * Calculate YoY percentage change
 */
export function calcYoyChange(current: number, previous: number): { value: number; direction: 'up' | 'down' | 'same' } {
  if (previous === 0) return { value: 0, direction: 'same' };
  const change = ((current - previous) / previous) * 100;
  return {
    value: Math.abs(Math.round(change)),
    direction: change > 0 ? 'up' : change < 0 ? 'down' : 'same',
  };
}

function isFiniteNumber(value: unknown, min = 0, max = Number.POSITIVE_INFINITY): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max;
}

function numericArrayOrDefault(value: unknown, length: number, defaultValue = 0): number[] {
  return Array.isArray(value) && value.length === length && value.every((item) => isFiniteNumber(item))
    ? value as number[]
    : Array(length).fill(defaultValue);
}

function traitScoresOrDefault(value: unknown): TraitScores {
  const rawScores = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  const scores: Record<string, unknown> = {};
  for (const code of TRAIT_CODES) {
    scores[code] = rawScores[code] === undefined ? 50 : rawScores[code];
  }
  return scores as unknown as TraitScores;
}

function validateNumberArray(name: string, value: unknown, length: number, max = Number.POSITIVE_INFINITY): string | null {
  if (!Array.isArray(value) || value.length !== length) return `Invalid ${name} size`;
  return value.every((item) => isFiniteNumber(item, 0, max)) ? null : `Invalid ${name} values`;
}

/**
 * Validate a V3 story
 */
export function validateStoryV3(story: WrappedStoryV3): { valid: boolean; error?: string } {
  if (!story || typeof story !== 'object' || story.v !== 3) {
    return { valid: false, error: 'Not a V3 story' };
  }
  const currentYear = new Date().getFullYear();
  if (!Number.isInteger(story.y) || story.y < 2024 || story.y > currentYear) {
    return { valid: false, error: `Invalid year: ${story.y}` };
  }

  for (const [name, value] of Object.entries({ p: story.p, s: story.s, m: story.m, h: story.h, d: story.d })) {
    if (!isFiniteNumber(value, 0)) return { valid: false, error: `Invalid ${name}` };
  }
  if (story.d > 366) return { valid: false, error: 'Invalid days active' };

  const arrayChecks = [
    validateNumberArray('heatmap', story.hm, HEATMAP_SIZE, HEATMAP_QUANT_SCALE),
    validateNumberArray('monthly activity', story.ma, 12),
    validateNumberArray('monthly hours', story.mh, 12),
    validateNumberArray('monthly sessions', story.ms, 12),
    validateNumberArray('session duration distribution', story.sd, 10),
    validateNumberArray('agent ratio distribution', story.ar, 10),
    validateNumberArray('message length distribution', story.ml, 8),
    validateNumberArray('streak stats', story.sk, 4),
  ].find(Boolean);
  if (arrayChecks) return { valid: false, error: arrayChecks };

  if (!story.ts || typeof story.ts !== 'object') {
    return { valid: false, error: 'Invalid trait scores' };
  }
  for (const code of TRAIT_CODES) {
    if (!isFiniteNumber((story.ts as unknown as Record<string, unknown>)[code], 0, 100)) {
      return { valid: false, error: `Invalid trait score: ${code}` };
    }
  }

  if (!Array.isArray(story.tp) || story.tp.length > MAX_PROJECTS) {
    return { valid: false, error: 'Invalid top projects' };
  }
  for (const project of story.tp) {
    if (!project || typeof project.n !== 'string' || project.n.length > MAX_PROJECT_NAME_LENGTH) return { valid: false, error: 'Invalid project name' };
    if (![project.m, project.h, project.d, project.s].every((value) => isFiniteNumber(value, 0))) return { valid: false, error: 'Invalid project stats' };
    if (!isFiniteNumber(project.ar, 0, 100)) return { valid: false, error: 'Invalid project agent ratio' };
  }

  if (!Array.isArray(story.pc) || story.pc.length > MAX_COOCCURRENCE_EDGES || !story.pc.every((edge) => Array.isArray(edge) && edge.length === 3 && edge.every((value) => isFiniteNumber(value, 0)))) {
    return { valid: false, error: 'Invalid project co-occurrence' };
  }
  if (!Array.isArray(story.te) || story.te.length > MAX_TIMELINE_EVENTS || !story.te.every((event) => event && isFiniteNumber(event.d, 1, 366) && isFiniteNumber(event.t, 0, EVENT_TYPES.length - 1) && (event.v === undefined || isFiniteNumber(event.v, 0)) && (event.p === undefined || isFiniteNumber(event.p, 0)))) {
    return { valid: false, error: 'Invalid timeline events' };
  }
  if (!Array.isArray(story.sf) || story.sf.length > MAX_SESSION_FINGERPRINTS || !story.sf.every((fp) => fp && isFiniteNumber(fp.d, 0) && isFiniteNumber(fp.m, 0) && typeof fp.a === 'boolean' && isFiniteNumber(fp.h, 0, 23) && isFiniteNumber(fp.w, 0, 6) && isFiniteNumber(fp.pi, 0) && validateNumberArray('fingerprint', fp.fp, 8, 100) === null)) {
    return { valid: false, error: 'Invalid session fingerprints' };
  }
  if (!isFiniteNumber(story.ls, 0)) {
    return { valid: false, error: 'Invalid longest session' };
  }
  if (story.n !== undefined && (typeof story.n !== 'string' || story.n.length > MAX_DISPLAY_NAME_LENGTH)) {
    return { valid: false, error: 'Invalid display name' };
  }
  if (!story.tk || typeof story.tk !== 'object') {
    return { valid: false, error: 'Invalid token stats' };
  }
  for (const value of [story.tk.total, story.tk.input, story.tk.output, story.tk.cache_read, story.tk.cache_create]) {
    if (!isFiniteNumber(value, 0)) return { valid: false, error: 'Invalid token count' };
  }
  if (!story.tk.models || typeof story.tk.models !== 'object') return { valid: false, error: 'Invalid token models' };
  for (const [model, tokens] of Object.entries(story.tk.models)) {
    if (model.length > 80 || !isFiniteNumber(tokens, 0)) return { valid: false, error: 'Invalid token model entry' };
  }

  return { valid: true };
}
