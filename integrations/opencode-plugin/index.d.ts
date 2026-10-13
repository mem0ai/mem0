import type {Plugin} from "@opencode-ai/plugin";

/**
 * Dual-shape module for OpenCode V1 and V2 (see opencode's V1->V2 migration guide):
 * - OpenCode V2 loaders decode the default export as `{ id, setup }` and call
 *   `setup(ctx)`.
 * - OpenCode V1 hosts (>= 1.18.29) pick the `server` key and call it as the V1
 *   plugin factory.
 */
export interface Mem0PluginModule {
  id: string;
  setup: (ctx: unknown) => Promise<void>;
  server: Plugin;
}

declare const Mem0PluginModule: Mem0PluginModule;
export default Mem0PluginModule;
