/**
 * Shared constants for Wrapped V3 encoding/decoding and visualization.
 *
 * These constants MUST stay in sync with:
 * - Python: claude_history_explorer/history.py
 * - Spec: docs/WRAPPED_V3_SPEC.md
 */

// =============================================================================
// Heatmap Constants
// =============================================================================

/** Number of days in heatmap (Monday=0 through Sunday=6) */
export const HEATMAP_DAYS = 7;

/** Number of hours in heatmap (0-23) */
export const HEATMAP_HOURS = 24;

/** Total cells in heatmap grid */
export const HEATMAP_SIZE = HEATMAP_DAYS * HEATMAP_HOURS; // 168

/** Index where weekend starts (Saturday = day 5) */
export const WEEKEND_START_DAY = 5;

/** Index where weekend ends inclusive (Sunday = day 6) */
export const WEEKEND_END_DAY = 6;

/** Quantization scale for heatmap values (0-15 for compact encoding) */
export const HEATMAP_QUANT_SCALE = 15;

// =============================================================================
// Distribution Bucket Constants
// =============================================================================

/** Session duration buckets in minutes: <15, 15-30, 30-60, 1-2h, 2-4h, 4-8h, 8-12h, 12-24h, 24-48h, >48h */
export const SESSION_DURATION_BUCKETS = [15, 30, 60, 120, 240, 480, 720, 1440, 2880];

/** Human-readable labels for session duration buckets */
export const SESSION_DURATION_LABELS = [
  '<15m', '15-30m', '30m-1h', '1-2h', '2-4h', '4-8h', '8-12h', '12-24h', '24-48h', '>48h'
];

/** Agent ratio buckets (0-1 scale): 0-10%, 10-20%, ..., 90-100% */
export const AGENT_RATIO_BUCKETS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];

/** Human-readable labels for agent ratio buckets */
export const AGENT_RATIO_LABELS = [
  '0-10%', '10-20%', '20-30%', '30-40%', '40-50%', '50-60%', '60-70%', '70-80%', '80-90%', '90-100%'
];

/** Message length buckets in characters */
export const MESSAGE_LENGTH_BUCKETS = [50, 100, 200, 500, 1000, 2000, 5000];

/** Human-readable labels for message length buckets */
export const MESSAGE_LENGTH_LABELS = [
  '<50', '50-100', '100-200', '200-500', '500-1k', '1-2k', '2-5k', '>5k'
];

// =============================================================================
// Event Types
// =============================================================================

/** Event type names indexed by type number */
export const EVENT_TYPES = [
  'peak_day',      // 0
  'streak_start',  // 1
  'streak_end',    // 2
  'new_project',   // 3
  'milestone',     // 4
  'gap_start',     // 5
  'gap_end',       // 6
] as const;

export type EventType = typeof EVENT_TYPES[number];

/** Human-readable event labels for display */
export const EVENT_LABELS: Record<number, string> = {
  0: 'Peak day',
  1: 'Streak started',
  2: 'Streak ended',
  3: 'New project',
  4: 'Milestone',
  5: 'Break started',
  6: 'Back at it',
};

/** Event icons for timeline display */
export const EVENT_ICONS: Record<number, string> = {
  0: '🔥', // peak_day
  1: '🚀', // streak_start
  2: '✅', // streak_end
  3: '🆕', // new_project
  4: '🏆', // milestone
  5: '😴', // gap_start
  6: '💪', // gap_end
};

// =============================================================================
// Trait Constants
// =============================================================================

/** Trait codes in canonical order */
export const TRAIT_CODES = ['ad', 'sp', 'fc', 'cc', 'wr', 'bs', 'cs', 'mv', 'td', 'ri'] as const;

export type TraitCode = typeof TRAIT_CODES[number];

/** Human-readable trait labels */
export const TRAIT_LABELS: Record<TraitCode, string> = {
  ad: 'Delegation',
  sp: 'Deep Work',
  fc: 'Focus',
  cc: 'Regularity',
  wr: 'Weekend',
  bs: 'Burst',
  cs: 'Switching',
  mv: 'Verbose',
  td: 'Tools',
  ri: 'Intensity',
};

/** Trait descriptions for low scores (< 33) */
export const TRAIT_LOW_DESCRIPTIONS: Record<TraitCode, string> = {
  ad: 'Hands-on',
  sp: 'Quick sessions',
  fc: 'Multi-project',
  cc: 'Flexible schedule',
  wr: 'Weekday focused',
  bs: 'Steady pace',
  cs: 'Deep focus',
  mv: 'Concise',
  td: 'Focused tools',
  ri: 'Light sessions',
};

/** Trait descriptions for high scores (> 67) */
export const TRAIT_HIGH_DESCRIPTIONS: Record<TraitCode, string> = {
  ad: 'Delegates heavily',
  sp: 'Marathon sessions',
  fc: 'Laser focused',
  cc: 'Regular schedule',
  wr: 'Weekend warrior',
  bs: 'Burst worker',
  cs: 'Context switcher',
  mv: 'Detailed',
  td: 'Tool explorer',
  ri: 'Intense sessions',
};

/** Thresholds for trait descriptions: low < 33, balanced 33-67, high > 67 */
export const TRAIT_LOW_THRESHOLD = 33;
export const TRAIT_HIGH_THRESHOLD = 67;

/** 6 key traits for mobile/compact display */
export const MOBILE_TRAITS: TraitCode[] = ['ad', 'sp', 'fc', 'cc', 'bs', 'ri'];

/** All 10 traits for desktop display */
export const ALL_TRAITS: TraitCode[] = [...TRAIT_CODES];

// =============================================================================
// Hard Limits
// =============================================================================

/** Maximum number of projects in encoded data */
export const MAX_PROJECTS = 12;

/** Maximum number of co-occurrence edges */
export const MAX_COOCCURRENCE_EDGES = 20;

/** Maximum number of timeline events */
export const MAX_TIMELINE_EVENTS = 25;

/** Maximum number of session fingerprints */
export const MAX_SESSION_FINGERPRINTS = 20;

/** Maximum length for project names */
export const MAX_PROJECT_NAME_LENGTH = 20;

/** Maximum length for display name */
export const MAX_DISPLAY_NAME_LENGTH = 30;

// =============================================================================
// Date/Time Constants
// =============================================================================

/** Short month names */
export const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Full month names */
export const MONTHS_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

/** Day names (Monday = 0) */
export const DAYS_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** Days in each month (non-leap year) */
export const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
