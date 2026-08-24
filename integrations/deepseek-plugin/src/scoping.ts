/**
 * Per-call memory scoping.
 *
 * The plugin is mounted with one default `userId`, but a single harness install
 * can serve more than one entity, so both tools accept optional `userId` /
 * `agentId` / `runId` params that override the mount-time default per call.
 * A missing or blank param falls back to the configured user.
 *
 * The two call sites need different key casing, and it is deliberate rather than
 * incidental: search passes scope inside `filters`, sent to the platform raw, so
 * it must be snake_case; add takes the entity params top-level, through the
 * SDK's camel->snake converter, so it must be camelCase. Keeping the split
 * explicit (like integrations/pi-agent-plugin/src/memory/scoping.ts) means the
 * asymmetry is visible in the code, not load-bearing on a converter no-op.
 */

export interface EntityParams {
  userId?: string;
  agentId?: string;
  runId?: string;
}

const clean = (v: string | undefined) => v?.trim() || undefined;

/** Search: snake_case, spread into `filters` and passed to the platform raw. */
export function resolveSearchFilters(
  params: EntityParams,
  defaultUserId: string,
): Record<string, string> {
  const filters: Record<string, string> = {
    user_id: clean(params.userId) ?? defaultUserId,
  };
  const agentId = clean(params.agentId);
  if (agentId) filters.agent_id = agentId;
  const runId = clean(params.runId);
  if (runId) filters.run_id = runId;
  return filters;
}

/** Add: camelCase, top-level params run through the SDK's camel->snake converter. */
export function resolveAddParams(
  params: EntityParams,
  defaultUserId: string,
): Record<string, string> {
  const out: Record<string, string> = {
    userId: clean(params.userId) ?? defaultUserId,
  };
  const agentId = clean(params.agentId);
  if (agentId) out.agentId = agentId;
  const runId = clean(params.runId);
  if (runId) out.runId = runId;
  return out;
}
