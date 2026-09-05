import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";
import type { Mem0Config, Mem0Provider, AddOptions, SearchOptions } from "../types.ts";
import type { Backend } from "../backend/base.ts";
import { isMemoryIdentitySelector, senderUserId, SenderIsolationError } from "../isolation.ts";
import { createSenderScopedProvider } from "../scoped-provider.ts";

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
  const nonOptional = { optional: false };
  const factories = [
    createMemorySearchTool, createMemoryAddTool, createMemoryGetTool,
    createMemoryListTool, createMemoryUpdateTool, createMemoryDeleteTool,
    createMemoryEventListTool, createMemoryEventStatusTool,
  ];

  if (deps.cfg.userIdScope === "per-sender") {
    for (const createTool of factories) {
      const name = createTool(deps).name;
      api.registerTool((ctx) => {
        // Copy primitives now; no shared session state or mutable host context.
        const sessionKey = ctx.sessionKey;
        const request = {
          senderId: ctx.requesterSenderId,
          channel: ctx.messageChannel,
          accountId: ctx.agentAccountId,
          agentId: ctx.agentId,
          sessionKey,
        };
        const getUserId = () => senderUserId(deps.cfg.userId, request);
        const requestDeps: ToolDeps = {
          ...deps,
          provider: createSenderScopedProvider(deps.provider, getUserId),
          resolveUserId: getUserId,
          effectiveUserId: getUserId,
          agentUserId: () => {
            throw new SenderIsolationError("agentId overrides are not allowed.");
          },
          getCurrentSessionId: () => sessionKey,
        };
        const tool = createTool(requestDeps);
        const properties: Record<string, unknown> = { ...tool.parameters.properties };
        delete properties.userId;
        delete properties.agentId;
        return {
          ...tool,
          description: tool.description +
            " In per-sender mode, userId and agentId overrides are not available.",
          parameters: { ...tool.parameters, properties },
          async execute(toolCallId, params) {
            try {
              getUserId();
              if ("userId" in params || "agentId" in params) {
                throw new SenderIsolationError("userId and agentId overrides are not allowed.");
              }
              if ((params.scope === "session" || params.longTerm === false) && !sessionKey) {
                throw new SenderIsolationError("session-scoped memory requires a request sessionKey.");
              }
              if (name === "memory_event_list" || name === "memory_event_status") {
                throw new SenderIsolationError(
                  "event tools are disabled because the backend event API is not sender-scoped.",
                );
              }
              const metadata = params.metadata;
              if (metadata && typeof metadata === "object" &&
                  Object.keys(metadata).some(isMemoryIdentitySelector)) {
                throw new SenderIsolationError("identity fields are not allowed in memory metadata.");
              }
              return await tool.execute(toolCallId, params);
            } catch (err) {
              if (!(err instanceof SenderIsolationError)) throw err;
              api.logger.warn(err.message);
              return {
                isError: true,
                content: [{ type: "text", text: err.message }],
                details: { error: err.message },
              };
            }
          },
        };
      }, { ...nonOptional, name });
    }
    return;
  }

  for (const createTool of factories) {
    api.registerTool(createTool(deps), nonOptional);
  }
}
