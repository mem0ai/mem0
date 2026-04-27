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
 *   - import      : Import memories from a JSON file
 *
 * Management:
 *   - init        : Authenticate with Mem0 Platform (email or API key)
 *   - status      : Check API connectivity and show current config
 *   - config show : Display current plugin configuration
 *   - config get  : Get a single config value
 *   - config set  : Update a plugin config field
 *   - event list  : List recent background events
 *   - event status: Get status of a specific event
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
import { readText } from "../fs-safe.ts";
import type { PluginAuthConfig } from "./config-file.ts";
import {
  readPluginAuth,
  writePluginAuth,
  writePluginConfigField,
  enableSkillsConfig,
  OPENCLAW_CONFIG_FILE,
} from "./config-file.ts";
import { jsonOut, jsonErr, redactSecrets } from "./json-helpers.ts";
import {
  LLM_PROVIDERS, EMBEDDER_PROVIDERS, VECTOR_PROVIDERS,
  buildOssLlmConfig, buildOssEmbedderConfig, buildOssVectorConfig,
  validateOssFlags, checkQdrantConnectivity, checkOllamaConnectivity, checkPgConnectivity,
  collectionNameForDims,
} from "./oss-wizard.ts";

// ============================================================================
// Reusable helpers (DRY)
// ============================================================================

/** Prompt user for input on stderr (keeps stdout clean for piping). */
function promptInput(question: string, prefill?: string): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stderr });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
    if (prefill) rl.write(prefill);
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
      headers: {
        "Content-Type": "application/json",
        "X-Mem0-Source": "OPENCLAW",
        "X-Mem0-Client-Language": "node",
      },
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
): Promise<{ ok: boolean; status?: number; error?: string; userEmail?: string }> {
  try {
    const resp = await fetch(`${baseUrl}/v1/ping/`, {
      headers: {
        Authorization: `Token ${apiKey}`,
        "X-Mem0-Source": "OPENCLAW",
        "X-Mem0-Client-Language": "node",
      },
    });
    if (!resp.ok) return { ok: false, status: resp.status };
    try {
      const data = (await resp.json()) as Record<string, unknown>;
      return { ok: true, userEmail: data.user_email as string | undefined };
    } catch {
      return { ok: true };
    }
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
  userIdFlag?: string,
  userEmail?: string,
  silent?: boolean,
): void {
  const existingAuth = readPluginAuth();
  const userId = resolveUserId(userIdFlag, existingAuth.userId);

  writePluginAuth({ apiKey, userId, mode: "platform", ...(userEmail && { userEmail }) });
  enableSkillsConfig(userId);

  if (!silent) {
    console.log(`  Configuration saved to ${OPENCLAW_CONFIG_FILE}`);
    console.log(`  Mode: platform (skills enabled)`);
    console.log(`  User ID: ${userId}`);
  }
}

function saveOssConfig(userIdFlag?: string, silent?: boolean): void {
  const existingAuth = readPluginAuth();
  const userId = resolveUserId(userIdFlag, existingAuth.userId);

  writePluginAuth({ apiKey: "", userId, mode: "open-source" });
  enableSkillsConfig(userId);

  if (!silent) {
    console.log(`  Configuration saved to ${OPENCLAW_CONFIG_FILE}`);
    console.log(`  Mode: open-source (skills enabled)`);
    console.log(`  User ID: ${userId}`);
  }
}

async function runOssWizardInteractive(
  opts: { userId?: string; json?: boolean },
  existingAuth: PluginAuthConfig,
): Promise<void> {
  // === Step 1: LLM Provider ===
  console.log("\n  Step 1/4 — LLM Provider\n");
  LLM_PROVIDERS.forEach((p, i) => console.log(`    ${i + 1}. ${p.label}`));
  console.log("");
  const llmIdx = parseInt(await promptInput(`  Choice (1-${LLM_PROVIDERS.length}): `) || "1", 10) - 1;
  const llmDef = LLM_PROVIDERS[llmIdx] || LLM_PROVIDERS[0];

  let llmApiKey: string | undefined;
  let llmUrl: string | undefined;
  if (llmDef.needsApiKey) {
    llmApiKey = await promptInput(`  ${llmDef.envVar} API Key (Enter to use env var): `);
    if (!llmApiKey) llmApiKey = undefined;
  }
  if (llmDef.needsUrl) {
    llmUrl = await promptInput(`  Base URL: `, llmDef.defaultUrl) || llmDef.defaultUrl;
  }

  const llmCfg = buildOssLlmConfig(llmDef.id, { apiKey: llmApiKey, url: llmUrl });

  if (llmDef.id === "ollama") {
    const ollamaUrl = (llmCfg.config.url as string) || "http://localhost:11434";
    const check = await checkOllamaConnectivity(ollamaUrl);
    if (!check.ok) {
      console.error(`\n  ⚠ Ollama not reachable at ${ollamaUrl}. Install: https://ollama.com/download\n`);
      return;
    }
    console.log("  ✓ Ollama connected");
  }

  writePluginConfigField(["oss", "llm"], llmCfg);

  // === Step 2: Embedding Provider ===
  console.log("\n  Step 2/4 — Embedding Provider\n");
  EMBEDDER_PROVIDERS.forEach((p, i) => console.log(`    ${i + 1}. ${p.label}`));
  console.log("");
  const embIdx = parseInt(await promptInput(`  Choice (1-${EMBEDDER_PROVIDERS.length}): `) || "1", 10) - 1;
  const embDef = EMBEDDER_PROVIDERS[embIdx] || EMBEDDER_PROVIDERS[0];

  let embApiKey: string | undefined;
  let embUrl: string | undefined;
  if (embDef.needsApiKey) {
    if (embDef.id === llmDef.id && llmApiKey) {
      console.log(`  Reusing ${llmDef.id} API key from Step 1`);
      embApiKey = llmApiKey;
    } else {
      embApiKey = await promptInput(`  ${embDef.envVar} API Key (Enter to use env var): `);
      if (!embApiKey) embApiKey = undefined;
    }
  }
  if (embDef.needsUrl) {
    if (embDef.id === llmDef.id && llmUrl) {
      console.log(`  Reusing ${llmDef.id} base URL from Step 1`);
      embUrl = llmUrl;
    } else {
      embUrl = await promptInput(`  Base URL: `, embDef.defaultUrl) || embDef.defaultUrl;
    }
  }

  const embCfg = buildOssEmbedderConfig(embDef.id, { apiKey: embApiKey, url: embUrl });

  if (embDef.id === "ollama" && embDef.id !== llmDef.id) {
    const ollamaUrl = (embCfg.config.url as string) || "http://localhost:11434";
    const check = await checkOllamaConnectivity(ollamaUrl);
    if (!check.ok) {
      console.error(`\n  ⚠ Ollama not reachable at ${ollamaUrl}. Install: https://ollama.com/download\n`);
      return;
    }
    console.log("  ✓ Ollama connected");
  }

  writePluginConfigField(["oss", "embedder"], { provider: embCfg.provider, config: embCfg.config });
  const dims = embCfg.dims ?? embDef.defaultDims;

  // === Step 3: Vector Store ===
  console.log("\n  Step 3/4 — Vector Store\n");
  VECTOR_PROVIDERS.forEach((p, i) => console.log(`    ${i + 1}. ${p.label}`));
  console.log("");
  const vecIdx = parseInt(await promptInput(`  Choice (1-${VECTOR_PROVIDERS.length}): `) || "1", 10) - 1;
  const vecDef = VECTOR_PROVIDERS[vecIdx] || VECTOR_PROVIDERS[0];

  let vecInput: Record<string, string | number | undefined> = { dims };
  if (vecDef.id === "qdrant") {
    if (vecDef.setupHint) console.log(`\n  Hint: ${vecDef.setupHint}`);
    console.log("");
    const url = await promptInput(`  Qdrant URL: `, vecDef.defaultUrl) || vecDef.defaultUrl;
    vecInput = { url, dims };

    const check = await checkQdrantConnectivity(url!);
    if (!check.ok) {
      console.error(`\n  ⚠ Qdrant not reachable at ${url}. Start with: docker run -d -p 6333:6333 qdrant/qdrant\n`);
      return;
    }
    console.log("  ✓ Qdrant connected");
  } else if (vecDef.id === "pgvector") {
    if (vecDef.setupHint) console.log(`\n  Hint: ${vecDef.setupHint}`);
    console.log("");
    const host = await promptInput("  Host [localhost]: ") || "localhost";
    const port = await promptInput("  Port [5432]: ") || "5432";
    const user = await promptInput("  User: ");
    const password = await promptInput("  Password: ");
    const dbname = await promptInput("  Database [postgres]: ") || "postgres";
    vecInput = { host, port, user, password, dbname, dims };

    const check = await checkPgConnectivity(host, parseInt(port, 10));
    if (!check.ok) {
      console.error(`\n  ⚠ PostgreSQL not reachable at ${host}:${port}. ${vecDef.setupHint ? `Start with: ${vecDef.setupHint}` : ""}\n`);
      return;
    }
    console.log("  ✓ PostgreSQL connected");
  }

  const vecCfg = buildOssVectorConfig(vecDef.id, vecInput as any);

  // Warn if switching embedder dimensions — old collection will have wrong vector size
  const existingVecCfg = existingAuth as any;
  const oldDims = existingVecCfg?.oss?.vectorStore?.config?.dimension as number | undefined;
  if (oldDims && dims && oldDims !== dims) {
    console.log(`\n  ⚠ Dimension change detected: ${oldDims} → ${dims}`);
    console.log(`    Old collection had ${oldDims}-dim vectors. New embedder produces ${dims}-dim vectors.`);
    console.log(`    A new collection "${collectionNameForDims(dims)}" will be created.`);
    console.log(`    Old memories in the previous collection will NOT be accessible with the new embedder.\n`);
  }

  writePluginConfigField(["oss", "vectorStore"], vecCfg);

  // === Step 4: User ID ===
  console.log("\n  Step 4/4 — User ID\n");
  let userIdValue = opts.userId;
  if (!userIdValue) {
    const defaultUid = resolveUserId(undefined, existingAuth.userId);
    const uidInput = await promptInput(`  User ID: `, defaultUid);
    userIdValue = uidInput || defaultUid;
  }

  console.log("");
  saveOssConfig(userIdValue);

  console.log("");
  console.log("  Open-source mode configured!");
  console.log("");
  console.log(`    LLM:       ${llmDef.id} (${llmCfg.config.model})`);
  console.log(`    Embedder:  ${embDef.id} (${embCfg.config.model})`);
  console.log(`    Vector:    ${vecDef.id} (${vecDef.id === "qdrant" ? vecCfg.config.url : vecCfg.config.host})`);
  console.log(`    Dims:      ${dims ?? "unknown"}`);
  console.log(`    Collection:${dims ? " " + collectionNameForDims(dims) : " (default)"}`);
  console.log(`    User ID:   ${userIdValue}`);
  console.log("");
  console.log("  Run: openclaw gateway restart");
  console.log("");
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
  captureCliEvent?: (command: string) => void,
): void {
  api.registerCli(
    ({ program }) => {
      const mem0 = program
        .command("mem0")
        .description("Mem0 memory plugin commands\n\nTip: All commands support --json for machine-readable output (for LLM agents)")
        .configureHelp({ sortSubcommands: false, subcommandTerm: (cmd) => cmd.name() });

      // Telemetry: fire event for each CLI subcommand
      if (captureCliEvent) {
        mem0.hook("preAction", (_thisCmd, actionCmd) => {
          try {
            const name = actionCmd.name();
            const parent = actionCmd.parent?.name();
            const full = parent && parent !== "mem0" ? `${parent}.${name}` : name;
            captureCliEvent(full);
          } catch { /* silently swallow */ }
        });
      }

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
        .option("--mode <mode>", "platform or open-source (skips menu)")
        .option("--oss-llm <provider>", "LLM: openai, ollama, anthropic")
        .option("--oss-llm-key <key>", "API key for LLM provider")
        .option("--oss-llm-model <model>", "Override default LLM model")
        .option("--oss-llm-url <url>", "Base URL (ollama only)")
        .option("--oss-embedder <provider>", "Embedder: openai, ollama, huggingface")
        .option("--oss-embedder-key <key>", "API key for embedder")
        .option("--oss-embedder-model <model>", "Override default embedder model")
        .option("--oss-embedder-url <url>", "Base URL (ollama only)")
        .option("--oss-vector <provider>", "Vector store: qdrant, pgvector")
        .option("--oss-vector-url <url>", "Qdrant server URL (default: http://localhost:6333)")
        .option("--oss-vector-host <host>", "PGVector host")
        .option("--oss-vector-port <port>", "PGVector port")
        .option("--oss-vector-user <user>", "PGVector user")
        .option("--oss-vector-password <pw>", "PGVector password")
        .option("--oss-vector-dbname <db>", "PGVector database name")
        .option("--oss-vector-dims <n>", "Override embedding dimensions")
        .option("--json", "Machine-readable JSON output")
        .action(
          async (opts: {
            email?: string;
            code?: string;
            apiKey?: string;
            userId?: string;
            mode?: string;
            ossLlm?: string;
            ossLlmKey?: string;
            ossLlmModel?: string;
            ossLlmUrl?: string;
            ossEmbedder?: string;
            ossEmbedderKey?: string;
            ossEmbedderModel?: string;
            ossEmbedderUrl?: string;
            ossVector?: string;
            ossVectorUrl?: string;
            ossVectorHost?: string;
            ossVectorPort?: string;
            ossVectorUser?: string;
            ossVectorPassword?: string;
            ossVectorDbname?: string;
            ossVectorDims?: string;
            json?: boolean;
          }) => {
            try {
              const baseUrl = "https://api.mem0.ai";
              const existingAuth = readPluginAuth();
              const hasExistingConfig = !!(existingAuth.apiKey || existingAuth.mode);

              // -- Non-interactive OSS via --mode open-source + flags --
              if (opts.mode === "open-source") {
                const validation = validateOssFlags(opts);
                if (validation.error) {
                  if (jsonErr(opts, validation.error)) return;
                  console.error(validation.error);
                  return;
                }

                const llmId = opts.ossLlm || "openai";
                const embId = opts.ossEmbedder || "openai";
                const vecId = opts.ossVector || "qdrant";

                const embKey = opts.ossEmbedderKey || (embId === llmId ? opts.ossLlmKey : undefined);
                const embUrl = opts.ossEmbedderUrl || (embId === llmId ? opts.ossLlmUrl : undefined);

                const llmCfg = buildOssLlmConfig(llmId, {
                  apiKey: opts.ossLlmKey, model: opts.ossLlmModel, url: opts.ossLlmUrl,
                });
                const embCfg = buildOssEmbedderConfig(embId, {
                  apiKey: embKey, model: opts.ossEmbedderModel, url: embUrl,
                });
                const dims = opts.ossVectorDims ? parseInt(opts.ossVectorDims, 10) : embCfg.dims;
                const vecCfg = buildOssVectorConfig(vecId, {
                  url: opts.ossVectorUrl, host: opts.ossVectorHost,
                  port: opts.ossVectorPort, user: opts.ossVectorUser,
                  password: opts.ossVectorPassword, dbname: opts.ossVectorDbname,
                  dims,
                });

                // Connectivity checks — Ollama, Qdrant, PGVector
                const ollamaUrls = new Set<string>();
                if (llmId === "ollama") ollamaUrls.add((llmCfg.config.url as string) || "http://localhost:11434");
                if (embId === "ollama") ollamaUrls.add((embCfg.config.url as string) || "http://localhost:11434");
                for (const oUrl of ollamaUrls) {
                  const check = await checkOllamaConnectivity(oUrl);
                  if (!check.ok) {
                    const msg = `Ollama not reachable at ${oUrl}. Install: https://ollama.com/download`;
                    if (jsonErr(opts, msg)) return;
                    console.error(`\n  ${msg}\n`);
                    return;
                  }
                }

                if (vecId === "qdrant") {
                  const qdrantUrl = (vecCfg.config.url as string) || "http://localhost:6333";
                  const check = await checkQdrantConnectivity(qdrantUrl);
                  if (!check.ok) {
                    const msg = `Qdrant not reachable at ${qdrantUrl}. Start with: docker run -d -p 6333:6333 qdrant/qdrant`;
                    if (jsonErr(opts, msg)) return;
                    console.error(`\n  ${msg}\n`);
                    return;
                  }
                } else if (vecId === "pgvector") {
                  const pgHost = (vecCfg.config.host as string) || "localhost";
                  const pgPort = (vecCfg.config.port as number) || 5432;
                  const check = await checkPgConnectivity(pgHost, pgPort);
                  if (!check.ok) {
                    const msg = `PostgreSQL not reachable at ${pgHost}:${pgPort}. Start with: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres pgvector/pgvector:pg17`;
                    if (jsonErr(opts, msg)) return;
                    console.error(`\n  ${msg}\n`);
                    return;
                  }
                }

                // Warn on dimension change
                const prevAuth = readPluginAuth() as any;
                const prevDims = prevAuth?.oss?.vectorStore?.config?.dimension as number | undefined;
                const newDims = dims;
                let dimWarning: string | undefined;
                if (prevDims && newDims && prevDims !== newDims) {
                  dimWarning = `Dimension change: ${prevDims} → ${newDims}. New collection "${collectionNameForDims(newDims)}" will be used. Old memories not accessible with new embedder.`;
                }

                writePluginConfigField(["oss", "llm"], llmCfg);
                writePluginConfigField(["oss", "embedder"], { provider: embCfg.provider, config: embCfg.config });
                writePluginConfigField(["oss", "vectorStore"], vecCfg);
                saveOssConfig(opts.userId, !!opts.json);

                const vecDisplay = vecId === "qdrant" ? vecCfg.config.url : vecCfg.config.host;
                const summary = {
                  ok: true as const,
                  mode: "open-source",
                  config: {
                    llm: { provider: llmCfg.provider, model: llmCfg.config.model },
                    embedder: { provider: embCfg.provider, model: embCfg.config.model, dims: newDims },
                    vectorStore: { provider: vecCfg.provider, ...(vecId === "qdrant" ? { url: vecCfg.config.url } : { host: vecCfg.config.host }), collectionName: newDims ? collectionNameForDims(newDims) : undefined },
                  },
                  ...(dimWarning && { warning: dimWarning }),
                  userId: resolveUserId(opts.userId, existingAuth.userId),
                  message: "Open-source mode configured. Restart the gateway: openclaw gateway restart",
                };
                if (jsonOut(opts, summary)) return;

                console.log("\n  Open-source mode configured!\n");
                console.log(`  LLM:       ${llmCfg.provider} (${llmCfg.config.model})`);
                console.log(`  Embedder:  ${embCfg.provider} (${embCfg.config.model})`);
                console.log(`  Vector:    ${vecCfg.provider} (${vecDisplay})`);
                console.log(`  User ID:   ${resolveUserId(opts.userId, existingAuth.userId)}`);
                console.log("\n  Restart the gateway: openclaw gateway restart\n");
                return;
              }

              // -- Non-interactive --mode platform routing -----------------
              if (opts.mode === "platform") {
                if (!opts.apiKey && !opts.email) {
                  const msg = "--api-key or --email required for platform mode";
                  if (jsonErr(opts, msg)) return;
                  console.error(msg);
                  return;
                }
                // fall through to existing --api-key / --email handlers below
              }

              // -- API key flow ------------------------------------------------
              if (opts.apiKey) {
                if (opts.email) {
                  const msg = "Cannot use both --api-key and --email.";
                  if (jsonErr(opts, msg)) return;
                  console.error(msg);
                  return;
                }

                const check = await validateApiKey(baseUrl, opts.apiKey);
                saveLoginConfig(opts.apiKey, opts.userId, check.userEmail, !!opts.json);

                let message: string;
                if (check.ok) {
                  message = "API key validated. Connected to Mem0 Platform.";
                } else if (check.status) {
                  message = `API key saved but validation returned HTTP ${check.status}. Check that the key is correct.`;
                } else {
                  message = `API key saved but could not reach ${baseUrl}: ${check.error}. Check your network connection.`;
                }

                const summary = {
                  ok: check.ok,
                  mode: "platform" as const,
                  userId: resolveUserId(opts.userId, existingAuth.userId),
                  validated: check.ok,
                  ...(check.status && !check.ok && { httpStatus: check.status }),
                  message,
                };
                if (jsonOut(opts, summary)) return;

                if (hasExistingConfig) {
                  console.log(
                    "  Existing configuration detected — updated API key (other settings preserved).",
                  );
                }
                if (check.ok) {
                  console.log(`  ${message}`);
                } else {
                  console.warn(`  ${message}`);
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
                if (!apiKey) {
                  if (jsonErr(opts, "Email verification failed — no API key returned.")) return;
                  return;
                }

                saveLoginConfig(apiKey, opts.userId, email, !!opts.json);
                const summary = {
                  ok: true as const,
                  mode: "platform" as const,
                  userId: resolveUserId(opts.userId, existingAuth.userId),
                  email,
                  message: "Authenticated. Restart the gateway: openclaw gateway restart",
                };
                if (jsonOut(opts, summary)) return;

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
                  const nextCmd = `openclaw mem0 init --email ${email} --code <CODE>`;
                  if (jsonOut(opts, { ok: true, email, codeSent: true, nextCommand: nextCmd })) return;
                  console.log(
                    `Verification code sent! Run:\n  ${nextCmd}`,
                  );
                } else {
                  if (jsonErr(opts, `Failed to send verification code to ${email}.`)) return;
                }
                return;
              }

              // -- No flags: interactive flow -----------------------------------
              if (!process.stdin.isTTY) {
                console.log("Usage (non-interactive):");
                console.log("  Platform:");
                console.log("    openclaw mem0 init --api-key <key>");
                console.log("    openclaw mem0 init --api-key <key> --user-id <id>");
                console.log("    openclaw mem0 init --email <email>");
                console.log("    openclaw mem0 init --email <email> --code <c>");
                console.log("  Open Source:");
                console.log("    openclaw mem0 init --mode open-source --oss-llm ollama --oss-embedder ollama --oss-vector qdrant");
                console.log("    openclaw mem0 init --mode open-source --oss-llm openai --oss-llm-key <key>");
                console.log("  Add --json for machine-readable output.");
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
                console.log("");

                // Validate existing key before asking
                if (existingAuth.apiKey) {
                  const check = await validateApiKey(
                    baseUrl,
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
                  "  Keep existing configuration? (y/n): ",
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
              console.log("  How would you like to use Mem0?");
              console.log("  1. Platform (recommended) — hosted memory, managed by Mem0");
              console.log("  2. Open Source — self-hosted, choose your own providers\n");

              const modeChoice = (await promptInput("  Choice (1/2): ")) || "1";

              if (modeChoice === "1") {
                console.log("\n  How would you like to authenticate?");
                console.log("  1. Login with email (recommended)");
                console.log("  2. Enter API key manually\n");
                const authChoice = (await promptInput("  Choice (1/2): ")) || "1";

                if (authChoice === "1") {
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
                    `  User ID: `, defaultUid,
                  );
                  userIdValue = uidInput || defaultUid;
                }

                console.log("");
                saveLoginConfig(apiKey, userIdValue, email);
                console.log("  Authenticated!");
                console.log(
                  "  Restart the gateway: openclaw gateway restart\n",
                );
                } else if (authChoice === "2") {
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
                    `  User ID: `, defaultUid,
                  );
                  userIdValue2 = uidInput || defaultUid;
                }

                console.log("");
                const check = await validateApiKey(baseUrl, key);
                saveLoginConfig(key, userIdValue2, check.userEmail);

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
                } else {
                  console.log("Invalid choice. Run `openclaw mem0 init` again.");
                }
              } else if (modeChoice === "2") {
                await runOssWizardInteractive(opts, existingAuth);
              } else {
                console.log("Invalid choice. Run `openclaw mem0 init` again.");
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
        .option("--json", "Output as JSON")
        .action(
          async (
            query: string,
            opts: {
              topK: string;
              scope: string;
              agentId?: string;
              userId?: string;
              json?: boolean;
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
                base.threshold = 0.1;
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
                if (jsonOut(opts, { ok: true, results: [] })) return;
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
              if (jsonOut(opts, { ok: true, results: output })) return;
              console.log(JSON.stringify(output, null, 2));
            } catch (err) {
              if (jsonErr(opts, `Search failed: ${String(err)}`)) return;
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
        .option("--json", "Output as JSON")
        .action(
          async (
            text: string,
            opts: { userId?: string; agentId?: string; json?: boolean },
          ) => {
            try {
              const uid = opts.userId
                ? opts.userId
                : opts.agentId
                  ? agentUserId(opts.agentId)
                  : effectiveUserId(getCurrentSessionId());
              const result = await provider.add(
                [{ role: "user", content: text }],
                { user_id: uid, source: "OPENCLAW" },
              );
              const count = result.results?.length ?? 0;
              if (jsonOut(opts, { ok: true, memories: (result.results || []).map((r: any) => ({ id: r.id, memory: r.memory, event: r.event })) })) return;
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
              if (jsonErr(opts, `Add failed: ${String(err)}`)) return;
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
        .option("--json", "Output as JSON")
        .action(async (memoryId: string, opts: { json?: boolean } = {}) => {
          try {
            const memory = await provider.get(memoryId);
            if (jsonOut(opts, { ok: true, memory: { id: memory.id, memory: memory.memory, user_id: memory.user_id, categories: memory.categories, metadata: memory.metadata, created_at: memory.created_at, updated_at: memory.updated_at } })) return;
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
            if (jsonErr(opts, `Get failed: ${String(err)}`)) return;
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
        .option("--json", "Output as JSON")
        .action(
          async (opts: {
            userId?: string;
            agentId?: string;
            topK: string;
            json?: boolean;
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
                source: "OPENCLAW",
              });

              if (!Array.isArray(memories) || memories.length === 0) {
                if (jsonOut(opts, { ok: true, memories: [], count: 0 })) return;
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
              if (jsonOut(opts, { ok: true, memories: output, count: memories.length })) return;
              console.log(JSON.stringify(output, null, 2));
              console.log(`\nTotal: ${memories.length} memories`);
            } catch (err) {
              if (jsonErr(opts, `List failed: ${String(err)}`)) return;
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
        .option("--json", "Output as JSON")
        .action(async (memoryId: string, text: string, opts: { json?: boolean } = {}) => {
          try {
            await provider.update(memoryId, text);
            if (jsonOut(opts, { ok: true, memory: { id: memoryId, memory: text } })) return;
            console.log(`Memory ${memoryId} updated.`);
          } catch (err) {
            if (jsonErr(opts, `Update failed: ${String(err)}`)) return;
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
        .option("--json", "Output as JSON")
        .action(
          async (
            memoryId: string | undefined,
            opts: {
              all?: boolean;
              userId?: string;
              agentId?: string;
              confirm?: boolean;
              json?: boolean;
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
                if (jsonOut(opts, { ok: true, deleted: true, id: "all", userId: uid })) return;
                console.log(`All memories deleted for user "${uid}".`);
                return;
              }

              if (!memoryId) {
                if (jsonErr(opts, "Provide a memory_id or use --all to delete all memories.")) return;
                console.error(
                  "Provide a memory_id or use --all to delete all memories.",
                );
                return;
              }

              await provider.delete(memoryId);
              if (jsonOut(opts, { ok: true, deleted: true, id: memoryId })) return;
              console.log(`Memory ${memoryId} deleted.`);
            } catch (err) {
              if (jsonErr(opts, `Delete failed: ${String(err)}`)) return;
              console.error(`Delete failed: ${String(err)}`);
            }
          },
        );

      // ====================================================================
      // status (matches: mem0 status)
      // ====================================================================

      mem0
        .command("status")
        .description("Check API connectivity and current config")
        .option("--json", "Output as JSON")
        .action(async (opts: { json?: boolean } = {}) => {
          try {
            const auth = readPluginAuth();
            const result = await backend.status();
            if (jsonOut(opts, {
              ok: true,
              mode: cfg.mode,
              connected: result.connected,
              userId: cfg.userId,
              ...(result.url && { url: result.url }),
              ...(result.error && { error: String(result.error) }),
            })) return;
            console.log(`Mode: ${cfg.mode}`);
            console.log(`User ID: ${cfg.userId}`);
            console.log(`Config: ${OPENCLAW_CONFIG_FILE}`);
            console.log("");

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
            if (jsonErr(opts, `Status check failed: ${String(err)}`)) return;
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
        email: "userEmail",
        base_url: "baseUrl",
        user_id: "userId",
        auto_recall: "autoRecall",
        auto_capture: "autoCapture",
        top_k: "topK",
        mode: "mode",
        embedder_provider: "oss.embedder.provider",
        embedder_model: "oss.embedder.config.model",
        embedder_key: "oss.embedder.config.apiKey",
        llm_provider: "oss.llm.provider",
        llm_model: "oss.llm.config.model",
        llm_key: "oss.llm.config.apiKey",
        vector_provider: "oss.vectorStore.provider",
        vector_host: "oss.vectorStore.config.host",
        vector_port: "oss.vectorStore.config.port",
        collection_name: "oss.vectorStore.config.collectionName",
        vector_db_name: "oss.vectorStore.config.dbname",
        vector_db_user: "oss.vectorStore.config.user",
        vector_db_path: "oss.vectorStore.config.dbPath",
        history_db_path: "oss.historyDbPath",
        disable_history: "oss.disableHistory",
      };

      // Keys that contain secrets — redact in show/get output
      const SECRET_KEYS = new Set(["apiKey", "oss.embedder.config.apiKey", "oss.llm.config.apiKey"]);

      // Boolean config fields — coerce "true"/"1"/"yes" on set
      const BOOLEAN_KEYS = new Set([
        "autoRecall",
        "autoCapture",
        "oss.disableHistory",
      ]);

      // Integer config fields — coerce to number on set
      const INTEGER_KEYS = new Set(["topK", "oss.vectorStore.config.port"]);

      /** Resolve a user-facing key to the internal camelCase field name. */
      function resolveConfigKey(key: string): string | null {
        return CONFIG_KEYS[key] ?? null;
      }

      /** Read a config value by internal field name. */
      function getConfigValue(field: string): unknown {
        if (field.startsWith("oss.")) {
          const parts = field.split(".");
          let current: unknown = cfg.oss;
          for (let i = 1; i < parts.length && current != null; i++) {
            current = (current as Record<string, unknown>)[parts[i]];
          }
          return current;
        }

        const auth = readPluginAuth();
        const values: Record<string, unknown> = {
          apiKey: auth.apiKey ?? cfg.apiKey,
          baseUrl: auth.baseUrl ?? cfg.baseUrl ?? "https://api.mem0.ai",
          userId: auth.userId ?? cfg.userId,
          mode: auth.mode ?? cfg.mode,
          userEmail: auth.userEmail,
          autoRecall: cfg.autoRecall,
          autoCapture: cfg.autoCapture,
          topK: cfg.topK,
        };
        return values[field];
      }

      /** Format a config value for display (redacts secrets). */
      function displayValue(field: string, value: unknown): string {
        if (value === undefined || value === null || value === "") {
          return "(not set)";
        }
        if (SECRET_KEYS.has(field) && typeof value === "string") {
          const redacted = redactSecrets({ v: value }, new Set(["v"]));
          return redacted.v as string;
        }
        return String(value);
      }

      configCmd
        .command("show")
        .description("Show current configuration")
        .option("--json", "Output as JSON")
        .action((opts: { json?: boolean } = {}) => {
          if (opts.json) {
            const showEntries: Array<[string, string]> = [
              ["mode", "mode"],
              ["user_id", "userId"],
              ["auto_recall", "autoRecall"],
              ["auto_capture", "autoCapture"],
              ["top_k", "topK"],
            ];
            if (cfg.mode === "platform") {
              showEntries.push(["api_key", "apiKey"], ["email", "userEmail"]);
            } else {
              showEntries.push(
                ["embedder_provider", "oss.embedder.provider"],
                ["embedder_model", "oss.embedder.config.model"],
                ["embedder_key", "oss.embedder.config.apiKey"],
                ["llm_provider", "oss.llm.provider"],
                ["llm_model", "oss.llm.config.model"],
                ["llm_key", "oss.llm.config.apiKey"],
                ["vector_provider", "oss.vectorStore.provider"],
                ["history_db_path", "oss.historyDbPath"],
                ["disable_history", "oss.disableHistory"],
              );
            }
            const configObj: Record<string, unknown> = {};
            for (const [displayKey, field] of showEntries) {
              const val = getConfigValue(field);
              configObj[displayKey] = SECRET_KEYS.has(field) && typeof val === "string"
                ? (redactSecrets({ v: val }, new Set(["v"])).v)
                : val;
            }
            jsonOut(opts, { ok: true, config: configObj });
            return;
          }
          // Display order: general first, then mode-specific
          const entries: Array<[string, string]> = [
            ["mode", "mode"],
            ["user_id", "userId"],
            ["auto_recall", "autoRecall"],
            ["auto_capture", "autoCapture"],
            ["top_k", "topK"],
          ];

          if (cfg.mode === "platform") {
            entries.push(
              ["api_key", "apiKey"],
              ["email", "userEmail"],
            );
          } else {
            entries.push(
              ["embedder_provider", "oss.embedder.provider"],
              ["embedder_model", "oss.embedder.config.model"],
              ["embedder_key", "oss.embedder.config.apiKey"],
              ["llm_provider", "oss.llm.provider"],
              ["llm_model", "oss.llm.config.model"],
              ["llm_key", "oss.llm.config.apiKey"],
              ["vector_provider", "oss.vectorStore.provider"],
              ["history_db_path", "oss.historyDbPath"],
              ["disable_history", "oss.disableHistory"],
            );
          }

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
          if (cfg.mode === "platform") {
            console.log("    openclaw mem0 config set mode open-source");
            console.log("    openclaw mem0 config set auto_recall false");
          } else {
            console.log("    openclaw mem0 config set vector_provider qdrant");
            console.log("    openclaw mem0 config set llm_model gpt-4o");
            console.log("    openclaw mem0 config set embedder_provider openai");
          }
          console.log("");
        });

      configCmd
        .command("get")
        .description("Get a config value")
        .argument("<key>", "Config key (e.g. user_id, api_key, llm_model)")
        .option("--json", "Output as JSON")
        .action((key: string, opts: { json?: boolean } = {}) => {
          const field = resolveConfigKey(key);
          if (!field) {
            if (jsonErr(opts, `Unknown config key: ${key}`)) return;
            console.error(
              `Unknown config key: ${key}`,
            );
            return;
          }
          const value = getConfigValue(field);
          if (jsonOut(opts, { ok: true, key, value })) return;
          console.log(displayValue(field, value));
        });

      configCmd
        .command("set")
        .description("Set a config value")
        .argument("<key>", "Config key (e.g. user_id, api_key, llm_model)")
        .argument("<value>", "New value")
        .option("--json", "Output as JSON")
        .action((key: string, rawValue: string, opts: { json?: boolean } = {}) => {
          const field = resolveConfigKey(key);
          if (!field) {
            if (jsonErr(opts, `Unknown config key: ${key}`)) return;
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
              if (jsonErr(opts, `Invalid integer value: ${rawValue}`)) return;
              console.error(`Invalid integer value: ${rawValue}`);
              return;
            }
            value = parsed;
          }

          // Nested OSS fields use dot-path writer; flat fields use auth writer
          if (field.startsWith("oss.")) {
            writePluginConfigField(field.split("."), value);
          } else {
            writePluginAuth({ [field]: value } as PluginAuthConfig);
          }
          if (jsonOut(opts, { ok: true, key, value })) return;
          console.log(
            `${key} = ${displayValue(field, value)}`,
          );
        });

      // ====================================================================
      // import (matches: mem0 import <file>)
      // ====================================================================

      mem0
        .command("import")
        .description("Import memories from a JSON file")
        .argument("<file>", "Path to JSON file containing memories")
        .option("--user-id <userId>", "Override user ID for all imported memories")
        .option("--agent-id <agentId>", "Override agent ID for all imported memories")
        .option("--json", "Output as JSON")
        .action(
          async (
            file: string,
            opts: { userId?: string; agentId?: string; json?: boolean },
          ) => {
            try {
              let data: unknown;
              try {
                data = JSON.parse(readText(file));
              } catch (err) {
                console.error(`Failed to read file: ${String(err)}`);
                return;
              }

              const items = Array.isArray(data) ? data : [data];
              let added = 0;
              let failed = 0;

              for (const item of items) {
                const content =
                  item?.memory ?? item?.text ?? item?.content ?? "";
                if (!content) {
                  failed++;
                  continue;
                }
                try {
                  await backend.add(content, undefined, {
                    userId: opts.userId ?? item?.user_id ?? cfg.userId,
                    agentId: opts.agentId ?? item?.agent_id,
                    metadata: item?.metadata,
                  });
                  added++;
                } catch {
                  failed++;
                }
              }

              if (jsonOut(opts, { ok: true, imported: added, failed, total: items.length })) return;
              console.log(`Imported ${added} memories.`);
              if (failed) {
                console.error(`${failed} memories failed to import.`);
              }
            } catch (err) {
              if (jsonErr(opts, `Import failed: ${String(err)}`)) return;
              console.error(`Import failed: ${String(err)}`);
            }
          },
        );

      // ====================================================================
      // event (matches: mem0 event list, mem0 event status <id>)
      // ====================================================================

      const eventCmd = mem0
        .command("event")
        .description("Manage background processing events");

      eventCmd
        .command("list")
        .description("List recent background events")
        .option("--json", "Output as JSON")
        .action(async (opts: { json?: boolean } = {}) => {
          try {
            if (!backend || cfg.mode === "open-source") {
              console.log("Event tracking is only available in platform mode.");
              return;
            }
            const results = await backend.listEvents();
            if (!results.length) {
              console.log("No events found.");
              return;
            }
            if (jsonOut(opts, { ok: true, events: results })) return;

            // Table header
            const header = [
              "Event ID".padEnd(36),
              "Type".padEnd(14),
              "Status".padEnd(12),
              "Latency".padStart(10),
              "Created".padEnd(20),
            ].join("  ");
            console.log(header);
            console.log("-".repeat(header.length));

            for (const ev of results) {
              const evId = String(ev.id ?? "");
              const evType = String(ev.event_type ?? "—").padEnd(14);
              const status = String(ev.status ?? "—").padEnd(12);
              const latency = typeof ev.latency === "number"
                ? `${Math.round(ev.latency as number)}ms`
                : "—";
              const created = String(ev.created_at ?? "—")
                .slice(0, 19)
                .replace("T", " ");

              console.log(
                `${evId.padEnd(36)}  ${evType}  ${status}  ${latency.padStart(10)}  ${created}`,
              );
            }
            console.log(`\n${results.length} event${results.length !== 1 ? "s" : ""}`);
          } catch (err) {
            if (jsonErr(opts, `Failed to list events: ${String(err)}`)) return;
            console.error(`Failed to list events: ${String(err)}`);
          }
        });

      eventCmd
        .command("status")
        .description("Get status of a specific background event")
        .argument("<event_id>", "Event ID to check")
        .option("--json", "Output as JSON")
        .action(async (eventId: string, opts: { json?: boolean } = {}) => {
          try {
            if (!backend || cfg.mode === "open-source") {
              console.log("Event tracking is only available in platform mode.");
              return;
            }
            const ev = await backend.getEvent(eventId);
            if (jsonOut(opts, { ok: true, event: ev })) return;

            const status = String(ev.status ?? "—");
            const evType = String(ev.event_type ?? "—");
            const latency = typeof ev.latency === "number"
              ? `${Math.round(ev.latency as number)}ms`
              : "—";
            const created = String(ev.created_at ?? "—")
              .slice(0, 19)
              .replace("T", " ");
            const updated = String(ev.updated_at ?? "—")
              .slice(0, 19)
              .replace("T", " ");

            console.log(`Event ID:  ${eventId}`);
            console.log(`Type:      ${evType}`);
            console.log(`Status:    ${status}`);
            console.log(`Latency:   ${latency}`);
            console.log(`Created:   ${created}`);
            console.log(`Updated:   ${updated}`);

            const results = ev.results as Record<string, unknown>[] | undefined;
            if (results && Array.isArray(results) && results.length) {
              console.log(`\nResults (${results.length}):`);
              for (const r of results) {
                const memId = String(r.id ?? "").slice(0, 8);
                const data = r.data as Record<string, unknown> | undefined;
                const memory = data?.memory ?? "";
                const evName = String(r.event ?? "");
                const user = String(r.user_id ?? "");
                let detail = `${evName}  ${memory}`;
                if (user) detail += `  (user_id=${user})`;
                console.log(`  · ${detail}  (${memId})`);
              }
            }
          } catch (err) {
            if (jsonErr(opts, `Failed to get event: ${String(err)}`)) return;
            console.error(`Failed to get event: ${String(err)}`);
          }
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
              search: "Query your memory store — semantic, keyword, or hybrid retrieval",
              add: "Add a memory from text, messages, or stdin",
              get: "Get a specific memory by ID",
              list: "List memories with optional filters",
              update: "Update a memory's text or metadata",
              delete: "Delete a memory, all memories, or an entity",
              import: "Import memories from a JSON file",
            },
            management: {
              init: "Interactive setup wizard for mem0 CLI",
              status: "Check connectivity and authentication",
              config: "Manage mem0 configuration (show, get, set)",
              event: "Manage background processing events (list, status)",
              dream: "Run memory consolidation (review, merge, prune)",
              help: "Show help. Use --json for machine-readable output (for LLM agents)",
            },
          };

          if (opts.json) {
            const detailed = {
              commands: {
                memory: {
                  search: { description: "Query your memory store", flags: { "--top-k <n>": "Max results", "--scope <scope>": "Memory scope", "--user-id <id>": "Override user ID", "--agent-id <id>": "Agent namespace", "--json": "JSON output" } },
                  add: { description: "Add a memory from text", flags: { "--user-id <id>": "Override user ID", "--agent-id <id>": "Agent namespace", "--json": "JSON output" } },
                  get: { description: "Get a specific memory by ID", flags: { "--json": "JSON output" } },
                  list: { description: "List memories", flags: { "--user-id <id>": "Override user ID", "--top-k <n>": "Max results", "--json": "JSON output" } },
                  update: { description: "Update a memory's text", flags: { "--json": "JSON output" } },
                  delete: { description: "Delete a memory or all memories", flags: { "--all": "Delete all", "--confirm": "Skip confirmation", "--json": "JSON output" } },
                  import: { description: "Import memories from JSON file", flags: { "--user-id <id>": "Override user ID", "--json": "JSON output" } },
                },
                management: {
                  init: { description: "Set up Mem0", flags: { "--mode <m>": "platform or open-source", "--api-key <k>": "API key", "--email <e>": "Email login", "--oss-llm <p>": "LLM provider", "--oss-embedder <p>": "Embedder", "--oss-vector <p>": "Vector store", "--json": "JSON output" } },
                  status: { description: "Check connectivity", flags: { "--json": "JSON output" } },
                  config: { description: "Manage configuration (show, get, set)", flags: { "--json": "JSON output" } },
                  event: { description: "Manage background events (list, status)", flags: { "--json": "JSON output" } },
                  dream: { description: "Run memory consolidation", flags: { "--dry-run": "Show inventory only", "--json": "JSON output" } },
                  help: { description: "Show help", flags: { "--json": "JSON output" } },
                },
              },
            };
            process.stdout.write(JSON.stringify(detailed, null, 2) + "\n");
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
        .option("--json", "Output as JSON")
        .action(async (opts: { dryRun?: boolean; json?: boolean }) => {
          try {
            const uid = cfg.userId;
            const memories = await provider.getAll({
              user_id: uid,
              source: "OPENCLAW",
            });
            const count = Array.isArray(memories) ? memories.length : 0;

            if (count === 0) {
              if (jsonOut(opts, { ok: true, count: 0, message: "No memories to consolidate." })) return;
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

            if (opts.dryRun && opts.json) {
              jsonOut(opts, { ok: true, count, categories: Object.fromEntries(catCounts) });
              return;
            }

            if (opts.json && !opts.dryRun) {
              jsonOut(opts, { ok: true, count, message: `${count} memories available for consolidation` });
              return;
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
            if (jsonErr(opts, `Dream failed: ${String(err)}`)) return;
            console.error(`Dream failed: ${String(err)}`);
          }
        });
    },
    {
      descriptors: [
        { name: "mem0", description: "Mem0 memory plugin commands", hasSubcommands: true },
      ],
    },
  );
}
