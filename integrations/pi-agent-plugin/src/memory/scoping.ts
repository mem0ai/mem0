import * as path from "node:path";
import * as crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import type { Scope, ScopeContext } from "../types.ts";
import {
  scopeAddParams,
  scopeSearchFilters,
} from "../../../agent-plugin-core/typescript/src/scoping.ts";

const WILDCARD_APP_ID = /^\*+$/;

/**
 * `MEM0_APP_ID` pins the project identity, so it wins over git-root detection.
 * This matters inside git worktrees, where `git rev-parse --show-toplevel`
 * returns the worktree path and would otherwise give the worktree its own
 * memory pool. Empty, whitespace-only and wildcard values are treated as unset
 * so they fall through to git detection instead of widening the scope filters.
 */
function configuredAppId(): string | undefined {
  const raw = process.env.MEM0_APP_ID;
  if (raw === undefined) return undefined;
  const trimmed = raw.trim();
  if (!trimmed || WILDCARD_APP_ID.test(trimmed)) return undefined;
  return raw;
}

export function detectAppId(cwd: string): string {
  const configured = configuredAppId();
  if (configured !== undefined) return configured;

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
