/**
 * CLI subcommand registration for the OpenClaw Mem0 plugin.
 *
 * Registers all `openclaw mem0 <subcommand>` commands:
 *
 * Memory:
 *   - add         : Add a memory from text (--user-id, --agent-id)
 *   - search      : Search memories (--top-k, --scope, --agent-id, --user-id)
 *   - get         : Get a specific memory by ID
 *   - list        : List memories with optional filters (--user-id, --agent-id, --top-k)
 *   - update      : Update a memory's text
 *   - delete      : Delete a memory or all memories (--all, --confirm)
 *   - history     : View edit history of a memory
 *
 * Management:
 *   - init        : Authenticate with Mem0 Platform (email or API key)
 *   - status      : Check API connectivity and show current config
 *   - config show : Display current plugin configuration
 *   - config get  : Get a single config value
 *   - config set  : Update a plugin config field
 *   - dream       : Run memory consolidation
 *
 * Naming conventions match the Python CLI (`mem0 init`, `mem0 search`, etc.)
 */

import { createInterface } from "node:readline";
import { userInfo as osUserInfo } from "node:os";

import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import type { Backend } from "../backend/base.ts";
import type {
  Mem0Config,
  Mem0Provider,
  MemoryItem,
  SearchOptions,
} from "../types.ts";
import { loadDreamPrompt } from "../skill-loader.ts";
import type { PluginAuthConfig } from "./config-file.ts";
import {
  readPluginAuth,
  writePluginAuth,
  writePluginConfigField,
  getBaseUrl,
  OPENCLAW_CONFIG_FILE,
} from "./config-file.ts";

// ============================================================================
// Reusable helpers (DRY)
// ============================================================================

/** Prompt user for input on stderr (keeps stdout clean for piping). */
function promptInput(question: string): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stderr });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

/** Get system username for userId fallback. */
function getSystemUsername(): string {
  try {
    return osUserInfo().username || "default";
  } catch {
    return "default";
  }
}

/**
 * Resolve userId silently (no interactive prompt).
 * Matches Python CLI: --user-id flag > existing config > system username > "default"
 * Uses os.userInfo().username which covers all platforms.
 */
function resolveUserId(flagValue?: string, existingValue?: string): string {
  if (flagValue) return flagValue;
  if (existingValue) return existingValue;
  return getSystemUsername();
}

/**
 * POST JSON to a Mem0 API endpoint. Returns parsed body on success, null on failure.
 * Handles rate limiting, network errors, and HTTP errors with consistent messaging.
 */
async function apiPost(
  url: string,
  body: Record<string, unknown>,
  errorPrefix: string,
): Promise<Record<string, unknown> | null> {
  let resp: Response;
  try {
    resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    console.error(`Could not reach ${url}: ${String(err)}`);
    return null;
  }

  if (resp.status === 429) {
    console.error("Too many attempts. Try again in a few minutes.");
    return null;
  }
  if (!resp.ok) {
    let detail: string;
    try {
      const data = (await resp.json()) as Record<string, unknown>;
      detail = String(data.error ?? resp.statusText);
    } catch {
      detail = resp.statusText;
    }
    console.error(`${errorPrefix}: ${detail}`);
    return null;
  }

  try {
    return (await resp.json()) as Record<string, unknown>;
  } catch {
    return {};
  }
}

/** Validate an API key by pinging the platform. Returns true if valid. */
async function validateApiKey(
  baseUrl: string,
  apiKey: string,
): Promise<{ ok: boolean; status?: number; error?: string }> {
  try {
    const resp = await fetch(`${baseUrl}/v1/ping/`, {
      headers: { Authorization: `Token ${apiKey}` },
    });
    return resp.ok
      ? { ok: true }
      : { ok: false, status: resp.status };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** Send email verification code. Returns true on success. */
async function sendVerificationCode(
  baseUrl: string,
  email: string,
): Promise<boolean> {
  const url = baseUrl.replace(/\/+$/, "");
  const result = await apiPost(
    `${url}/api/v1/auth/email_code/`,
    { email },
    "Failed to send code",
  );
  return result !== null;
}

/** Verify email code and extract API key. Returns apiKey or null. */
async function verifyEmailCode(
  baseUrl: string,
  email: string,
  code: string,
): Promise<string | null> {
  const url = baseUrl.replace(/\/+$/, "");
  const result = await apiPost(
    `${url}/api/v1/auth/email_code/verify/`,
    { email, code: code.trim() },
    "Verification failed",
  );
  if (!result) return null;

  const apiKey = result.api_key as string | undefined;
  if (!apiKey) {
    console.error(
      "Auth succeeded but no API key was returned. Contact support.",
    );
    return null;
  }
  return apiKey;
}

/**
 * Save login config and print summary.
 * Matches Python CLI: saves api_key, base_url, user_id only.
 */
function saveLoginConfig(
  apiKey: string,
  baseUrl: string,
  userIdFlag?: string,
): void {
  const existingAuth = readPluginAuth();
  const userId = resolveUserId(userIdFlag, existingAuth.userId);

  writePluginAuth({ apiKey, baseUrl, userId, mode: "platform" });

  console.log(`  Configuration saved to ${OPENCLAW_CONFIG_FILE}`);
  console.log(`  Mode: platform`);
  console.log(`  User ID: ${userId}`);
}

function saveOssConfig(userIdFlag?: string): void {
  const existingAuth = readPluginAuth();
  const userId = resolveUserId(userIdFlag, existingAuth.userId);

  writePluginAuth({ userId, mode: "open-source" });

  console.log(`  Configuration saved to ${OPENCLAW_CONFIG_FILE}`);
  console.log(`  Mode: open-source`);
  console.log(`  User ID: ${userId}`);
}

// ============================================================================
// Main registration function
// ============================================================================

export function registerCliCommands(
  api: OpenClawPluginApi,
  backend: Backend,
  provider: Mem0Provider,
  cfg: Mem0Config,
  effectiveUserId: (sessionKey?: string) => string,
  agentUserId: (id: string) => string,
  buildSearchOptions: (
    userIdOverride?: string,
    limit?: number,
    runId?: string,
    sessionKey?: string,
  ) => SearchOptions,
  getCurrentSessionId: () => string | undefined,
): void {
  api.registerCli(
    ({ program }) => {
      const mem0 = program
        .command("mem0")
        .description("Mem0 memory plugin commands");

      // ====================================================================
      // init (matches: mem0 init)
      // ====================================================================

      mem0
        .command("init")
        .description("Set up Mem0 — authenticate and configure")
        .option("--email <email>", "Login via email verification code")
        .option("--code <code>", "Verification code (use with --email)")
        .option("--api-key <key>", "Direct API key entry")
        .option("--user-id <id>", "Set user ID for memory namespace")
        .action(
          async (opts: {
            email?: string;
            code?: string;
            apiKey?: string;
            userId?: string;
          }) => {
            try {
              const baseUrl = getBaseUrl();
              const existingAuth = readPluginAuth();
              const hasExistingConfig = !!(existingAuth.apiKey || existingAuth.mode);

              // -- API key flow ------------------------------------------------
              if (opts.apiKey) {
                if (opts.email) {
                  console.error("Cannot use both --api-key and --email.");
                  return;
                }

                saveLoginConfig(opts.apiKey, baseUrl, opts.userId);
                if (hasExistingConfig) {
                  console.log(
                    "  Existing configuration detected — updated API key (other settings preserved).",
                  );
                }

                const check = await validateApiKey(baseUrl, opts.apiKey);
                if (check.ok) {
                  console.log(
                    "  API key validated. Connected to Mem0 Platform.",
                  );
                } else if (check.status) {
                  console.warn(
                    `  API key saved but validation returned HTTP ${check.status}. Check that the key is correct.`,
                  );
                } else {
                  console.warn(
                    `  API key saved but could not reach ${baseUrl}: ${check.error}. Check your network connection.`,
                  );
                }
                console.log(
                  "  Restart the gateway: openclaw gateway restart\n",
                );
                return;
              }

              // -- Email + code (verify) — non-interactive ----------------------
              if (opts.email && opts.code) {
                const email = opts.email.trim().toLowerCase();
                const apiKey = await verifyEmailCode(baseUrl, email, opts.code);
                if (!apiKey) return;

                saveLoginConfig(apiKey, baseUrl, opts.userId);
                if (hasExistingConfig) {
                  console.log(
                    "  Existing configuration detected — updated API key (other settings preserved).",
                  );
                }
                console.log("  Authenticated!");
                console.log(
                  "  Restart the gateway: openclaw gateway restart\n",
                );
                return;
              }

              // -- Email only (send code) ---------------------------------------
              if (opts.email) {
                const email = opts.email.trim().toLowerCase();
                const sent = await sendVerificationCode(baseUrl, email);
                if (sent) {
                  console.log(
                    `Verification code sent! Run:\n  openclaw mem0 init --email ${email} --code <CODE>`,
                  );
                }
                return;
              }

              // -- No flags: interactive flow -----------------------------------
              if (!process.stdin.isTTY) {
                console.log("Usage (non-interactive):");
                console.log(
                  "  openclaw mem0 init --api-key <key>",
                );
                console.log(
                  "  openclaw mem0 init --api-key <key> --user-id <id>",
                );
                console.log(
                  "  openclaw mem0 init --email <email>",
                );
                console.log(
                  "  openclaw mem0 init --email <email> --code <c>",
                );
                console.log(
                  "  openclaw mem0 init --email <email> --code <c> --user-id <id>",
                );
                return;
              }

              // Detect existing config and offer to reuse or reconfigure
              if (hasExistingConfig) {
                console.log("\n  Existing Mem0 configuration found:\n");
                if (existingAuth.apiKey) {
                  const masked = existingAuth.apiKey.length > 8
                    ? existingAuth.apiKey.slice(0, 4) + "..." + existingAuth.apiKey.slice(-4)
                    : existingAuth.apiKey.slice(0, 2) + "***";
                  console.log(`    API Key:  ${masked}`);
                }
                if (existingAuth.userId)
                  console.log(`    User ID:  ${existingAuth.userId}`);
                if (existingAuth.mode)
                  console.log(`    Mode:     ${existingAuth.mode}`);
                if (existingAuth.orgId)
                  console.log(`    Org ID:   ${existingAuth.orgId}`);
                if (existingAuth.projectId)
                  console.log(`    Project:  ${existingAuth.projectId}`);
                console.log("");

                // Validate existing key before asking
                if (existingAuth.apiKey) {
                  const check = await validateApiKey(
                    existingAuth.baseUrl || baseUrl,
                    existingAuth.apiKey,
                  );
                  if (check.ok) {
                    console.log(
                      "    Existing API key is valid and connected.\n",
                    );
                  } else {
                    console.log(
                      "    Existing API key could not be validated (may be expired or revoked).\n",
                    );
                  }
                }

                const reuse = await promptInput(
                  "  Keep existing configuration? (Y/n): ",
                );
                if (
                  reuse === "" ||
                  reuse.toLowerCase() === "y" ||
                  reuse.toLowerCase() === "yes"
                ) {
                  console.log(
                    "\n  Configuration preserved. No changes made.",
                  );
                  console.log(
                    "  To update individual settings: openclaw mem0 config set <key> <value>\n",
                  );
                  return;
                }
                console.log("");
              }

              console.log("\n  Mem0 Setup\n");
              console.log("  How would you like to set up Mem0?");
              console.log("  1. Login with email (recommended)");
              console.log("  2. Enter API key manually");
              console.log("  3. Open-source mode (self-hosted)\n");

              const choice = await promptInput("  Choice (1/2/3): ");

              if (choice === "1") {
                // --- Email interactive flow ---
                const email = (
                  await promptInput("  Email: ")
                ).toLowerCase();
                if (!email) {
                  console.error("Email is required.");
                  return;
                }

                const sent = await sendVerificationCode(baseUrl, email);
                if (!sent) return;

                console.log(
                  "  Verification code sent! Check your email.\n",
                );
                const code = await promptInput("  Code: ");
                if (!code) {
                  console.error("Code is required.");
                  return;
                }

                const apiKey = await verifyEmailCode(baseUrl, email, code);
                if (!apiKey) return;

                // Prompt for userId if not passed via flag
                let userIdValue = opts.userId;
                if (!userIdValue) {
                  const defaultUid = resolveUserId(undefined, existingAuth.userId);
                  const uidInput = await promptInput(
                    `  User ID (${defaultUid}): `,
                  );
                  userIdValue = uidInput || undefined;
                }

                console.log("");
                saveLoginConfig(apiKey, baseUrl, userIdValue);
                console.log("  Authenticated!");
                console.log(
                  "  Restart the gateway: openclaw gateway restart\n",
                );
              } else if (choice === "2") {
                // --- API key interactive flow ---
                const key = await promptInput("  API Key: ");
                if (!key) {
                  console.error("API key is required.");
                  return;
                }

                // Prompt for userId if not passed via flag
                let userIdValue2 = opts.userId;
                if (!userIdValue2) {
                  const defaultUid = resolveUserId(undefined, existingAuth.userId);
                  const uidInput = await promptInput(
                    `  User ID (${defaultUid}): `,
                  );
                  userIdValue2 = uidInput || undefined;
                }

                console.log("");
                saveLoginConfig(key, baseUrl, userIdValue2);

                const check = await validateApiKey(baseUrl, key);
                if (check.ok) {
                  console.log(
                    "  API key validated. Connected to Mem0 Platform.",
                  );
                } else if (check.status) {
                  console.warn(
                    `  API key saved but validation returned HTTP ${check.status}.`,
                  );
                } else {
                  console.warn(
                    `  API key saved but could not reach ${baseUrl}: ${check.error}`,
                  );
                }
                console.log(
                  "  Restart the gateway: openclaw gateway restart\n",
                );
              } else if (choice === "3") {
                // --- Open-source interactive flow ---
                console.log(
                  "\n  Open-source mode uses the Mem0 OSS SDK locally.",
                );
                console.log(
                  "  By default it requires an OpenAI API key for embeddings and LLM.\n",
                );

                console.log(
                  "  You need an OpenAI API key for embeddings and LLM.",
                );
                console.log(
                  "  Get one from https://platform.openai.com/api-keys\n",
                );
                const openaiKey = await promptInput(
                  "  OpenAI API Key (or press Enter to skip): ",
                );
                if (openaiKey) {
                  writePluginConfigField(
                    ["oss", "embedder"],
                    { provider: "openai", config: { apiKey: openaiKey } },
                  );
                  writePluginConfigField(
                    ["oss", "llm"],
                    { provider: "openai", config: { apiKey: openaiKey } },
                  );
                  console.log(
                    "\n  OpenAI API key saved to config.\n",
                  );
                } else {
                  console.log(
                    "\n  Skipped. You can add it later via:",
                  );
                  console.log(
                    "    openclaw mem0 config set oss.embedder.config.apiKey <key>",
                  );
                  console.log(
                    "  Or set OPENAI_API_KEY in your environment.\n",
                  );
                }

                // Prompt for userId
                let userIdValue3 = opts.userId;
                if (!userIdValue3) {
                  const defaultUid = resolveUserId(undefined, existingAuth.userId);
                  const uidInput = await promptInput(
                    `  User ID (${defaultUid}): `,
                  );
                  userIdValue3 = uidInput || undefined;
                }

                console.log("");
                saveOssConfig(userIdValue3);
                console.log("  Open-source mode configured!");
                console.log(
                  "  Restart the gateway: openclaw gateway restart\n",
                );
              } else {
                console.log(
                  "Invalid choice. Run `openclaw mem0 init` again.",
                );
              }
            } catch (err) {
              console.error(`Init failed: ${String(err)}`);
            }
          },
        );

      // ====================================================================
      // search (matches: mem0 search <query> --top-k --user-id --agent-id)
      // ====================================================================

      mem0
        .command("search")
        .description("Search memories")
        .argument("<query>", "Search query")
        .option("--top-k <n>", "Max results", String(cfg.topK))
        .option(
          "--scope <scope>",
          'Memory scope: "session", "long-term", or "all"',
          "all",
        )
        .option("--agent-id <agentId>", "Search agent's memory namespace")
        .option("--user-id <userId>", "Override user ID")
        .action(
          async (
            query: string,
            opts: {
              topK: string;
              scope: string;
              agentId?: string;
              userId?: string;
            },
          ) => {
            try {
              const limit = parseInt(opts.topK, 10);
              const scope = opts.scope as "session" | "long-term" | "all";
              const currentSessionId = getCurrentSessionId();
              const uid = opts.userId
                ? opts.userId
                : opts.agentId
                  ? agentUserId(opts.agentId)
                  : effectiveUserId(currentSessionId);

              // CLI search: no source filter so users find ALL memories
              const cliSearchOpts = (
                userIdOverride?: string,
                lim?: number,
                runId?: string,
              ): SearchOptions => {
                const base = buildSearchOptions(userIdOverride, lim, runId);
                delete (base as any).source;
                base.threshold = 0.3;
                return base;
              };

              let allResults: MemoryItem[] = [];

              if (scope === "session" || scope === "all") {
                if (currentSessionId) {
                  const sessionResults = await provider.search(
                    query,
                    cliSearchOpts(uid, limit, currentSessionId),
                  );
                  if (sessionResults?.length) {
                    allResults.push(
                      ...sessionResults.map((r) => ({
                        ...r,
                        _scope: "session" as const,
                      })),
                    );
                  }
                } else if (scope === "session") {
                  console.log(
                    "No active session ID available for session-scoped search.",
                  );
                  return;
                }
              }

              if (scope === "long-term" || scope === "all") {
                const longTermResults = await provider.search(
                  query,
                  cliSearchOpts(uid, limit),
                );
                if (longTermResults?.length) {
                  allResults.push(
                    ...longTermResults.map((r) => ({
                      ...r,
                      _scope: "long-term" as const,
                    })),
                  );
                }
              }

              // Deduplicate by ID when searching "all"
              if (scope === "all") {
                const seen = new Set<string>();
                allResults = allResults.filter((r) => {
                  if (seen.has(r.id)) return false;
                  seen.add(r.id);
                  return true;
                });
              }

              if (!allResults.length) {
                console.log("No memories found.");
                return;
              }

              const output = allResults.map((r) => ({
                id: r.id,
                memory: r.memory,
                score: r.score,
                scope: (r as any)._scope,
                categories: r.categories,
                created_at: r.created_at,
              }));
              console.log(JSON.stringify(output, null, 2));
            } catch (err) {
              console.error(`Search failed: ${String(err)}`);
            }
          },
        );

      // ====================================================================
      // add (matches: mem0 add <text> --user-id --agent-id)
      // ====================================================================

      mem0
        .command("add")
        .description("Add a memory from text")
        .argument("<text>", "Text to store as a memory")
        .option("--user-id <userId>", "Override user ID")
        .option("--agent-id <agentId>", "Store in agent's memory namespace")
        .action(
          async (
            text: string,
            opts: { userId?: string; agentId?: string },
          ) => {
            try {
              const uid = opts.userId
                ? opts.userId
                : opts.agentId
                  ? agentUserId(opts.agentId)
                  : effectiveUserId(getCurrentSessionId());
              const result = await provider.add(
                [{ role: "user", content: text }],
                { user_id: uid },
              );
              const count = result.results?.length ?? 0;
              if (count > 0) {
                console.log(`Added ${count} memory(s):`);
                for (const r of result.results) {
                  console.log(`  ${r.id}: ${r.memory} [${r.event}]`);
                }
              } else {
                console.log(
                  "No new memories extracted (text may already be stored or not contain durable facts).",
                );
              }
            } catch (err) {
              console.error(`Add failed: ${String(err)}`);
            }
          },
        );

      // ====================================================================
      // get (matches: mem0 get <memory_id>)
      // ====================================================================

      mem0
        .command("get")
        .description("Get a specific memory by ID")
        .argument("<memory_id>", "Memory ID to retrieve")
        .action(async (memoryId: string) => {
          try {
            const memory = await provider.get(memoryId);
            console.log(
              JSON.stringify(
                {
                  id: memory.id,
                  memory: memory.memory,
                  user_id: memory.user_id,
                  categories: memory.categories,
                  metadata: memory.metadata,
                  created_at: memory.created_at,
                  updated_at: memory.updated_at,
                },
                null,
                2,
              ),
            );
          } catch (err) {
            console.error(`Get failed: ${String(err)}`);
          }
        });

      // ====================================================================
      // list (matches: mem0 list --user-id --agent-id --top-k)
      // ====================================================================

      mem0
        .command("list")
        .description("List memories with optional filters")
        .option("--user-id <userId>", "Override user ID")
        .option("--agent-id <agentId>", "List agent's memories")
        .option("--top-k <n>", "Max results", "50")
        .action(
          async (opts: {
            userId?: string;
            agentId?: string;
            topK: string;
          }) => {
            try {
              const uid = opts.userId
                ? opts.userId
                : opts.agentId
                  ? agentUserId(opts.agentId)
                  : cfg.userId;
              const limit = parseInt(opts.topK, 10);
              const memories = await provider.getAll({
                user_id: uid,
                page_size: limit,
              });

              if (!Array.isArray(memories) || memories.length === 0) {
                console.log("No memories found.");
                return;
              }

              const output = memories.map((m) => ({
                id: m.id,
                memory: m.memory,
                categories: m.categories,
                created_at: m.created_at,
                updated_at: m.updated_at,
              }));
              console.log(JSON.stringify(output, null, 2));
              console.log(`\nTotal: ${memories.length} memories`);
            } catch (err) {
              console.error(`List failed: ${String(err)}`);
            }
          },
        );

      // ====================================================================
      // update (matches: mem0 update <memory_id> <text>)
      // ====================================================================

      mem0
        .command("update")
        .description("Update a memory's text")
        .argument("<memory_id>", "Memory ID to update")
        .argument("<text>", "New text for the memory")
        .action(async (memoryId: string, text: string) => {
          try {
            await provider.update(memoryId, text);
            console.log(`Memory ${memoryId} updated.`);
          } catch (err) {
            console.error(`Update failed: ${String(err)}`);
          }
        });

      // ====================================================================
      // delete (matches: mem0 delete <memory_id> --all --user-id)
      // ====================================================================

      mem0
        .command("delete")
        .description("Delete a memory, or all memories for a user")
        .argument("[memory_id]", "Memory ID to delete")
        .option("--all", "Delete all memories for the user")
        .option("--user-id <userId>", "Override user ID (with --all)")
        .option("--agent-id <agentId>", "Delete from agent's namespace")
        .option("--confirm", "Skip confirmation for bulk delete")
        .action(
          async (
            memoryId: string | undefined,
            opts: {
              all?: boolean;
              userId?: string;
              agentId?: string;
              confirm?: boolean;
            },
          ) => {
            try {
              if (opts.all) {
                const uid = opts.userId
                  ? opts.userId
                  : opts.agentId
                    ? agentUserId(opts.agentId)
                    : cfg.userId;

                if (!opts.confirm && process.stdin.isTTY) {
                  const answer = await promptInput(
                    `  Delete ALL memories for user "${uid}"? This cannot be undone. (yes/N): `,
                  );
                  if (answer.toLowerCase() !== "yes") {
                    console.log("Cancelled.");
                    return;
                  }
                } else if (!opts.confirm) {
                  console.error(
                    "Bulk delete requires --confirm flag in non-interactive mode.",
                  );
                  return;
                }

                await provider.deleteAll(uid);
                console.log(`All memories deleted for user "${uid}".`);
                return;
              }

              if (!memoryId) {
                console.error(
                  "Provide a memory_id or use --all to delete all memories.",
                );
                return;
              }

              await provider.delete(memoryId);
              console.log(`Memory ${memoryId} deleted.`);
            } catch (err) {
              console.error(`Delete failed: ${String(err)}`);
            }
          },
        );

      // ====================================================================
      // history (matches: mem0 history <memory_id>)
      // ====================================================================

      mem0
        .command("history")
        .description("View edit history of a memory")
        .argument("<memory_id>", "Memory ID to view history for")
        .action(async (memoryId: string) => {
          try {
            const entries = await provider.history(memoryId);
            if (!entries.length) {
              console.log("No history found for this memory.");
              return;
            }
            console.log(JSON.stringify(entries, null, 2));
          } catch (err) {
            console.error(`History failed: ${String(err)}`);
          }
        });

      // ====================================================================
      // status (matches: mem0 status)
      // ====================================================================

      mem0
        .command("status")
        .description("Check API connectivity and current config")
        .action(async () => {
          try {
            const auth = readPluginAuth();
            console.log(`Mode: ${cfg.mode}`);
            console.log(`User ID: ${cfg.userId}`);
            console.log(`Config: ${OPENCLAW_CONFIG_FILE}`);
            console.log("");

            const result = await backend.status();
            if (result.connected) {
              console.log("Connected to Mem0");
            } else {
              console.log("Not connected to Mem0");
            }
            if (result.url) {
              console.log(`URL: ${String(result.url)}`);
            }
            if (result.error) {
              console.log(`Error: ${String(result.error)}`);
            }
          } catch (err) {
            console.error(`Status check failed: ${String(err)}`);
          }
        });

      // ====================================================================
      // config (matches: mem0 config show, mem0 config get, mem0 config set)
      // ====================================================================

      const configCmd = mem0
        .command("config")
        .description("Manage plugin configuration");

      // All settable config keys: short alias → camelCase field in openclaw.json
      // Matches Python CLI key names (snake_case) with dot-notation support.
      const CONFIG_KEYS: Record<string, string> = {
        // Short aliases (matches Python CLI)
        api_key: "apiKey",
        base_url: "baseUrl",
        user_id: "userId",
        org_id: "orgId",
        project_id: "projectId",
        enable_graph: "enableGraph",
        auto_recall: "autoRecall",
        auto_capture: "autoCapture",
        top_k: "topK",
        mode: "mode",
        // Dot notation (matches Python CLI: platform.api_key, defaults.user_id)
        "platform.api_key": "apiKey",
        "platform.base_url": "baseUrl",
        "defaults.user_id": "userId",
        "defaults.org_id": "orgId",
        "defaults.project_id": "projectId",
        "defaults.enable_graph": "enableGraph",
        "defaults.auto_recall": "autoRecall",
        "defaults.auto_capture": "autoCapture",
        "defaults.top_k": "topK",
      };

      // Keys that contain secrets — redact in show/get output
      const SECRET_KEYS = new Set(["apiKey"]);

      // Boolean config fields — coerce "true"/"1"/"yes" on set
      const BOOLEAN_KEYS = new Set([
        "enableGraph",
        "autoRecall",
        "autoCapture",
      ]);

      // Integer config fields — coerce to number on set
      const INTEGER_KEYS = new Set(["topK"]);

      /** Resolve a user-facing key to the internal camelCase field name. */
      function resolveConfigKey(key: string): string | null {
        return CONFIG_KEYS[key] ?? null;
      }

      /** Read a config value by internal field name. */
      function getConfigValue(field: string): unknown {
        const auth = readPluginAuth();
        const values: Record<string, unknown> = {
          apiKey: auth.apiKey ?? cfg.apiKey,
          baseUrl: auth.baseUrl ?? cfg.baseUrl ?? "https://api.mem0.ai",
          userId: auth.userId ?? cfg.userId,
          orgId: auth.orgId ?? cfg.orgId,
          projectId: auth.projectId ?? cfg.projectId,
          mode: auth.mode ?? cfg.mode,
          enableGraph: cfg.enableGraph,
          autoRecall: cfg.autoRecall,
          autoCapture: cfg.autoCapture,
          topK: cfg.topK,
        };
        return values[field];
      }

      /** Redact a secret value for display: first 4 + ... + last 4 */
      function redact(value: string): string {
        if (value.length <= 8) return value.slice(0, 2) + "***";
        return value.slice(0, 4) + "..." + value.slice(-4);
      }

      /** Format a config value for display (redacts secrets). */
      function displayValue(field: string, value: unknown): string {
        if (value === undefined || value === null || value === "") {
          return "(not set)";
        }
        if (SECRET_KEYS.has(field) && typeof value === "string") {
          return redact(value);
        }
        return String(value);
      }

      configCmd
        .command("show")
        .description("Show current configuration")
        .action(() => {
          // Display order matching Python CLI: platform first, then defaults
          const entries: Array<[string, string, string]> = [
            ["platform.api_key", "apiKey", ""],
            ["platform.base_url", "baseUrl", ""],
            ["defaults.user_id", "userId", ""],
            ["defaults.org_id", "orgId", ""],
            ["defaults.project_id", "projectId", ""],
            ["defaults.enable_graph", "enableGraph", ""],
            ["defaults.auto_recall", "autoRecall", ""],
            ["defaults.auto_capture", "autoCapture", ""],
            ["defaults.top_k", "topK", ""],
            ["mode", "mode", ""],
          ];

          // Calculate column widths
          const maxKeyLen = Math.max(
            ...entries.map(([k]) => k.length),
            3,
          );

          console.log("");
          console.log(
            `  ${"Key".padEnd(maxKeyLen)}   Value`,
          );
          console.log(
            `  ${"─".repeat(maxKeyLen)}   ${"─".repeat(30)}`,
          );
          for (const [displayKey, field] of entries) {
            const value = getConfigValue(field);
            const display = displayValue(field, value);
            console.log(
              `  ${displayKey.padEnd(maxKeyLen)}   ${display}`,
            );
          }
          console.log("");
          console.log(`  Config file: ${OPENCLAW_CONFIG_FILE}`);
          console.log("");
          console.log("  To change a setting:");
          console.log("    openclaw mem0 config set <key> <value>");
          console.log("");
          console.log("  Examples:");
          console.log("    openclaw mem0 config set mode open-source");
          console.log("    openclaw mem0 config set mode platform");
          console.log("    openclaw mem0 config set auto_recall false");
          console.log("    openclaw mem0 config set top_k 10");
          console.log("");
        });

      configCmd
        .command("get")
        .description("Get a config value")
        .argument("<key>", "Config key (e.g. user_id, platform.api_key)")
        .action((key: string) => {
          const field = resolveConfigKey(key);
          if (!field) {
            console.error(
              `Unknown config key: ${key}`,
            );
            return;
          }
          const value = getConfigValue(field);
          console.log(displayValue(field, value));
        });

      configCmd
        .command("set")
        .description("Set a config value")
        .argument("<key>", "Config key (e.g. user_id, platform.api_key)")
        .argument("<value>", "New value")
        .action((key: string, rawValue: string) => {
          const field = resolveConfigKey(key);
          if (!field) {
            console.error(
              `Unknown config key: ${key}`,
            );
            return;
          }

          // Type coercion (matches Python CLI behavior)
          let value: unknown = rawValue;
          if (BOOLEAN_KEYS.has(field)) {
            value =
              rawValue.toLowerCase() === "true" ||
              rawValue === "1" ||
              rawValue.toLowerCase() === "yes";
          } else if (INTEGER_KEYS.has(field)) {
            const parsed = parseInt(rawValue, 10);
            if (isNaN(parsed)) {
              console.error(`Invalid integer value: ${rawValue}`);
              return;
            }
            value = parsed;
          }

          writePluginAuth({ [field]: value } as PluginAuthConfig);
          console.log(
            `${key} = ${displayValue(field, value)}`,
          );
        });

      // ====================================================================
      // help (matches: mem0 help, mem0 help --json)
      // ====================================================================

      mem0
        .command("help")
        .description("Show help. Use --json for machine-readable output (for LLM agents)")
        .option("--json", "Output as JSON for agent/programmatic use")
        .action((opts: { json?: boolean }) => {
          const commands = {
            memory: {
              add: "Add a memory from text, messages, or stdin",
              search: "Query your memory store — semantic, keyword, or hybrid retrieval",
              get: "Get a specific memory by ID",
              list: "List memories with optional filters",
              update: "Update a memory's text or metadata",
              delete: "Delete a memory, all memories, or an entity",
              history: "View edit history of a memory",
            },
            management: {
              init: "Interactive setup wizard for mem0 CLI",
              status: "Check connectivity and authentication",
              help: "Show help. Use --json for machine-readable output (for LLM agents)",
              config: "Manage mem0 configuration (show, get, set)",
              dream: "Run memory consolidation (review, merge, prune)",
            },
          };

          if (opts.json) {
            console.log(JSON.stringify({ commands }, null, 2));
            return;
          }

          console.log("");
          console.log("  openclaw mem0 <command>");
          console.log("");
          console.log("  Memory:");
          for (const [cmd, desc] of Object.entries(commands.memory)) {
            console.log(`    ${cmd.padEnd(12)} ${desc}`);
          }
          console.log("");
          console.log("  Management:");
          for (const [cmd, desc] of Object.entries(commands.management)) {
            console.log(`    ${cmd.padEnd(12)} ${desc}`);
          }
          console.log("");
        });

      // ====================================================================
      // dream
      // ====================================================================

      mem0
        .command("dream")
        .description(
          "Run memory consolidation (review, merge, prune stored memories)",
        )
        .option(
          "--dry-run",
          "Show memory inventory without running consolidation",
        )
        .action(async (opts: { dryRun?: boolean }) => {
          try {
            const uid = cfg.userId;
            const memories = await provider.getAll({
              user_id: uid,
            });
            const count = Array.isArray(memories) ? memories.length : 0;

            if (count === 0) {
              console.log("No memories to consolidate.");
              return;
            }

            const catCounts = new Map<string, number>();
            for (const mem of memories) {
              const cat =
                (mem.metadata as any)?.category ??
                mem.categories?.[0] ??
                "uncategorized";
              catCounts.set(cat, (catCounts.get(cat) ?? 0) + 1);
            }
            process.stderr.write(`\nMemory inventory for "${uid}":\n`);
            for (const [cat, num] of [...catCounts.entries()].sort(
              (a, b) => b[1] - a[1],
            )) {
              process.stderr.write(`  ${cat}: ${num}\n`);
            }
            process.stderr.write(`  TOTAL: ${count}\n\n`);

            if (opts.dryRun) {
              process.stderr.write("Dry run — no changes made.\n");
              return;
            }

            const dreamPrompt = loadDreamPrompt(cfg.skills ?? {});
            if (!dreamPrompt) {
              process.stderr.write(
                "Dream skill file not found at skills/memory-dream/SKILL.md\n",
              );
              return;
            }

            const memoryDump = (memories as MemoryItem[])
              .map((m, i) => {
                const cat =
                  (m.metadata as any)?.category ??
                  m.categories?.[0] ??
                  "uncategorized";
                const imp = (m.metadata as any)?.importance ?? "?";
                const created = m.created_at ?? "unknown";
                return `${i + 1}. [${m.id}] (${cat}, importance: ${imp}, created: ${created}) ${m.memory}`;
              })
              .join("\n");

            const fullPrompt = [
              "<dream-protocol>",
              dreamPrompt,
              "</dream-protocol>",
              "",
              `<all-memories count="${count}" user="${uid}">`,
              memoryDump,
              "</all-memories>",
              "",
              "Begin consolidation. Review all memories above and execute merge, delete, and rewrite operations using the available tools.",
            ].join("\n");

            process.stdout.write(fullPrompt + "\n");
            process.stderr.write(
              `Dream prompt written to stdout (${fullPrompt.length} chars). Paste it into an OpenClaw session to run consolidation.\n`,
            );
          } catch (err) {
            console.error(`Dream failed: ${String(err)}`);
          }
        });
    },
    {
      commands: ["mem0"],
      descriptors: [
        { name: "mem0", description: "Mem0 memory plugin commands" },
      ],
    },
  );
}
