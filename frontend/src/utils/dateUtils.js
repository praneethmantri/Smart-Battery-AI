/**
 * Date and time formatting utilities for Smart Battery AI.
 * Converts backend UTC ISO-8601 datetimes to the user's browser-local timezone automatically.
 * NEVER manually hardcodes or adds timezone offsets.
 */

/**
 * Safely parses a UTC ISO-8601 timestamp into a native JavaScript Date.
 * If the input string is a valid ISO string without a timezone indicator,
 * treats it as UTC (appends 'Z') because all backend timestamps are stored in UTC.
 */
export function parseUtcDate(isoString) {
  if (!isoString) return null;
  if (isoString instanceof Date) return isNaN(isoString.getTime()) ? null : isoString;

  let s = String(isoString).trim();
  // If timestamp has no timezone designator (no 'Z' and no +HH:MM / -HH:MM),
  // append 'Z' so the browser's JavaScript Date engine interprets it as UTC, not local.
  if (!s.endsWith('Z') && !s.includes('+') && !/T.*[+-]\d{2}:?\d{2}$/.test(s)) {
    s += 'Z';
  }

  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Formats a UTC timestamp into browser-local time with date context:
 * - Today: "Today, 8:18 PM" (or "Today, 8:18:07 PM" when showSeconds=true)
 * - Yesterday: "Yesterday, 11:42 PM"
 * - Older dates: "09 Sep, 10:16 PM"
 *
 * @param {string|Date} timestamp - Backend UTC ISO timestamp
 * @param {Object} options
 * @param {boolean} [options.showSeconds=false] - Whether to include seconds
 * @param {boolean} [options.showDateContext=true] - Whether to include Today/Yesterday/Date prefix
 * @returns {string} Local formatted time string
 */
export function formatTelemetryTimestamp(timestamp, { showSeconds = false, showDateContext = true } = {}) {
  const date = parseUtcDate(timestamp);
  if (!date) return '--';

  const timeOptions = {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  };
  if (showSeconds) {
    timeOptions.second = '2-digit';
  }

  // Format in browser's local timezone
  let timeStr = date.toLocaleTimeString([], timeOptions);
  // Normalize AM/PM casing
  timeStr = timeStr.replace(/\b(am|pm)\b/gi, (m) => m.toUpperCase());

  if (!showDateContext) {
    return timeStr;
  }

  const now = new Date();
  const isToday =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  const isYesterday =
    date.getFullYear() === yesterday.getFullYear() &&
    date.getMonth() === yesterday.getMonth() &&
    date.getDate() === yesterday.getDate();

  if (isToday) {
    return `Today, ${timeStr}`;
  } else if (isYesterday) {
    return `Yesterday, ${timeStr}`;
  } else {
    const day = String(date.getDate()).padStart(2, '0');
    const month = date.toLocaleDateString([], { month: 'short' });
    return `${day} ${month}, ${timeStr}`;
  }
}

/**
 * Standard browser-local time formatter:
 * Conceptual format: "8:18 PM" or "20:18" (when hour12=false)
 */
export function formatLocalTime(timestamp, { hour12 = true, showSeconds = false, fallback = '--:--' } = {}) {
  const date = parseUtcDate(timestamp);
  if (!date) return fallback;

  let timeStr = date.toLocaleTimeString([], {
    hour: hour12 ? 'numeric' : '2-digit',
    minute: '2-digit',
    ...(showSeconds ? { second: '2-digit' } : {}),
    hour12,
  });
  return timeStr.replace(/\b(am|pm)\b/gi, (m) => m.toUpperCase());
}

/**
 * Formats a UTC timestamp into browser-local date: e.g. "09 Sep" or "Sep 10, 2026"
 */
export function formatLocalDate(timestamp, { includeYear = false, fallback = '-' } = {}) {
  const date = parseUtcDate(timestamp);
  if (!date) return fallback;

  const day = String(date.getDate()).padStart(2, '0');
  const month = date.toLocaleDateString([], { month: 'short' });
  if (includeYear) {
    return `${day} ${month} ${date.getFullYear()}`;
  }
  return `${day} ${month}`;
}
