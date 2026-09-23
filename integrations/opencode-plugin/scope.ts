import {
  normalizeScope,
  scopeAddParams,
  scopeSearchFilters as sharedSearchFilters,
  type Scope,
} from "../agent-plugin-core/typescript/src/scoping.ts";

export type { Scope };

const context = (userId: string, appId: string, runId: string, projectIds?: string[]) => ({
  userId,
  appId,
  runId,
  projectIds,
});

export function scopeSearchFilters(
  scope: Scope,
  userId: string,
  appId: string,
  runId: string,
  projectIds?: string[],
): Record<string, unknown> {
  return sharedSearchFilters(scope, context(userId, appId, runId, projectIds));
}

export function scopeWriteParams(
  scope: Scope,
  userId: string,
  appId: string,
  runId: string,
): { user_id: string; app_id?: string; run_id?: string } {
  const values = scopeAddParams(scope, context(userId, appId, runId));
  return {
    user_id: values.userId,
    ...(values.appId ? { app_id: values.appId } : {}),
    ...(values.runId ? { run_id: values.runId } : {}),
  };
}

export const asScope = normalizeScope;

export function resolveDefaultScope(settings: Record<string, unknown> | null | undefined): Scope {
  return normalizeScope(settings?.default_scope);
}

