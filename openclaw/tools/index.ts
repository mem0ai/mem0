/**
 * Tool aggregator — single entry-point for registering all Mem0 tools.
 *
 * Re-exports the canonical `ToolContext` interface and provides
 * `registerAllTools(ctx)` which wires up every tool in one call.
 */

import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import type { Backend } from "../backend/base.ts";
import type {
  Mem0Config,
  Mem0Provider,
  AddOptions,
  SearchOptions,
} from "../types.ts";

// ---------------------------------------------------------------------------
// Canonical ToolContext definition
// ---------------------------------------------------------------------------

export interface ToolContext {
  api: OpenClawPluginApi;
  backend: Backend;
  cfg: Mem0Config;
  provider?: Mem0Provider;
  resolveUserId: (opts: { agentId?: string; userId?: string }) => string;
  effectiveUserId: (sessionKey?: string) => string;
  agentUserId: (id: string) => string;
  getCurrentSessionId: () => string | undefined;
  skillsActive: boolean;
  buildAddOptions: (
    userIdOverride?: string,
    runId?: string,
    sessionKey?: string,
  ) => AddOptions;
  buildSearchOptions: (
    userIdOverride?: string,
    limit?: number,
    runId?: string,
    sessionKey?: string,
  ) => SearchOptions;
}

// ---------------------------------------------------------------------------
// Tool factory imports
// ---------------------------------------------------------------------------

import { createMemorySearchTool } from "./memory-search.ts";
import { createMemoryStoreTool } from "./memory-store.ts";
import { createMemoryGetTool } from "./memory-get.ts";
import { createMemoryListTool } from "./memory-list.ts";
import { createMemoryUpdateTool } from "./memory-update.ts";
import { createMemoryDeleteTool } from "./memory-delete.ts";
import { createMemoryHistoryTool } from "./memory-history.ts";

// ---------------------------------------------------------------------------
// Aggregator
// ---------------------------------------------------------------------------

/**
 * Registers all Mem0 tools with the plugin API.
 *
 * 7 core tools for memory management:
 *   search, store, get, list, update, delete, history
 */
export function registerAllTools(ctx: ToolContext): void {
  const { api } = ctx;

  api.registerTool(createMemorySearchTool(ctx), { name: "memory_search" });
  api.registerTool(createMemoryStoreTool(ctx), { name: "memory_store" });
  api.registerTool(createMemoryGetTool(ctx), { name: "memory_get" });
  api.registerTool(createMemoryListTool(ctx), { name: "memory_list" });
  api.registerTool(createMemoryUpdateTool(ctx), { name: "memory_update" });
  api.registerTool(createMemoryDeleteTool(ctx), { name: "memory_delete" });
  api.registerTool(createMemoryHistoryTool(ctx), { name: "memory_history" });
}
