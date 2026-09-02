export type Scope = "project" | "session" | "global";

export interface ScopeContext {
  userId: string;
  appId: string;
  runId: string;
}

export function normalizeScope(value: unknown): Scope {
  return value === "session" || value === "global" ? value : "project";
}

export function scopeSearchFilters(scope: Scope, context: ScopeContext): Record<string, string> {
  if (scope === "session") {
    return { user_id: context.userId, app_id: context.appId, run_id: context.runId };
  }
  return scope === "global"
    ? { user_id: context.userId, app_id: "*" }
    : { user_id: context.userId, app_id: context.appId };
}

export function scopeAddParams(scope: Scope, context: ScopeContext): Record<string, string> {
  if (scope === "session") {
    return { userId: context.userId, appId: context.appId, runId: context.runId };
  }
  return scope === "global"
    ? { userId: context.userId }
    : { userId: context.userId, appId: context.appId };
}
