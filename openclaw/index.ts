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
 * - Auto-recall: injects relevant memories (both scopes) before each agent turn
 * - Auto-capture: stores key facts scoped to the current session after each agent turn
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
import { createProvider, providerToBackend } from "./providers.ts";
import { mem0ConfigSchema } from "./config.ts";
import type { FileConfig } from "./config.ts";
import { createPublicArtifactsProvider } from "./public-artifacts.ts";
import { filterMessagesForExtraction } from "./filtering.ts";
import {
  effectiveUserId,
  agentUserId,
  resolveUserId,
  isNonInteractiveTrigger,
  isSubagentSession,
} from "./isolation.ts";
import {
  loadTriagePrompt,
  loadDreamPrompt,
  isSkillsMode,
} from "./skill-loader.ts";
import { recall as skillRecall, sanitizeQuery } from "./recall.ts";
import {
  incrementSessionCount,
  checkCheapGates,
  checkMemoryGate,
  acquireDreamLock,
  releaseDreamLock,
  recordDreamCompletion,
} from "./dream-gate.ts";
import { PlatformBackend } from "./backend/platform.ts";
import type { Backend } from "./backend/base.ts";
import { registerCliCommands } from "./cli/commands.ts";
import { readPluginAuth } from "./cli/config-file.ts";
import { registerAllTools } from "./tools/index.ts";
import type { ToolDeps } from "./tools/index.ts";
import { captureEvent } from "./telemetry.ts";
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
          cfg,
          get stateDir() {
            return pluginStateDir;
          },
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
      if (cfg.customCategories) opts.custom_categories = cfg.customCategories;
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
        getStateDir: () => pluginStateDir,
      },
      skillsActive,
      _captureEvent,
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
    getStateDir: () => string | undefined;
  },
  skillsActive: boolean = false,
  _captureEvent: (
    event: string,
    props?: Record<string, unknown>,
  ) => void = () => {},
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
        const systemContext = loadTriagePrompt(cfg.skills ?? {});
        return { prependSystemContext: systemContext };
      }

      if (sessionId) session.setCurrentSessionId(sessionId);

      const isSubagent = isSubagentSession(sessionId);
      const userId = _effectiveUserId(isSubagent ? undefined : sessionId);

      // Static protocol goes in prependSystemContext (cacheable across turns)
      let systemContext = loadTriagePrompt(cfg.skills ?? {});
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
          const query = sanitizeQuery(event.prompt);

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

      // Auto-dream: check CHEAP gates first (local file reads only).
      // Only hit the API for memory count if time + session gates pass.
      const stateDir = session.getStateDir();
      const dreamEnabled =
        cfg.skills?.dream?.enabled !== false &&
        cfg.skills?.dream?.auto !== false;
      let dreamContext = "";
      if (dreamEnabled && stateDir && !isSubagent) {
        try {
          const cheapResult = checkCheapGates(
            stateDir,
            cfg.skills?.dream ?? {},
          );
          if (cheapResult.proceed) {
            // Cheap gates passed. Now do the expensive memory count check.
            const memories = await provider.getAll({
              user_id: userId,
              source: "OPENCLAW",
            });
            const memCount = Array.isArray(memories) ? memories.length : 0;
            const memResult = checkMemoryGate(
              memCount,
              cfg.skills?.dream ?? {},
            );
            if (memResult.pass && acquireDreamLock(stateDir)) {
              const dreamPrompt = loadDreamPrompt(cfg.skills ?? {});
              if (dreamPrompt) {
                dreamContext =
                  "\n\n<auto-dream>\nIMPORTANT: Before responding to the user, run a memory consolidation pass. Follow the protocol below, then respond normally.\n\n" +
                  dreamPrompt +
                  "\n</auto-dream>";
                // Track which session triggered dream (session-keyed, not global)
                dreamSessionId = sessionId;
                _captureEvent("openclaw.hook.dream", {
                  phase: "triggered",
                  memory_count: memCount,
                });
                api.logger.info(
                  `openclaw-mem0: auto-dream triggered (${memCount} memories, gate passed)`,
                );
              } else {
                releaseDreamLock(stateDir);
              }
            }
          }
        } catch (err) {
          api.logger.warn(
            `openclaw-mem0: auto-dream gate check failed: ${String(err)}`,
          );
        }
      }

      return {
        prependSystemContext: systemContext, // cached by provider
        prependContext: recallContext + dreamContext, // per-turn dynamic
      };
    });

    // Session-keyed dream tracking. Only the session that triggered dream
    // can complete it. Prevents cross-session false completion.
    let dreamSessionId: string | undefined;

    api.on("agent_end", async (event: any, ctx: any) => {
      const sessionId = ctx?.sessionKey ?? undefined;
      const trigger = ctx?.trigger ?? undefined;
      if (sessionId) session.setCurrentSessionId(sessionId);

      // If dream was triggered for THIS session, handle cleanup regardless
      // of success/failure. A failed turn must still release the lock.
      const stateDir = session.getStateDir();
      if (dreamSessionId && dreamSessionId === sessionId && stateDir) {
        dreamSessionId = undefined;

        if (!event.success) {
          // Turn failed/aborted after lock acquired. Release lock, do not
          // record completion. Gates will re-trigger next eligible turn.
          releaseDreamLock(stateDir);
          api.logger.warn(
            "openclaw-mem0: auto-dream turn failed, lock released, will retry",
          );
          return;
        }

        // Verify the model actually performed WRITE operations (not just reads).
        // Only count memory_add, memory_update, memory_delete.
        // Exclude memory_list and memory_search (read-only, orient-only pass).
        // Scan only the LAST assistant message (this turn), not the full session
        // snapshot, to avoid matching earlier tool calls from prior turns.
        const WRITE_TOOLS = new Set([
          "memory_add",
          "memory_update",
          "memory_delete",
        ]);
        const messages = event.messages ?? [];
        // Find the last assistant message (this turn's output)
        const lastAssistant = [...messages]
          .reverse()
          .find((m: any) => m.role === "assistant");
        const writeToolUsed =
          lastAssistant && Array.isArray(lastAssistant.content)
            ? lastAssistant.content.some(
                (block: any) =>
                  block.type === "tool_use" && WRITE_TOOLS.has(block.name),
              )
            : false;

        if (writeToolUsed) {
          releaseDreamLock(stateDir);
          recordDreamCompletion(stateDir);
          _captureEvent("openclaw.hook.dream", {
            phase: "completed",
            write_tools_used: true,
          });
          api.logger.info(
            "openclaw-mem0: auto-dream completed (verified write tool usage), lock released",
          );
        } else {
          releaseDreamLock(stateDir);
          api.logger.warn(
            "openclaw-mem0: auto-dream injected but no write tools executed. Lock released, will retry.",
          );
        }
        return;
      }

      if (!event.success) return;

      // Track session for dream gating (interactive turns only)
      if (
        stateDir &&
        sessionId &&
        !isNonInteractiveTrigger(trigger, sessionId)
      ) {
        incrementSessionCount(stateDir, sessionId);
      }

      api.logger.info("openclaw-mem0: skills-mode agent_end (no auto-capture)");
    });

    return; // Skip legacy hook registration
  }

  // ========================================================================
  // LEGACY MODE: Original auto-recall + auto-capture behavior
  // ========================================================================

  // Track last seen session ID to detect actual new sessions (not every turn)
  let lastRecallSessionId: string | undefined;

  // Auto-recall: inject relevant memories before prompt is built
  if (cfg.autoRecall) {
    const RECALL_TIMEOUT_MS = 8_000;

    api.on("before_prompt_build", async (event: any, ctx: any) => {
      if (!event.prompt || event.prompt.length < 5) return;

      // Skip non-interactive triggers (cron, heartbeat, automation)
      const trigger = (ctx as any)?.trigger ?? undefined;
      const sessionId = (ctx as any)?.sessionKey ?? undefined;
      if (isNonInteractiveTrigger(trigger, sessionId)) {
        api.logger.info(
          "openclaw-mem0: skipping recall for non-interactive trigger",
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
          "openclaw-mem0: skipping recall for system/bootstrap prompt",
        );
        return;
      }

      // Update shared state for tools (best-effort — tools don't have ctx)
      if (sessionId) session.setCurrentSessionId(sessionId);

      // Detect actual new session (first turn with a different sessionKey)
      const isNewSession =
        sessionId !== undefined && sessionId !== lastRecallSessionId;
      if (sessionId) lastRecallSessionId = sessionId;

      // Subagents have ephemeral UUIDs — their namespace is always empty.
      // Search the parent (main) user namespace instead so subagents get
      // the user's long-term context.
      const isSubagent = isSubagentSession(sessionId);
      const recallSessionKey = isSubagent ? undefined : sessionId;

      // Strip OpenClaw sender metadata from the prompt before searching
      const cleanPrompt = event.prompt
        .replace(
          /Sender\s*\(untrusted metadata\):\s*```json[\s\S]*?```\s*/gi,
          "",
        )
        .trim();

      const recallStart = Date.now();
      const recallWork = async () => {
        // Single search with a reasonable candidate pool
        const recallTopK = Math.max((cfg.topK ?? 5) * 2, 10);

        // Search long-term memories (user-scoped; subagents read from parent namespace)
        let longTermResults = await provider.search(
          cleanPrompt,
          buildSearchOptions(
            undefined,
            recallTopK,
            undefined,
            recallSessionKey,
          ),
        );

        longTermResults = longTermResults.filter(
          (r) => (r.score ?? 0) >= cfg.searchThreshold,
        );

        // Dynamic thresholding: drop memories scoring less than 50% of
        // the top result's score to filter out the long tail of weak matches
        if (longTermResults.length > 1) {
          const topScore = longTermResults[0]?.score ?? 0;
          if (topScore > 0) {
            longTermResults = longTermResults.filter(
              (r) => (r.score ?? 0) >= topScore * 0.5,
            );
          }
        }

        // Only broaden for genuinely new sessions with short prompts
        // (cold-start blindness). Skip on subsequent turns to save API calls.
        if (isNewSession && cleanPrompt.length < 100) {
          const broadOpts = buildSearchOptions(
            undefined,
            5,
            undefined,
            recallSessionKey,
          );
          broadOpts.threshold = cfg.searchThreshold;
          const broadResults = await provider.search(
            "recent decisions, preferences, active projects, and configuration",
            broadOpts,
          );
          const existingIds = new Set(longTermResults.map((r) => r.id));
          for (const r of broadResults) {
            if (!existingIds.has(r.id)) {
              longTermResults.push(r);
            }
          }
        }

        // Cap at configured topK after filtering
        longTermResults = longTermResults.slice(0, cfg.topK);

        if (longTermResults.length === 0) return undefined;

        // Build context with clear labels
        const memoryContext = longTermResults
          .map(
            (r) =>
              `- ${r.memory}${r.categories?.length ? ` [${r.categories.join(", ")}]` : ""}`,
          )
          .join("\n");

        _captureEvent("openclaw.hook.recall", {
          strategy: "legacy",
          memory_count: longTermResults.length,
          latency_ms: Date.now() - recallStart,
        });

        api.logger.info(
          `openclaw-mem0: injecting ${longTermResults.length} memories into context`,
        );

        const preamble = isSubagent
          ? `The following are stored memories for user "${cfg.userId}". You are a subagent — use these memories for context but do not assume you are this user.`
          : `The following are stored memories for user "${cfg.userId}". Use them to personalize your response:`;

        return {
          prependContext: `<relevant-memories>\n${preamble}\n${memoryContext}\n</relevant-memories>`,
        };
      };

      try {
        const timeout = new Promise<undefined>((resolve) => {
          setTimeout(() => resolve(undefined), RECALL_TIMEOUT_MS);
        });
        const result = await Promise.race([
          recallWork(),
          timeout.then(() => {
            api.logger.warn(
              `openclaw-mem0: recall timed out after ${RECALL_TIMEOUT_MS}ms, skipping`,
            );
            return undefined;
          }),
        ]);
        return result;
      } catch (err) {
        api.logger.warn(`openclaw-mem0: recall failed: ${String(err)}`);
      }
    });
  }

  // Auto-capture: store conversation context after agent ends.
  if (cfg.autoCapture) {
    api.on("agent_end", async (event, ctx) => {
      if (!event.success || !event.messages || event.messages.length === 0) {
        return;
      }

      // Skip non-interactive triggers (cron, heartbeat, automation)
      const trigger = (ctx as any)?.trigger ?? undefined;
      const sessionId = (ctx as any)?.sessionKey ?? undefined;
      if (isNonInteractiveTrigger(trigger, sessionId)) {
        api.logger.info(
          "openclaw-mem0: skipping capture for non-interactive trigger",
        );
        return;
      }

      // Skip capture for subagents — their ephemeral UUIDs create orphaned
      // namespaces that are never read again. The main agent's agent_end
      // hook captures the consolidated result including subagent output.
      if (isSubagentSession(sessionId)) {
        api.logger.info(
          "openclaw-mem0: skipping capture for subagent (main agent captures consolidated result)",
        );
        return;
      }

      // Update shared state for tools (best-effort — tools don't have ctx)
      if (sessionId) session.setCurrentSessionId(sessionId);

      const MEMORY_MUTATE_TOOLS = new Set([
        "memory_add",
        "memory_update",
        "memory_delete",
      ]);
      const agentUsedMemoryTool = event.messages.some((msg: any) => {
        if (msg?.role !== "assistant" || !Array.isArray(msg?.content))
          return false;
        return msg.content.some(
          (block: any) =>
            (block?.type === "tool_use" || block?.type === "toolCall") &&
            MEMORY_MUTATE_TOOLS.has(block.name),
        );
      });
      if (agentUsedMemoryTool) {
        api.logger.info(
          "openclaw-mem0: skipping auto-capture — agent already used memory tools this turn",
        );
        return;
      }

      // --- Build capture payload synchronously (cheap), then fire-and-forget ---

      // Patterns indicating an assistant message contains a summary of
      // completed work — these are high-value for extraction and should
      // be included even if they fall outside the recent-message window.
      const SUMMARY_PATTERNS = [
        /## What I (Accomplished|Built|Updated)/i,
        /✅\s*(Done|Complete|All done)/i,
        /Here's (what I updated|the recap|a summary)/i,
        /### Changes Made/i,
        /Implementation Status/i,
        /All locked in\. Quick summary/i,
      ];

      // First pass: extract all messages into a typed array
      const allParsed: Array<{
        role: string;
        content: string;
        index: number;
        isSummary: boolean;
      }> = [];

      for (let i = 0; i < event.messages.length; i++) {
        const msg = event.messages[i];
        if (!msg || typeof msg !== "object") continue;
        const msgObj = msg as Record<string, unknown>;

        const role = msgObj.role;
        if (role !== "user" && role !== "assistant") continue;

        let textContent = "";
        const content = msgObj.content;

        if (typeof content === "string") {
          textContent = content;
        } else if (Array.isArray(content)) {
          for (const block of content) {
            if (
              block &&
              typeof block === "object" &&
              "text" in block &&
              typeof (block as Record<string, unknown>).text === "string"
            ) {
              textContent +=
                (textContent ? "\n" : "") +
                ((block as Record<string, unknown>).text as string);
            }
          }
        }

        if (!textContent) continue;
        // Strip injected memory context, keep the actual user text
        if (textContent.includes("<relevant-memories>")) {
          textContent = textContent
            .replace(/<relevant-memories>[\s\S]*?<\/relevant-memories>\s*/g, "")
            .trim();
          if (!textContent) continue;
        }
        // Strip OpenClaw sender metadata prefix (prevents storing TUI identity as memory)
        if (
          textContent.includes("Sender") &&
          textContent.includes("untrusted metadata")
        ) {
          textContent = textContent
            .replace(
              /Sender\s*\(untrusted metadata\):\s*```json[\s\S]*?```\s*/gi,
              "",
            )
            .trim();
          if (!textContent) continue;
        }

        const isSummary =
          role === "assistant" &&
          SUMMARY_PATTERNS.some((p) => p.test(textContent));

        allParsed.push({
          role: role as string,
          content: textContent,
          index: i,
          isSummary,
        });
      }

      if (allParsed.length === 0) return;

      // Select messages: last 20 + any earlier summary messages,
      // sorted by original index to preserve chronological order.
      const recentWindow = 20;
      const recentCutoff = allParsed.length - recentWindow;

      const candidates: typeof allParsed = [];

      // Include summary messages from anywhere in the conversation
      for (const msg of allParsed) {
        if (msg.isSummary && msg.index < recentCutoff) {
          candidates.push(msg);
        }
      }

      // Include recent messages
      const seenIndices = new Set(candidates.map((m) => m.index));
      for (const msg of allParsed) {
        if (msg.index >= recentCutoff && !seenIndices.has(msg.index)) {
          candidates.push(msg);
        }
      }

      // Sort by original position so the extraction model sees
      // messages in the order they actually occurred
      candidates.sort((a, b) => a.index - b.index);

      const selected = candidates.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      // Apply noise filtering pipeline: drop noise, strip fragments, truncate
      const formattedMessages = filterMessagesForExtraction(selected);

      if (formattedMessages.length === 0) return;

      // Skip if no meaningful user content remains after filtering
      if (!formattedMessages.some((m) => m.role === "user")) return;
      const userContent = formattedMessages
        .filter((m) => m.role === "user")
        .map((m) => m.content)
        .join(" ");
      if (userContent.length < 50) {
        api.logger.info(
          "openclaw-mem0: skipping capture — user content too short for meaningful extraction",
        );
        return;
      }

      // Inject a timestamp preamble so the extraction model can anchor
      // time-sensitive facts to a concrete date and attribute to the correct user
      const timestamp = new Date().toISOString().split("T")[0];
      formattedMessages.unshift({
        role: "system",
        content: `Current date: ${timestamp}. The user is identified as "${cfg.userId}". Extract durable facts from this conversation. Include this date when storing time-sensitive information.`,
      });

      const addOpts = buildAddOptions(undefined, undefined, sessionId);
      const captureStart = Date.now();
      provider
        .add(formattedMessages, addOpts)
        .then((result) => {
          const capturedCount = result.results?.length ?? 0;
          _captureEvent("openclaw.hook.capture", {
            captured_count: capturedCount,
            latency_ms: Date.now() - captureStart,
          });
          if (capturedCount > 0) {
            api.logger.info(
              `openclaw-mem0: auto-captured ${capturedCount} memories`,
            );
          }
        })
        .catch((err) => {
          api.logger.warn(`openclaw-mem0: capture failed: ${String(err)}`);
        });
    });
  }
}

export default memoryPlugin;
