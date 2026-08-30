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

/**
 * Normalize `add({ timestamp })` to an ISO-8601 UTC string.
 *
 * A bare date means midnight UTC on that day. This is when the conversation
 * happened, which is what relative references in it resolve against and what
 * the memory's age is measured from. Same strictness as expiration dates: a
 * value `new Date()` would silently reinterpret is rejected instead.
 */
export function normalizeObservationTimestamp(
  value?: number | string | Date | null,
): string | undefined {
  if (value === undefined || value === null) return undefined;

  // The option type allows a number, but the Python SDK rejects epochs and the
  // two must agree on what a valid timestamp is.
  if (typeof value === "number") {
    throw new Error(
      "timestamp must be an ISO-8601 date or datetime, e.g. '2023-05-24'.",
    );
  }

  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) {
      throw new Error(
        "timestamp must be an ISO-8601 date or datetime, e.g. '2023-05-24'.",
      );
    }
    return value.toISOString();
  }

  if (EXPIRATION_DATE_PATTERN.test(value)) {
    return normalizeExpirationDate(value) + "T00:00:00.000Z";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(
      "timestamp must be an ISO-8601 date or datetime, e.g. '2023-05-24'.",
    );
  }
  return parsed.toISOString();
}

/** True when a later memory contradicted this one. */
export function payloadIsSuperseded(payload?: Record<string, any>): boolean {
  return Boolean(payload?.superseded_by);
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
