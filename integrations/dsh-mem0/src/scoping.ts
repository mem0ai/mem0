/**
 * Per-call memory scoping.
 *
 * The plugin is mounted with one default `userId`, but a single harness install
 * can serve more than one entity, so both tools accept optional `userId` /
 * `agentId` / `runId` params that override the mount-time default per call.
 * A missing or blank param falls back to the configured user.
 *
 * The platform expects snake_case entity keys, and search takes them inside
 * `filters` while add takes them top-level. The resolved shape is snake_case so
 * it drops straight into both call sites (see index.ts).
 */

export interface EntityParams {
  userId?: string;
  agentId?: string;
  runId?: string;
}

export interface ResolvedEntity {
  user_id: string;
  agent_id?: string;
  run_id?: string;
}

function clean(value: string | undefined): string | undefined {
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}

export function resolveEntity(
  params: EntityParams,
  defaultUserId: string,
): ResolvedEntity {
  const entity: ResolvedEntity = {
    user_id: clean(params.userId) ?? defaultUserId,
  };
  const agentId = clean(params.agentId);
  if (agentId) entity.agent_id = agentId;
  const runId = clean(params.runId);
  if (runId) entity.run_id = runId;
  return entity;
}
