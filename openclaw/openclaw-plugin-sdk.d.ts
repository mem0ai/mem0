declare module "openclaw/plugin-sdk/plugin-entry" {
  export interface OpenClawPluginToolContext {
    config?: Record<string, unknown>;
    workspaceDir?: string;
    agentDir?: string;
    agentId?: string;
    sessionKey?: string;
    sessionId?: string;
    messageChannel?: string;
    agentAccountId?: string;
    requesterSenderId?: string;
    senderIsOwner?: boolean;
    sandboxed?: boolean;
  }

  export type OpenClawPluginToolFactory =
    (ctx: OpenClawPluginToolContext) =>
      | Record<string, unknown>
      | Record<string, unknown>[]
      | null
      | undefined;

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
      definition: Record<string, unknown> | OpenClawPluginToolFactory,
      metadata?: Record<string, unknown>,
    ): void;
    on(
      event: string,
      handler: (event: any, ctx: any) => any,
    ): void;
    registerCli(
      handler: (context: { program: any }) => void,
      options?: Record<string, unknown>,
    ): void;
    registerService(service: {
      id: string;
      start: () => void;
      stop: () => void;
    }): void;
    [key: string]: unknown;
  }

  export interface OpenClawPluginDefinition {
    id: string;
    name: string;
    description: string;
    kind?: "memory" | "context-engine";
    configSchema?: Record<string, unknown>;
    register(api: OpenClawPluginApi): void;
  }

  export function definePluginEntry(
    definition: OpenClawPluginDefinition,
  ): OpenClawPluginDefinition;
}
