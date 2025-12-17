/**
 * Decoder for Wrapped story data.
 * Decodes MessagePack + Base64URL encoded data from URLs.
 *
 * Supports both v1 (strings) and v2 (indices) formats.
 */

import msgpack from 'msgpack-lite';

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
