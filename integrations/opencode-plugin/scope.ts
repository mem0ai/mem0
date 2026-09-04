import {
  normalizeScope,
  scopeAddParams,
  scopeSearchFilters as sharedSearchFilters,
  type Scope,
} from "../agent-plugin-core/typescript/src/scoping.ts";

export type { Scope };

const context = (userId: string, appId: string, runId: string) => ({ userId, appId, runId });

export function scopeSearchFilters(
  scope: Scope,
  userId: string,
  appId: string,
  runId: string,
): Record<string, string> {
  return sharedSearchFilters(scope, context(userId, appId, runId));
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

export const SCOPE_GUIDANCE =
  'Memory tools accept an optional `scope`: omit it (or "project") for normal queries; use "session" to limit to the current run; use "global" ONLY when the user explicitly asks to search across all their projects in this workspace.';
