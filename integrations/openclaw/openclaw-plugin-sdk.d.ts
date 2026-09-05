declare module "openclaw/plugin-sdk" {
  // Relevant fields from upstream tool-types.ts, available since v2026.4.24.
  // https://github.com/openclaw/openclaw/blob/cbcfdf62c7297bda66009ea7476f053c3e9addab/src/plugins/tool-types.ts
  export interface OpenClawPluginToolContext {
    agentId?: string;
    sessionKey?: string;
    sessionId?: string;
    messageChannel?: string;
    agentAccountId?: string;
    requesterSenderId?: string;
  }

  interface AgentTool {
    name: string;
    description: string;
    parameters: unknown;
    execute: (
      toolCallId: string,
      params: Record<string, unknown>,
    ) => Promise<{ content: Array<{ type: string; text: string }>; [key: string]: unknown }>;
    [key: string]: unknown;
  }

  export type OpenClawPluginToolFactory = (
    ctx: OpenClawPluginToolContext,
  ) => AgentTool | AgentTool[] | null | undefined;

  // Relevant hook-types.ts fields at v2026.9.1. Identity remains optional:
  // v2026.4.24 and non-user runs do not supply senderId.
  // https://github.com/openclaw/openclaw/blob/ad6fe23aecb9b833d68139b0ddc9f239b894d2f1/src/plugins/hook-types.ts
  interface PluginHookAgentContext {
    agentId?: string;
    sessionKey?: string;
    sessionId?: string;
    runId?: string;
    channel?: string;
    messageProvider?: string;
    accountId?: string;
    senderId?: string;
    trigger?: string;
    channelId?: string;
  }

  export interface MemoryArtifact {
    id: string;
    type: "memory" | "dream" | "digest" | "entity";
    title: string;
    content: string;
    metadata?: Record<string, unknown>;
    createdAt?: string;
    updatedAt?: string;
  }

  export interface PublicArtifactsProvider {
    listArtifacts(options?: {
      userId?: string;
      types?: string[];
      limit?: number;
    }): Promise<MemoryArtifact[]>;
  }

  export interface MemoryCapabilityConfig {
    promptBuilder?: (ctx: any) => Promise<string | null>;
    flushPlanResolver?: (ctx: any) => Promise<any>;
    runtime?: Record<string, unknown>;
    publicArtifacts?: PublicArtifactsProvider;
  }

  export interface OpenClawPluginApi {
    pluginConfig: Record<string, unknown>;
    registrationMode?: "full" | "cli-metadata" | string;
    logger: {
      info(msg: string): void;
      warn(msg: string): void;
      error(msg: string): void;
      debug(msg: string): void;
    };
    resolvePath(p: string): string;
    registerTool(
      definition: AgentTool | OpenClawPluginToolFactory,
      metadata?: { optional?: boolean; [key: string]: unknown },
    ): void;
    on(
      event: "before_prompt_build",
      handler: (
        event: { prompt: string; messages: unknown[] },
        ctx: PluginHookAgentContext,
      ) => unknown,
    ): void;
    on(
      event: "agent_end",
      handler: (
        event: { messages: unknown[]; success: boolean; runId?: string },
        ctx: PluginHookAgentContext,
      ) => unknown,
    ): void;
    registerCli(
      handler: (context: { program: any }) => void,
      options?: Record<string, unknown>,
    ): void;
    registerCommand?(definition: Record<string, unknown>): void;
    registerService(service: {
      id: string;
      start: (...args: any[]) => void;
      stop: () => void;
    }): void;
    registerMemoryCapability?(config: MemoryCapabilityConfig): void;
    [key: string]: unknown;
  }
}

declare module "openclaw/plugin-sdk/plugin-entry" {
  import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
  export type {
    OpenClawPluginApi,
    OpenClawPluginToolContext,
    OpenClawPluginToolFactory,
  } from "openclaw/plugin-sdk";

  export interface PluginEntry {
    id: string;
    name: string;
    description?: string;
    register(api: OpenClawPluginApi): void;
  }

  export function definePluginEntry<T extends PluginEntry>(entry: T): T;
}

declare module "openclaw/plugin-sdk/core" {
  export * from "openclaw/plugin-sdk";
}
