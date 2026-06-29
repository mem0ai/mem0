/**
 * Memory scope resolution — ported from the pi-agent plugin's scoping model.
 *
 * Lets the agent choose, per memory operation, how wide to read/write:
 *   - "project" (default): this repo only        -> { user_id, app_id }
 *   - "session": this run only                   -> { user_id, app_id, run_id }
 *   - "global": across ALL of the user's projects -> { user_id, app_id: "*" }
 *
 * Mirrors pi-agent/src/memory/scoping.ts (resolveSearchFilters / resolveAddParams)
 * so the Kilo plugin exposes scope the same way: as a per-call tool parameter,
 * not a stateful "switch project" command.
 */

export type Scope = "project" | "session" | "global";

/** Filters for `search` / `get_memories` at the given scope. */
export function scopeSearchFilters(
  scope: Scope,
  userId: string,
  appId: string,
  runId: string,
): Record<string, string> {
  switch (scope) {
    case "session":
      return { user_id: userId, app_id: appId, run_id: runId };
    case "global":
      return { user_id: userId, app_id: "*" };
    case "project":
    default:
      return { user_id: userId, app_id: appId };
  }
}

/** Identity params for `add` / `delete_all` at the given scope. */
export function scopeWriteParams(
  scope: Scope,
  userId: string,
  appId: string,
  runId: string,
): { user_id: string; app_id?: string; run_id?: string } {
  switch (scope) {
    case "session":
      return { user_id: userId, app_id: appId, run_id: runId };
    case "global":
      return { user_id: userId };
    case "project":
    default:
      return { user_id: userId, app_id: appId };
  }
}

/** Normalize an arbitrary value to a valid Scope (defaults to "project"). */
export function asScope(value: unknown): Scope {
  return value === "session" || value === "global" ? value : "project";
}

/**
 * Resolve the persisted default scope from a parsed `~/.mem0/settings.json`
 * object. This is the user-changeable default applied to memory operations when
 * no explicit `scope` is passed (set via the `mem0-scope` skill). Falls back to
 * "project" when unset or invalid.
 */
export function resolveDefaultScope(
  settings: Record<string, unknown> | null | undefined,
): Scope {
  return asScope(settings?.default_scope);
}

/** Guidance injected so the agent uses `global` only when explicitly asked. */
export const SCOPE_GUIDANCE =
  'Memory tools accept an optional `scope`: omit it (or "project") for normal queries; use "session" to limit to the current run; use "global" ONLY when the user explicitly asks to search across all their projects in this workspace.';
