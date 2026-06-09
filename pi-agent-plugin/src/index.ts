export type {
  Scope,
  Mem0Config,
  DreamConfig,
  ScopeContext,
  CustomCategory,
} from "./types.ts";
export { DEFAULT_CUSTOM_CATEGORIES } from "./types.ts";

export { loadConfig, CONFIG_DIR } from "./config/index.ts";

export { registerMemoryTool, buildToolExecute } from "./memory/tools.ts";
export { detectAppId, detectRunId, resolveSearchFilters, resolveAddParams } from "./memory/scoping.ts";
export { formatAge, shortId, formatMemoryCompact, formatMemoryList, groupByCategory } from "./memory/formatting.ts";

export { setupAutoCapture, extractConversation } from "./capture/index.ts";

export {
  incrementSessionCount,
  checkCheapGates,
  checkMemoryGate,
  acquireDreamLock,
  releaseDreamLock,
  recordDreamCompletion,
} from "./dream/index.ts";
export { DREAM_PROTOCOL } from "./dream/prompt.ts";

export { MEMORY_POLICY } from "./prompt.ts";

export { registerCommands } from "./commands.ts";

export { default as mem0Extension } from "./entry.ts";
