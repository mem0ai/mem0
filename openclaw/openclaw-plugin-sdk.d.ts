declare module "openclaw/plugin-sdk" {
  export interface OpenClawPluginApi {
    pluginConfig: Record<string, unknown>;
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
