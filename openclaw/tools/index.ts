import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import type { Mem0Config, Mem0Provider, AddOptions, SearchOptions } from "../types.ts";
import type { Backend } from "../backend/base.ts";

import { createMemorySearchTool } from "./memory-search.ts";
import { createMemoryAddTool } from "./memory-add.ts";
import { createMemoryGetTool } from "./memory-get.ts";
import { createMemoryListTool } from "./memory-list.ts";
import { createMemoryUpdateTool } from "./memory-update.ts";
import { createMemoryDeleteTool } from "./memory-delete.ts";
import { createMemoryEventListTool } from "./memory-event-list.ts";
import { createMemoryEventStatusTool } from "./memory-event-status.ts";

export interface ToolDeps {
  api: OpenClawPluginApi;
  provider: Mem0Provider;
  cfg: Mem0Config;
  backend?: Backend;
  resolveUserId: (opts: { agentId?: string; userId?: string }) => string;
  effectiveUserId: (sessionKey?: string) => string;
  agentUserId: (id: string) => string;
  buildAddOptions: (userIdOverride?: string, runId?: string, sessionKey?: string) => AddOptions;
  buildSearchOptions: (userIdOverride?: string, limit?: number, runId?: string, sessionKey?: string) => SearchOptions;
  getCurrentSessionId: () => string | undefined;
  skillsActive: boolean;
  captureToolEvent: (toolName: string, properties: Record<string, unknown>) => void;
}

export function registerAllTools(deps: ToolDeps): void {
  const { api } = deps;

  api.registerTool(createMemorySearchTool(deps));
  api.registerTool(createMemoryAddTool(deps));
  api.registerTool(createMemoryGetTool(deps));
  api.registerTool(createMemoryListTool(deps));
  api.registerTool(createMemoryUpdateTool(deps));
  api.registerTool(createMemoryDeleteTool(deps));
  api.registerTool(createMemoryEventListTool(deps));
  api.registerTool(createMemoryEventStatusTool(deps));
}
