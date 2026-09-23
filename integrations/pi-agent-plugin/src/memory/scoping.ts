import * as crypto from "node:crypto";
import type { Scope, ScopeContext } from "../types.ts";
import {
  scopeAddParams,
  scopeSearchFilters,
} from "../../../agent-plugin-core/typescript/src/scoping.ts";

export function detectRunId(sessionFile: string | undefined): string {
  if (!sessionFile) return "unknown";
  return crypto.createHash("sha256").update(sessionFile).digest("hex").slice(0, 12);
}

export function resolveSearchFilters(
  scope: Scope,
  ctx: ScopeContext,
): Record<string, unknown> {
  return scopeSearchFilters(scope, ctx);
}

export function resolveAddParams(
  scope: Scope,
  ctx: ScopeContext,
): Record<string, string> {
  return scopeAddParams(scope, ctx);
}
