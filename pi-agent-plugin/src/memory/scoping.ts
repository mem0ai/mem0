import * as path from "node:path";
import * as crypto from "node:crypto";
import type { Scope, ScopeContext } from "../types.ts";

export function detectAppId(cwd: string): string {
  return path.basename(cwd);
}

export function detectRunId(sessionFile: string | undefined): string {
  if (!sessionFile) return "unknown";
  return crypto.createHash("sha256").update(sessionFile).digest("hex").slice(0, 12);
}

export function resolveSearchFilters(
  scope: Scope,
  ctx: ScopeContext,
): Record<string, string> {
  switch (scope) {
    case "project":
      return { user_id: ctx.userId, app_id: ctx.appId };
    case "session":
      return { user_id: ctx.userId, app_id: ctx.appId, run_id: ctx.runId };
    case "user":
      return { user_id: ctx.userId };
    case "global":
      return {};
  }
}

export function resolveAddParams(
  scope: Scope,
  ctx: ScopeContext,
): Record<string, string> {
  switch (scope) {
    case "project":
      return { userId: ctx.userId, appId: ctx.appId };
    case "session":
      return { userId: ctx.userId, appId: ctx.appId, runId: ctx.runId };
    case "user":
      return { userId: ctx.userId };
    case "global":
      return {};
  }
}
