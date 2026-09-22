import * as path from "node:path";
import * as crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import type { Scope, ScopeContext } from "../types.ts";
import {
  scopeAddParams,
  scopeSearchFilters,
} from "../../../agent-plugin-core/typescript/src/scoping.ts";

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
  return scopeSearchFilters(scope, ctx);
}

export function resolveAddParams(
  scope: Scope,
  ctx: ScopeContext,
): Record<string, string> {
  return scopeAddParams(scope, ctx);
}
