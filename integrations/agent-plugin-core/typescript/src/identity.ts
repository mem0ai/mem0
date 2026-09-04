export interface EntityParams {
  userId?: string;
  agentId?: string;
  runId?: string;
}

const clean = (value: string | undefined): string | undefined => value?.trim() || undefined;

export function entitySearchFilters(
  params: EntityParams,
  defaultUserId: string,
): Record<string, string> {
  const filters: Record<string, string> = { user_id: clean(params.userId) ?? defaultUserId };
  const agentId = clean(params.agentId);
  const runId = clean(params.runId);
  if (agentId) filters.agent_id = agentId;
  if (runId) filters.run_id = runId;
  return filters;
}

export function entityAddParams(params: EntityParams, defaultUserId: string): Record<string, string> {
  const values: Record<string, string> = { userId: clean(params.userId) ?? defaultUserId };
  const agentId = clean(params.agentId);
  const runId = clean(params.runId);
  if (agentId) values.agentId = agentId;
  if (runId) values.runId = runId;
  return values;
}

export function parseProjectFromRemote(remote: string): string | null {
  const match = remote.trim().match(/[:/]([^/:]+)\/([^/:]+?)(?:\.git)?\/?$/);
  return match ? `${match[1]}-${match[2]}` : null;
}
