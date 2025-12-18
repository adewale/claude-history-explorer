/**
 * Decoder for Wrapped story data.
 * Decodes MessagePack + Base64URL encoded data from URLs.
 *
 * Supports v1 (strings), v2 (indices), and v3 (Tufte edition) formats.
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
  HEATMAP_SIZE,
  HEATMAP_DAYS,
  HEATMAP_HOURS,
  MONTHS_SHORT,
  DAYS_SHORT,
} from './constants';

// Dictionaries for v2 index decoding - MUST stay in sync with Python history.py
const WRAPPED_TRAITS = [
  "Agent-driven",      // 0
  "Collaborative",     // 1
  "Hands-on",          // 2
  "Deep-work focused", // 3
  "Steady-paced",      // 4
  "Quick-iterative",   // 5
  "High-intensity",    // 6
  "Moderately active", // 7
  "Deliberate",        // 8
];

const WRAPPED_COLLAB_STYLES = [
  "Heavy delegation",  // 0
  "Balanced",          // 1
  "Hands-on",          // 2
  "Agent-only",        // 3
];

const WRAPPED_WORK_PACES = [
  "Rapid-fire",        // 0
  "Steady",            // 1
  "Deliberate",        // 2
  "Methodical",        // 3
];

export interface WrappedStory {
  v?: number;     // version (2 for indexed format)
  y: number;      // year
  n?: string;     // display name
  p: number;      // projects
  s: number;      // sessions
  m: number;      // messages
  h: number;      // hours
  d: number;      // days active (unique days with sessions)
  t: string[];    // traits (decoded from indices in v2)
  c: string;      // collaboration style (decoded from index in v2)
  w: string;      // work pace (decoded from index in v2)
  pp: string;     // peak project name
  pm: number;     // peak project messages
  ci: number;     // max concurrent instances
  ls: number;     // longest session hours
  a: number[];    // monthly activity (12 values)
  tp: TopProject[]; // top 3 projects
}

export interface TopProject {
  n: string;  // name
  m: number;  // messages
  d: number;  // days
}

/**
 * Decode Base64URL string (without padding) to Uint8Array
 */
function base64UrlDecode(str: string): Uint8Array {
  // Add padding if needed
  const paddingNeeded = (4 - (str.length % 4)) % 4;
  const padded = str + '='.repeat(paddingNeeded);

  // Convert Base64URL to Base64
  const base64 = padded.replace(/-/g, '+').replace(/_/g, '/');

  // Decode
  const binaryString = atob(base64);
  const bytes = new Uint8Array(binaryString.length);
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

/**
 * Decode a wrapped story from URL-safe encoded string.
 * Handles both v1 (strings) and v2 (indices) formats.
 */
export function decodeWrappedStory(encoded: string): WrappedStory {
  try {
    const bytes = base64UrlDecode(encoded);
    const raw = msgpack.decode(bytes);

    // Check version and decode indices if v2
    const version = raw.v || 1;

    let traits: string[];
    let collab: string;
    let pace: string;

    if (version >= 2) {
      // V2: decode indices to strings
      traits = (raw.t || []).map((t: number | string) => {
        if (typeof t === 'number' && t >= 0 && t < WRAPPED_TRAITS.length) {
          return WRAPPED_TRAITS[t];
        }
        return String(t);
      });

      if (typeof raw.c === 'number' && raw.c >= 0 && raw.c < WRAPPED_COLLAB_STYLES.length) {
        collab = WRAPPED_COLLAB_STYLES[raw.c];
      } else {
        collab = String(raw.c || '');
      }

      if (typeof raw.w === 'number' && raw.w >= 0 && raw.w < WRAPPED_WORK_PACES.length) {
        pace = WRAPPED_WORK_PACES[raw.w];
      } else {
        pace = String(raw.w || '');
      }
    } else {
      // V1: already strings
      traits = raw.t || [];
      collab = raw.c || '';
      pace = raw.w || '';
    }

    return {
      v: version,
      y: raw.y,
      n: raw.n,
      p: raw.p || 0,
      s: raw.s || 0,
      m: raw.m || 0,
      h: raw.h || 0,
      d: raw.d || 0,
      t: traits,
      c: collab,
      w: pace,
      pp: raw.pp || '',
      pm: raw.pm || 0,
      ci: raw.ci || 0,
      ls: raw.ls || 0,
      a: raw.a || [],
      tp: raw.tp || [],
    };
  } catch (error) {
    throw new Error(`Failed to decode wrapped story: ${error}`);
  }
}

/**
 * Validate that the story data is well-formed
 */
export function validateStory(story: WrappedStory): { valid: boolean; error?: string } {
  if (!story.y || typeof story.y !== 'number') {
    return { valid: false, error: 'Missing or invalid year' };
  }
  if (story.y < 2024 || story.y > new Date().getFullYear() + 1) {
    return { valid: false, error: `Invalid year: ${story.y}` };
  }
  if (typeof story.m !== 'number' || story.m < 0) {
    return { valid: false, error: 'Missing or invalid message count' };
  }
  return { valid: true };
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

  // Year-over-year (optional)
  yoy?: YearOverYear;
}

// =============================================================================
// V3 Decoding Functions
// =============================================================================

/**
 * Decode run-length encoded data
 */
export function rleDecode(encoded: number[]): number[] {
  const result: number[] = [];
  for (let i = 0; i < encoded.length; i += 2) {
    const value = encoded[i];
    const count = encoded[i + 1] || 1;
    for (let j = 0; j < count; j++) {
      result.push(value);
    }
  }
  return result;
}

/**
 * Decode project array to object
 * Wire format: [name, messages, hours, days, sessions, agent_ratio]
 */
function decodeProject(arr: any[]): TopProjectV3 {
  return {
    n: arr[0] || '',
    m: arr[1] || 0,
    h: arr[2] || 0,
    d: arr[3] || 0,
    s: arr[4] || 0,
    ar: arr[5] || 0,
  };
}

/**
 * Decode timeline event array to object
 * Wire format: [day, type, value, project_idx] (-1 for missing)
 */
function decodeEvent(arr: any[]): TimelineEvent {
  const event: TimelineEvent = {
    d: arr[0] || 0,
    t: arr[1] || 0,
  };
  if (arr[2] !== -1 && arr[2] !== undefined) event.v = arr[2];
  if (arr[3] !== -1 && arr[3] !== undefined) event.p = arr[3];
  return event;
}

/**
 * Decode fingerprint array to object
 * Wire format: [duration, messages, is_agent, hour, weekday, project_idx, fp0..fp7]
 */
function decodeFingerprint(arr: any[]): SessionFingerprint {
  return {
    d: arr[0] || 0,
    m: arr[1] || 0,
    a: arr[2] === 1,
    h: arr[3] || 0,
    w: arr[4] || 0,
    pi: arr[5] || 0,
    fp: arr.slice(6, 14),  // Elements 6-13 are fp0..fp7
  };
}

/**
 * Decode a V3 wrapped story from URL-safe encoded string
 */
export function decodeWrappedStoryV3(encoded: string): WrappedStoryV3 {
  try {
    const bytes = base64UrlDecode(encoded);
    const raw = msgpack.decode(bytes);

    // RLE decode heatmap if flagged
    let heatmap = raw.hm || [];
    if (raw.hm_rle && raw.hm) {
      heatmap = rleDecode(raw.hm);
    }

    // Decode compact array formats to objects
    const tp = (raw.tp || []).map((arr: any[]) => decodeProject(arr));
    const te = (raw.te || []).map((arr: any[]) => decodeEvent(arr));
    const sf = (raw.sf || []).map((arr: any[]) => decodeFingerprint(arr));

    return {
      v: 3,
      y: raw.y,
      n: raw.n,
      p: raw.p || 0,
      s: raw.s || 0,
      m: raw.m || 0,
      h: raw.h || 0,
      d: raw.d || 0,
      hm: heatmap,
      ma: raw.ma || [],
      mh: raw.mh || [],
      ms: raw.ms || [],
      sd: raw.sd || [],
      ar: raw.ar || [],
      ml: raw.ml || [],
      ts: raw.ts || {
        ad: 50, sp: 50, fc: 50, cc: 50, wr: 50,
        bs: 50, cs: 50, mv: 50, td: 50, ri: 50
      },
      tp,
      pc: raw.pc || [],
      te,
      sf,
      yoy: raw.yoy,
    };
  } catch (error) {
    throw new Error(`Failed to decode V3 wrapped story: ${error}`);
  }
}

/**
 * Detect version and decode appropriate format
 */
export function decodeWrappedStoryAuto(encoded: string): WrappedStory | WrappedStoryV3 {
  try {
    const bytes = base64UrlDecode(encoded);
    const raw = msgpack.decode(bytes);
    const version = raw.v || 1;

    if (version >= 3) {
      return decodeWrappedStoryV3(encoded);
    }
    return decodeWrappedStory(encoded);
  } catch (error) {
    throw new Error(`Failed to decode wrapped story: ${error}`);
  }
}

/**
 * Check if a story is V3 format
 */
export function isV3Story(story: WrappedStory | WrappedStoryV3): story is WrappedStoryV3 {
  return story.v === 3;
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
 */
export function dayOfYearToMonth(dayOfYear: number): string {
  const date = new Date(2024, 0, dayOfYear);
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

/**
 * Validate a V3 story
 */
export function validateStoryV3(story: WrappedStoryV3): { valid: boolean; error?: string } {
  if (story.v !== 3) {
    return { valid: false, error: 'Not a V3 story' };
  }
  if (!story.y || typeof story.y !== 'number') {
    return { valid: false, error: 'Missing or invalid year' };
  }
  if (story.y < 2024 || story.y > new Date().getFullYear() + 1) {
    return { valid: false, error: `Invalid year: ${story.y}` };
  }
  if (typeof story.m !== 'number' || story.m < 0) {
    return { valid: false, error: 'Missing or invalid message count' };
  }
  if (story.hm && story.hm.length !== 168) {
    return { valid: false, error: `Invalid heatmap size: ${story.hm.length} (expected 168)` };
  }
  return { valid: true };
}
