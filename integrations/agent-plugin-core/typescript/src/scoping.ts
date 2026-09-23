export type Scope = "project" | "session" | "global";

export interface ScopeContext {
  userId: string;
  appId: string;
  runId: string;
  projectIds?: string[];
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
  const keys: Array<"userId" | "appId" | "runId"> = ["userId"];
  if (scope !== "global") keys.push("appId");
  if (scope === "session") keys.push("runId");
  for (const key of keys) {
    if (!context[key]?.trim() || /^\*+$/.test(context[key].trim())) {
      throw new Error(`Invalid memory scope ${key}`);
    }
  }
}

export function scopeSearchFilters(scope: Scope, context: ScopeContext): Record<string, unknown> {
  validateContext(scope, context);
  if (scope === "global") return { user_id: context.userId };
  const projectIds = context.projectIds?.filter((id) => id.trim() && !/^\*+$/.test(id.trim())) ?? [];
  if (!projectIds.length) {
    return scope === "session"
      ? { user_id: context.userId, app_id: context.appId, run_id: context.runId }
      : { user_id: context.userId, app_id: context.appId };
  }
  const app = { app_id: context.appId };
  const lanes = projectIds.map((id) => ({ AND: [{ agent_id: id }, app] }));
  const repo = {
    OR: [lanes.length === 1 ? lanes[0] : { OR: lanes }, { AND: [{ user_id: context.userId }, app] }],
  };
  return scope === "session" ? { AND: [repo, { run_id: context.runId }] } : repo;
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
