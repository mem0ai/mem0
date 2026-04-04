import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import type { Mem0Config, Mem0Provider, AddOptions, SearchOptions } from "../types.ts";

import { createMemorySearchTool } from "./memory-search.ts";
import { createMemoryAddTool } from "./memory-add.ts";
import { createMemoryGetTool } from "./memory-get.ts";
import { createMemoryListTool } from "./memory-list.ts";
import { createMemoryUpdateTool } from "./memory-update.ts";
import { createMemoryDeleteTool } from "./memory-delete.ts";
import { createMemoryHistoryTool } from "./memory-history.ts";

export interface ToolDeps {
  api: OpenClawPluginApi;
  provider: Mem0Provider;
  cfg: Mem0Config;
  resolveUserId: (opts: { agentId?: string; userId?: string }) => string;
  effectiveUserId: (sessionKey?: string) => string;
  agentUserId: (id: string) => string;
  buildAddOptions: (userIdOverride?: string, runId?: string, sessionKey?: string) => AddOptions;
  buildSearchOptions: (userIdOverride?: string, limit?: number, runId?: string, sessionKey?: string) => SearchOptions;
  getCurrentSessionId: () => string | undefined;
  skillsActive: boolean;
}

export function registerAllTools(deps: ToolDeps): void {
  const { api } = deps;

  api.registerTool(createMemorySearchTool(deps), { name: "memory_search" });
  api.registerTool(createMemoryAddTool(deps), { name: "memory_add" });
  api.registerTool(createMemoryGetTool(deps), { name: "memory_get" });
  api.registerTool(createMemoryListTool(deps), { name: "memory_list" });
  api.registerTool(createMemoryUpdateTool(deps), { name: "memory_update" });
  api.registerTool(createMemoryDeleteTool(deps), { name: "memory_delete" });
  api.registerTool(createMemoryHistoryTool(deps), { name: "memory_history" });
}
