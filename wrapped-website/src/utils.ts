/**
 * Shared utility functions for the wrapped website.
 *
 * These utilities are used across multiple pages to avoid duplication.
 */

/**
 * Escape HTML special characters to prevent XSS attacks.
 *
 * @param str - The string to escape
 * @returns The escaped string safe for HTML insertion
 */
export function escapeHtml(str: string): string {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Format a number with locale-specific thousands separators.
 *
 * @param num - The number to format
 * @returns The formatted string (e.g., "1,234,567")
 */
export function formatNumber(num: number): string {
  return num.toLocaleString('en-US');
}

/**
 * Format a duration in minutes to a human-readable string.
 *
 * @param minutes - Duration in minutes
 * @returns Formatted string (e.g., "2h 30m" or "45m")
 */
export function formatDurationMinutes(minutes: number): string {
  if (!minutes || minutes <= 0) return '?';
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

/**
 * Format a unix timestamp to a readable date string.
 *
 * @param timestamp - Unix timestamp in seconds
 * @param format - 'short' for "Dec 15" or 'long' for "Dec 15, 2024 10:30 AM"
 * @returns Formatted date string
 */
export function formatTimestamp(
  timestamp: number,
  format: 'short' | 'long' = 'short'
): string {
  if (!timestamp) return 'N/A';
  const date = new Date(timestamp * 1000);
  if (format === 'long') {
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/**
 * Generic validation result type.
 */
export interface ValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Create a successful validation result.
 */
export function validResult(): ValidationResult {
  return { valid: true };
}

/**
 * Create a failed validation result with an error message.
 */
export function invalidResult(error: string): ValidationResult {
  return { valid: false, error };
}
