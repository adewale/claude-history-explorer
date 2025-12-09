/**
 * Decoder for Wrapped story data.
 * Decodes MessagePack + Base64URL encoded data from URLs.
 */

import msgpack from 'msgpack-lite';

export interface WrappedStory {
  y: number;      // year
  n?: string;     // display name
  p: number;      // projects
  s: number;      // sessions
  m: number;      // messages
  h: number;      // hours
  t: string[];    // traits
  c: string;      // collaboration style
  w: string;      // work pace
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
 * Decode a wrapped story from URL-safe encoded string
 */
export function decodeWrappedStory(encoded: string): WrappedStory {
  try {
    const bytes = base64UrlDecode(encoded);
    const data = msgpack.decode(bytes);
    return data as WrappedStory;
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
