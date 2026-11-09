/**
 * Expiration date handling for memories.
 *
 * Memories may carry an `expiration_date` (YYYY-MM-DD) after which they are
 * hidden from `getAll()` and `search()` unless `showExpired` is set.
 */

const EXPIRATION_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * Normalize a user-supplied expiration date to a YYYY-MM-DD string.
 *
 * Deliberately stricter than `new Date(value)`, which accepts formats the
 * Python SDK rejects ("12/31/2099", "2099") and resolves them against the
 * local timezone, shifting the calendar day. It also silently rolls invalid
 * dates over — `new Date("2099-02-30T00:00:00Z")` yields March 2nd.
 */
export function normalizeExpirationDate(value: string): string {
  const match = EXPIRATION_DATE_PATTERN.exec(value);
  if (match) {
    const [, year, month, day] = match;
    const parsed = new Date(`${value}T00:00:00Z`);
    if (
      !Number.isNaN(parsed.getTime()) &&
      parsed.getUTCFullYear() === Number(year) &&
      parsed.getUTCMonth() === Number(month) - 1 &&
      parsed.getUTCDate() === Number(day)
    ) {
      return value;
    }
  }
  throw new Error("expirationDate must be a valid date in YYYY-MM-DD format.");
}

/** True when the payload carries an expiration date strictly before today (UTC). */
export function payloadIsExpired(
  payload: Record<string, any> | null | undefined,
) {
  const raw = payload?.expiration_date;
  if (!raw) return false;
  try {
    // YYYY-MM-DD sorts lexicographically the same way it sorts chronologically.
    return normalizeExpirationDate(String(raw)) < todayUtc();
  } catch {
    // Unparseable stored value: treat as non-expiring rather than hiding data.
    return false;
  }
}
