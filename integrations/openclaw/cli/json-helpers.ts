/**
 * JSON output helpers for agent-friendly CLI commands.
 */

function writeStdout(data: Record<string, unknown>): void {
  process.stdout.write(JSON.stringify(data, null, 2) + "\n");
}

export function jsonOut(
  opts: { json?: boolean },
  data: Record<string, unknown>,
): boolean {
  if (!opts.json) return false;
  writeStdout(data);
  return true;
}

export function jsonErr(
  opts: { json?: boolean },
  error: string,
): boolean {
  if (!opts.json) return false;
  writeStdout({ ok: false, error });
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
