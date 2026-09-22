export type Scope = "project" | "session" | "global";

export interface ScopeContext {
  userId: string;
  appId: string;
  runId: string;
}

export function normalizeScope(value: unknown): Scope {
  return value === "session" || value === "global" ? value : "project";
}

export function resolveToolScope(requested: Scope | undefined, configured: Scope): Scope {
  const scope = requested ?? configured;
  if (scope === "global" && configured !== "global") {
    throw new Error("Select global scope in the plugin settings or /mem0-scope command first.");
  }
  return scope;
}

function validateContext(scope: Scope, context: ScopeContext): void {
  const keys: (keyof ScopeContext)[] = ["userId"];
  if (scope !== "global") keys.push("appId");
  if (scope === "session") keys.push("runId");
  for (const key of keys) {
    if (!context[key]?.trim() || /^\*+$/.test(context[key].trim())) {
      throw new Error(`Invalid memory scope ${key}`);
    }
  }
}

export function scopeSearchFilters(scope: Scope, context: ScopeContext): Record<string, string> {
  validateContext(scope, context);
  if (scope === "session") {
    return { user_id: context.userId, app_id: context.appId, run_id: context.runId };
  }
  return scope === "global"
    ? { user_id: context.userId }
    : { user_id: context.userId, app_id: context.appId };
}

export function scopeAddParams(scope: Scope, context: ScopeContext): Record<string, string> {
  validateContext(scope, context);
  if (scope === "session") {
    return { userId: context.userId, appId: context.appId, runId: context.runId };
  }
  return scope === "global"
    ? { userId: context.userId }
    : { userId: context.userId, appId: context.appId };
}
