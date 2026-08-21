// Hand-maintained mirror of the OpenClaw plugin SDK surface this plugin
// uses. Keep shapes in sync with openclaw's src/plugins/memory-state.ts —
// an invented MemoryArtifact stub here is how record-shaped public
// artifacts shipped and crashed the gateway artifact sort.
declare module "openclaw/plugin-sdk" {
  export type MemoryPluginPublicArtifactContentType = "markdown" | "json" | "text";

  // Public artifacts are files on disk; every field below is required by
  // the gateway's artifact sort.
  export interface MemoryPluginPublicArtifact {
    kind: string;
    workspaceDir: string;
    relativePath: string;
    absolutePath: string;
    agentIds: string[];
    contentType: MemoryPluginPublicArtifactContentType;
  }

  export interface PublicArtifactsProvider {
    listArtifacts(params: { cfg: unknown }): Promise<MemoryPluginPublicArtifact[]>;
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
      definition: {
        name: string;
        description: string;
        parameters: unknown;
        execute: (
          toolCallId: string,
          params: Record<string, unknown>,
        ) => Promise<{ content: Array<{ type: string; text: string }>; [key: string]: unknown }>;
        [key: string]: unknown;
      },
      metadata?: { optional?: boolean; [key: string]: unknown },
    ): void;
    on(event: string, handler: (event: any, ctx: any) => any): void;
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
