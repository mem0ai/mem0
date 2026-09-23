/**
 * OpenClaw Memory (Mem0) Plugin
 *
 * Long-term memory via Mem0 — supports both the Mem0 platform
 * and the open-source self-hosted SDK. Uses the official `mem0ai` package.
 *
 * Features:
 * - 6 core tools: memory_search, memory_add, memory_get, memory_list,
 *   memory_update, memory_delete
 * - Short-term (session-scoped) and long-term (user-scoped) memory
 * - Auto-recall: injects relevant long-term memories once per session, on the first prompt
 * - Auto-capture: sends each turn's prompt and reply at checkpoints and when the session ends
 * - Per-agent isolation: multi-agent setups write/read from separate userId namespaces
 *   automatically via sessionKey routing (zero breaking changes for single-agent setups)
 * - CLI: openclaw mem0 search, openclaw mem0 status
 * - Dual mode: platform or open-source (self-hosted)
 */

import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

import type {
  Mem0Config,
  Mem0Provider,
  AddOptions,
  SearchOptions,
} from "./types.ts";
import {
  createProvider,
  customCategoryMapToList,
  providerToBackend,
} from "./providers.ts";
import { mem0ConfigSchema } from "./config.ts";
import type { FileConfig } from "./config.ts";
import { createPublicArtifactsProvider } from "./public-artifacts.ts";
import {
  effectiveUserId,
  agentUserId,
  resolveUserId,
  isNonInteractiveTrigger,
  isSubagentSession,
} from "./isolation.ts";
import {
  loadCompactTriagePrompt,
  isSkillsMode,
} from "./skill-loader.ts";
import { recall as skillRecall, sanitizeQuery } from "./recall.ts";
import { PlatformBackend } from "./backend/platform.ts";
import type { Backend } from "./backend/base.ts";
import { registerCliCommands } from "./cli/commands.ts";
import { readPluginAuth } from "./cli/config-file.ts";
import { registerAllTools } from "./tools/index.ts";
import type { ToolDeps } from "./tools/index.ts";
import { captureEvent } from "./telemetry.ts";
import {
  createMemoryLifecycle,
  type ConversationMessage,
} from "../agent-plugin-core/typescript/src/lifecycle.ts";
import { USER_RECALL_HEADING } from "../agent-plugin-core/typescript/src/prompts.ts";
import { bootstrapTelemetryFlag } from "./fs-safe.ts";

// ============================================================================
// Re-exports (for tests and external consumers)
// ============================================================================

export {
  extractAgentId,
  effectiveUserId,
  agentUserId,
  resolveUserId,
  isNonInteractiveTrigger,
  isSubagentSession,
} from "./isolation.ts";
export {
  isNoiseMessage,
  isGenericAssistantMessage,
  isSessionSpecificContent,
  stripNoiseFromContent,
  filterMessagesForExtraction,
} from "./filtering.ts";
export { mem0ConfigSchema } from "./config.ts";
export type { FileConfig } from "./config.ts";
export { createProvider } from "./providers.ts";

// ============================================================================
// Helpers
// ============================================================================

// ============================================================================
// Plugin Definition
// ============================================================================

const memoryPlugin = definePluginEntry({
  id: "openclaw-mem0",
  name: "Memory (Mem0)",
  description: "Mem0 memory backend — Mem0 platform or self-hosted open-source",

  register(api: OpenClawPluginApi) {
    bootstrapTelemetryFlag();

    // Read auth from openclaw.json plugin config (picks up post-startup login).
    // This is the single source of truth — set via `openclaw mem0 login`.
    const pluginAuth = readPluginAuth();
    const fileConfig: FileConfig = {
      apiKey: pluginAuth.apiKey,
      baseUrl: pluginAuth.baseUrl,
    };
    const cfg = mem0ConfigSchema.parse(api.pluginConfig, fileConfig);
    const isMetadataRegistration = api.registrationMode === "cli-metadata";

    // Telemetry context bound to this plugin instance's config
    const telemetryCtx = {
      apiKey: cfg.apiKey,
      mode: cfg.mode,
      skillsActive: false,
    };
    const _captureEvent = (event: string, props?: Record<string, unknown>) => {
      try {
        captureEvent(event, props, telemetryCtx);
      } catch {
        /* silently swallow */
      }
    };

    if (isMetadataRegistration) {
      registerCliCommands(
        api,
        null as any,
        null as any,
        cfg,
        () => cfg.userId,
        (id: string) => `${cfg.userId}:agent:${id}`,
        () => ({ user_id: cfg.userId, top_k: cfg.topK }),
        () => undefined,
        (cmd: string) => _captureEvent(`openclaw.cli.${cmd}`, { command: cmd }),
      );
      return;
    }

    if (cfg.needsSetup) {
      api.logger.warn(
        "openclaw-mem0: API key not configured. Memory features are disabled.\n" +
          "  To set up, run:\n" +
          "  openclaw mem0 init\n" +
          "  Get your key at: https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=openclaw-src",
      );

      // Register CLI even without API key — init command must be available
      // to bootstrap configuration. Pass nulls for backend/provider since
      // only the init subcommand works without auth.
      registerCliCommands(
        api,
        null as any,
        null as any,
        cfg,
        () => cfg.userId,
        (id: string) => `${cfg.userId}:agent:${id}`,
        () => ({ user_id: cfg.userId, top_k: cfg.topK }),
        () => undefined,
        (cmd: string) => _captureEvent(`openclaw.cli.${cmd}`, { command: cmd }),
      );

      api.registerService({
        id: "openclaw-mem0",
        start: () => {
          api.logger.info("openclaw-mem0: waiting for API key configuration");
        },
        stop: () => {},
      });
      return;
    }

    const provider = createProvider(cfg, api);
    const lifecycle = createMemoryLifecycle();
    lifecycle.beginSession();

    // Create Backend instance — PlatformBackend for platform mode, providerToBackend adapter for OSS
    let backend: Backend;
    if (cfg.mode === "platform") {
      backend = new PlatformBackend({
        apiKey: cfg.apiKey!,
        baseUrl: cfg.baseUrl ?? "https://api.mem0.ai",
      });
    } else {
      backend = providerToBackend(provider, cfg.userId);
    }

    // Shared mutable state — declared together before any closures capture them.
    let currentSessionId: string | undefined;
    let pluginStateDir: string | undefined;

    // ========================================================================
    // Per-agent isolation helpers (thin wrappers around exported functions)
    // ========================================================================
    const _effectiveUserId = (sessionKey?: string) =>
      effectiveUserId(cfg.userId, sessionKey);
    const _agentUserId = (id: string) => agentUserId(cfg.userId, id);
    const _resolveUserId = (opts: { agentId?: string; userId?: string }) =>
      resolveUserId(cfg.userId, opts, currentSessionId);

    const skillsActive = isSkillsMode(cfg.skills);
    telemetryCtx.skillsActive = skillsActive;

    _captureEvent("openclaw.plugin.registered", {
      auto_recall: cfg.autoRecall,
      auto_capture: cfg.autoCapture,
    });

    api.logger.info(
      `openclaw-mem0: registered (mode: ${cfg.mode}, user: ${cfg.userId}, autoRecall: ${cfg.autoRecall}, autoCapture: ${cfg.autoCapture}, skills: ${skillsActive})`,
    );

    // ========================================================================
    // Public Artifacts (for memory-wiki bridge mode)
    // ========================================================================
    if (typeof api.registerMemoryCapability === "function") {
      api.registerMemoryCapability({
        publicArtifacts: createPublicArtifactsProvider({
          provider,
          effectiveUserId: _effectiveUserId,
        }),
        runtime: {
          async getMemorySearchManager(_params: any) {
            try {
              const userId = _effectiveUserId();
              let memoryCount = 0;
              try {
                const memories = await provider.getAll({
                  user_id: userId,
                  page_size: 1,
                  source: "OPENCLAW",
                });
                memoryCount = Array.isArray(memories) ? memories.length : 0;
              } catch {
                // Non-fatal: status still works without count
              }
              return {
                manager: {
                  status() {
                    return {
                      backend: cfg.mode,
                      files: 0,
                      chunks: memoryCount,
                      dirty: false,
                      workspaceDir: pluginStateDir ?? "",
                      userId,
                    };
                  },
                  async probeEmbeddingAvailability() {
                    return { ok: true };
                  },
                  async close() {},
                },
              };
            } catch (err) {
              return {
                manager: null,
                error: `mem0 ${cfg.mode} backend unavailable: ${String(err)}`,
              };
            }
          },
          resolveMemoryBackendConfig(_params: any) {
            return {
              backend: cfg.mode,
              baseUrl: cfg.baseUrl ?? "https://api.mem0.ai",
              userId: cfg.userId,
            };
          },
          async closeAllMemorySearchManagers() {},
        },
      });
      api.logger.debug("openclaw-mem0: memory capability + runtime registered");
    }

    // Helper: build add options
    function buildAddOptions(
      userIdOverride?: string,
      runId?: string,
      sessionKey?: string,
    ): AddOptions {
      // v3.0.0: removed output_format, customPrompt renamed to customInstructions
      const opts: AddOptions = {
        user_id: userIdOverride || _effectiveUserId(sessionKey),
        source: "OPENCLAW",
      };
      if (runId) opts.run_id = runId;
      // Pass customInstructions and customCategories to control what Mem0 extracts
      if (cfg.customInstructions) opts.custom_instructions = cfg.customInstructions;
      const customCategories = customCategoryMapToList(cfg.customCategories);
      if (customCategories) opts.custom_categories = customCategories;
      return opts;
    }

    // Helper: build search options (skills config overrides legacy defaults)
    // v3.0.0: removed keyword_search, reranking, filter_memories, limit
    function buildSearchOptions(
      userIdOverride?: string,
      limit?: number,
      runId?: string,
      sessionKey?: string,
    ): SearchOptions {
      const recallCfg = cfg.skills?.recall;
      const opts: SearchOptions = {
        user_id: userIdOverride || _effectiveUserId(sessionKey),
        top_k: limit ?? cfg.topK,
        threshold: recallCfg?.threshold ?? cfg.searchThreshold,
        source: "OPENCLAW",
      };
      if (runId) opts.run_id = runId;
      return opts;
    }

    // ========================================================================
    // Tools (modular — each tool in its own file under tools/)
    // ========================================================================

    const toolDeps: ToolDeps = {
      api,
      provider,
      cfg,
      backend,
      resolveUserId: _resolveUserId,
      effectiveUserId: _effectiveUserId,
      agentUserId: _agentUserId,
      buildAddOptions,
      buildSearchOptions,
      getCurrentSessionId: () => currentSessionId,
      skillsActive,
      captureToolEvent: (toolName: string, props: Record<string, unknown>) => {
        _captureEvent(`openclaw.tool.${toolName}`, {
          tool_name: toolName,
          ...props,
        });
      },
    };
    registerAllTools(toolDeps);

    // ========================================================================
    // CLI Commands
    // ========================================================================

    registerCliCommands(
      api,
      backend,
      provider,
      cfg,
      _effectiveUserId,
      _agentUserId,
      buildSearchOptions,
      () => currentSessionId,
      (cmd: string) => _captureEvent(`openclaw.cli.${cmd}`, { command: cmd }),
    );

    // ========================================================================
    // Lifecycle Hooks
    // ========================================================================

    registerHooks(
      api,
      provider,
      cfg,
      _effectiveUserId,
      buildAddOptions,
      buildSearchOptions,
      {
        setCurrentSessionId: (id: string) => {
          currentSessionId = id;
        },
      },
      skillsActive,
      _captureEvent,
      lifecycle,
    );

    // ========================================================================
    // Service
    // ========================================================================

    api.registerService({
      id: "openclaw-mem0",
      start: (...args: any[]) => {
        pluginStateDir = args[0]?.stateDir;
        api.logger.info(
          `openclaw-mem0: initialized (mode: ${cfg.mode}, user: ${cfg.userId}, autoRecall: ${cfg.autoRecall}, autoCapture: ${cfg.autoCapture}, stateDir: ${pluginStateDir ?? "none"})`,
        );
      },
      stop: () => {
        api.logger.info("openclaw-mem0: stopped");
      },
    });
  },
});

// ============================================================================
// Lifecycle Hook Registration
// ============================================================================

function registerHooks(
  api: OpenClawPluginApi,
  provider: Mem0Provider,
  cfg: Mem0Config,
  _effectiveUserId: (sessionKey?: string) => string,
  buildAddOptions: (
    userIdOverride?: string,
    runId?: string,
    sessionKey?: string,
  ) => AddOptions,
  buildSearchOptions: (
    userIdOverride?: string,
    limit?: number,
    runId?: string,
    sessionKey?: string,
  ) => SearchOptions,
  session: {
    setCurrentSessionId: (id: string) => void;
  },
  skillsActive: boolean = false,
  _captureEvent: (
    event: string,
    props?: Record<string, unknown>,
  ) => void = () => {},
  lifecycle: ReturnType<typeof createMemoryLifecycle> = createMemoryLifecycle(),
) {
  // ========================================================================
  // SKILLS MODE: Agentic memory via before_prompt_build
  // ========================================================================
  if (skillsActive) {
    // Use before_prompt_build instead of before_agent_start:
    // - prependSystemContext: static memory protocol (provider-cacheable, no per-turn cost)
    // - prependContext: dynamic recalled memories (changes every turn)
    //
    // NOTE: We previously used a shared `lastCleanUserMessage` variable populated
    // by message_received to get clean user content. That variable was process-global
    // mutable state vulnerable to cross-session races. Removed in favor of using
    // sanitizeQuery() on event.prompt within this hook, where ctx.sessionKey is
    // available and the execution is scoped to the correct session.
    api.on("before_prompt_build", async (event: any, ctx: any) => {
      if (!event.prompt || event.prompt.length < 5) return;

      const trigger = ctx?.trigger ?? undefined;
      const sessionId = ctx?.sessionKey ?? undefined;
      if (isNonInteractiveTrigger(trigger, sessionId)) {
        api.logger.info(
          "openclaw-mem0: skills-mode skipping non-interactive trigger",
        );
        return;
      }

      const promptLower = event.prompt.toLowerCase();
      const isSystemPrompt =
        promptLower.includes("a new session was started") ||
        promptLower.includes("session startup sequence") ||
        promptLower.includes("/new or /reset") ||
        promptLower.startsWith("run your session");
      if (isSystemPrompt) {
        api.logger.info(
          "openclaw-mem0: skills-mode skipping recall for system/bootstrap prompt",
        );
        // Still inject the protocol, just skip recall search
        const systemContext = loadCompactTriagePrompt(cfg.skills ?? {});
        return { prependSystemContext: systemContext };
      }

      if (sessionId) session.setCurrentSessionId(sessionId);

      const isSubagent = isSubagentSession(sessionId);
      const userId = _effectiveUserId(isSubagent ? undefined : sessionId);

      // Static protocol goes in prependSystemContext (cacheable across turns)
      let systemContext = loadCompactTriagePrompt(cfg.skills ?? {});
      if (isSubagent) {
        systemContext =
          "You are a subagent — use these memories for context but do not assume you are this user. Do NOT store new memories.\n\n" +
          systemContext;
      }

      // Dynamic recall goes in prependContext (changes every turn).
      // Strategy controls how much the plugin searches automatically:
      //   "always" — long-term + session search every turn (2 searches)
      //   "smart"  — long-term search only, no session search (1 search) [default]
      //   "manual" — no auto-recall; agent controls all search via memory_search (0 searches)
      let recallContext = "";
      const recallEnabled = cfg.skills?.recall?.enabled !== false;
      const recallStrategy = cfg.skills?.recall?.strategy ?? "smart";

      if (recallEnabled && recallStrategy !== "manual") {
        const recallStart = Date.now();
        try {
          const query = lifecycle.prepareUserText(sanitizeQuery(event.prompt));

          // Smart mode: skip session search (saves 1 API call per turn)
          const sessionIdForRecall =
            recallStrategy === "always"
              ? isSubagent
                ? undefined
                : sessionId
              : undefined; // smart: long-term only

          const recallResult = await skillRecall(
            provider,
            query,
            userId,
            cfg.skills ?? {},
            sessionIdForRecall,
          );

          api.logger.info(
            `openclaw-mem0: skills-mode recall (strategy=${recallStrategy}) injecting ${recallResult.memories.length} memories (~${recallResult.tokenEstimate} tokens)`,
          );

          _captureEvent("openclaw.hook.recall", {
            strategy: recallStrategy,
            memory_count: recallResult.memories.length,
            latency_ms: Date.now() - recallStart,
          });

          recallContext = recallResult.context;
        } catch (err) {
          api.logger.warn(
            `openclaw-mem0: skills-mode recall failed: ${String(err)}`,
          );
        }
      } else if (recallEnabled && recallStrategy === "manual") {
        api.logger.info(
          "openclaw-mem0: skills-mode recall strategy=manual, agent controls search",
        );
      }

      return {
        prependSystemContext: systemContext, // cached by provider
        prependContext: recallContext, // per-turn dynamic
      };
    });

    api.on("agent_end", async (event: any, ctx: any) => {
      const sessionId = ctx?.sessionKey ?? undefined;
      if (sessionId) session.setCurrentSessionId(sessionId);

      if (!event.success) return;

      api.logger.info("openclaw-mem0: skills-mode agent_end (no auto-capture)");
    });

    return; // Skip legacy hook registration
  }

  if (!cfg.autoRecall && !cfg.autoCapture) return;

  const sessions = new Map<string, { lifecycle: ReturnType<typeof createMemoryLifecycle>; recalled: boolean }>();
  const memoryFor = (sessionKey = "") => {
    let state = sessions.get(sessionKey);
    if (!state) {
      state = { lifecycle: createMemoryLifecycle({ recallHeading: USER_RECALL_HEADING }), recalled: false };
      state.lifecycle.beginSession();
      sessions.set(sessionKey, state);
    }
    return state;
  };

  const sender =
    (sessionKey?: string) =>
    async (messages: ConversationMessage[], reason: string) => {
      const captureStart = Date.now();
      try {
        const result = await provider.add(messages, buildAddOptions(undefined, undefined, sessionKey));
        const capturedCount = result.results?.length ?? 0;
        _captureEvent("openclaw.hook.capture", {
          reason,
          message_count: messages.length,
          captured_count: capturedCount,
          latency_ms: Date.now() - captureStart,
        });
        if (capturedCount > 0) {
          api.logger.info(`openclaw-mem0: auto-captured ${capturedCount} memories`);
        }
      } catch (err) {
        api.logger.warn(`openclaw-mem0: capture failed: ${String(err)}`);
      }
    };

  api.on("before_prompt_build", async (event: any, ctx: any) => {
    if (!event.prompt) return;

    const trigger = ctx?.trigger ?? undefined;
    const sessionId = ctx?.sessionKey ?? undefined;
    if (isNonInteractiveTrigger(trigger, sessionId)) {
      api.logger.info("openclaw-mem0: skipping non-interactive trigger");
      return;
    }

    const promptLower = event.prompt.toLowerCase();
    const isSystemPrompt =
      promptLower.includes("a new session was started") ||
      promptLower.includes("session startup sequence") ||
      promptLower.includes("/new or /reset") ||
      promptLower.startsWith("run your session");
    if (isSystemPrompt) {
      api.logger.info("openclaw-mem0: skipping system/bootstrap prompt");
      return;
    }

    if (sessionId) session.setCurrentSessionId(sessionId);

    const isSubagent = isSubagentSession(sessionId);
    const prompt = event.prompt
      .replace(/Sender\s*\(untrusted metadata\):\s*```json[\s\S]*?```\s*/gi, "")
      .trim();
    const state = memoryFor(sessionId);
    if (cfg.autoCapture && !isSubagent) state.lifecycle.recordUserPrompt(prompt);
    if (!cfg.autoRecall || state.recalled) return;
    state.recalled = true;

    const recallStart = Date.now();
    const context = await state.lifecycle.recall(prompt, true, async (query) => {
      try {
        const results = await provider.search(query, {
          ...buildSearchOptions(undefined, cfg.topK, undefined, isSubagent ? undefined : sessionId),
          threshold: undefined,
          rerank: false,
          latest_only: true,
        });
        _captureEvent("openclaw.hook.recall", {
          strategy: "first_prompt",
          memory_count: results.length,
          latency_ms: Date.now() - recallStart,
        });
        return { results };
      } catch (err) {
        api.logger.warn(`openclaw-mem0: recall failed: ${String(err)}`);
        throw err;
      }
    });
    if (!context) return;
    api.logger.info("openclaw-mem0: injecting recalled memories into context");
    return { prependContext: context };
  });

  api.on("session_end", async (event: any, ctx: any) => {
    const sessionKey = ctx?.sessionKey ?? event?.sessionKey ?? "";
    const state = sessions.get(sessionKey);
    if (!state) return;
    sessions.delete(sessionKey);
    await state.lifecycle.end("session-end", sender(sessionKey || undefined));
  });

  if (!cfg.autoCapture) return;

  api.on("agent_end", async (event: any, ctx: any) => {
    const trigger = ctx?.trigger ?? undefined;
    const sessionId = ctx?.sessionKey ?? undefined;
    if (isNonInteractiveTrigger(trigger, sessionId) || isSubagentSession(sessionId)) return;
    if (sessionId) session.setCurrentSessionId(sessionId);

    const state = memoryFor(sessionId);
    if (event.success) {
      const messages: unknown[] = event.messages ?? [];
      let lastUser = messages.length - 1;
      while (lastUser >= 0 && (messages[lastUser] as any)?.role !== "user") lastUser--;
      const reply = state.lifecycle
        .prepareConversation(messages.slice(lastUser + 1) as any[])
        .filter((message) => message.role === "assistant")
        .at(-1);
      if (reply) state.lifecycle.recordAssistantResponse(reply.content);
    }
    void state.lifecycle.afterResponse(sender(sessionId));
  });

  api.on("before_compaction", async (_event: any, ctx: any) => {
    const sessionKey = ctx?.sessionKey ?? undefined;
    await sessions.get(sessionKey ?? "")?.lifecycle.flush("pre-compact", sender(sessionKey));
  });
}

export default memoryPlugin;
