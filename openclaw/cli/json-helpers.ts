/**
 * JSON output helpers for agent-friendly CLI commands.
 *
 * When --json is passed, all output (success and error) goes to stdout
 * via console.log so agents parse a single stream.
 */

export function jsonOut(
  opts: { json?: boolean },
  data: Record<string, unknown>,
): boolean {
  if (!opts.json) return false;
  console.log(JSON.stringify(data, null, 2));
  return true;
}

export function jsonErr(
  opts: { json?: boolean },
  error: string,
): boolean {
  if (!opts.json) return false;
  console.log(JSON.stringify({ ok: false, error }, null, 2));
  return true;
}

export function redactSecrets(
  obj: Record<string, unknown>,
  secretKeys: Set<string>,
): Record<string, unknown> {
  const result = { ...obj };
  for (const key of secretKeys) {
    const val = result[key];
    if (typeof val !== "string") continue;
    result[key] = val.length <= 8
      ? val.slice(0, 2) + "***"
      : val.slice(0, 4) + "..." + val.slice(-4);
  }
  return result;
}
