import * as path from "node:path";
import * as crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import type { Scope, ScopeContext } from "../types.ts";

export function detectAppId(cwd: string): string {
  try {
    const root = execFileSync("git", ["rev-parse", "--show-toplevel"], {
      cwd,
      encoding: "utf-8",
      timeout: 3000,
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return path.basename(root);
  } catch {
    return path.basename(cwd);
  }
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
    case "global":
      return { user_id: ctx.userId, app_id: "*" };
  }
}

// Reserved app_id for scope="global" adds. A memory written without an appId
// gets app_id: null, but resolveSearchFilters("global") uses a "*" wildcard,
// which only matches non-null values — so a null-tagged memory would never
// surface in a global search. Tagging it with this sentinel instead keeps it
// inside the wildcard's match set without widening what counts as "global"
// on the read side (which already correctly covers every real project's
// memories via the wildcard).
export const GLOBAL_APP_ID = "__global__";

export function resolveAddParams(
  scope: Scope,
  ctx: ScopeContext,
): Record<string, string> {
  switch (scope) {
    case "project":
      return { userId: ctx.userId, appId: ctx.appId };
    case "session":
      return { userId: ctx.userId, appId: ctx.appId, runId: ctx.runId };
    case "global":
      return { userId: ctx.userId, appId: GLOBAL_APP_ID };
  }
}
