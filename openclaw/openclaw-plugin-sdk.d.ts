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
      definition: Record<string, unknown>,
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
}
