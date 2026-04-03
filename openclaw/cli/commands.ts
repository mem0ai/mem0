/**
 * CLI subcommand registration for the OpenClaw Mem0 plugin.
 *
 * Registers all `openclaw mem0 <subcommand>` commands:
 *   - login   : Authenticate with Mem0 Platform (email or API key)
 *   - search  : Search memories
 *   - stats   : Show memory statistics
 *   - status  : Check API connectivity
 *   - dream   : Run memory consolidation
 */

import { createInterface } from "node:readline";

import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import type { Backend } from "../backend/base.ts";
import type {
  Mem0Config,
  Mem0Provider,
  MemoryItem,
  SearchOptions,
} from "../types.ts";
import { loadDreamPrompt } from "../skill-loader.ts";
import {
  readMem0Config,
  getBaseUrl,
  setPlatformAuth,
  writeMem0Config,
} from "./config-file.ts";

// ============================================================================
// Login config helpers
// ============================================================================

function prompt(question: string): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stderr });
  return new Promise((resolve) => {
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });
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
      // login
      // ====================================================================

      mem0
        .command("login")
        .description("Authenticate with Mem0 Platform")
        .option("--email <email>", "Login via email verification code")
        .option("--code <code>", "Verification code (use with --email)")
        .option("--api-key <key>", "Direct API key entry")
        .action(
          async (opts: { email?: string; code?: string; apiKey?: string }) => {
            try {
              const config = readMem0Config();
              const baseUrl = getBaseUrl(config);

              // -- API key flow ------------------------------------------------
              if (opts.apiKey) {
                if (opts.email) {
                  console.error("Cannot use both --api-key and --email.");
                  return;
                }

                setPlatformAuth(config, opts.apiKey, baseUrl);
                writeMem0Config(config);

                // Validate with ping
                try {
                  const resp = await fetch(`${baseUrl}/v1/ping/`, {
                    headers: { Authorization: `Token ${opts.apiKey}` },
                  });
                  if (resp.ok) {
                    console.log(
                      "API key saved and validated. Connected to Mem0 Platform.",
                    );
                  } else {
                    console.warn(
                      `API key saved but validation returned HTTP ${resp.status}. ` +
                        "Check that the key is correct.",
                    );
                  }
                } catch (err) {
                  console.warn(
                    `API key saved but could not reach ${baseUrl}: ${String(err)}. ` +
                      "Check your network connection.",
                  );
                }
                return;
              }

              // -- Email + code (verify) flow ----------------------------------
              if (opts.email && opts.code) {
                const email = opts.email.trim().toLowerCase();
                const url = baseUrl.replace(/\/+$/, "");

                let resp: Response;
                try {
                  resp = await fetch(`${url}/api/v1/auth/email_code/verify/`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, code: opts.code.trim() }),
                  });
                } catch (err) {
                  console.error(`Could not reach ${url}: ${String(err)}`);
                  return;
                }

                if (resp.status === 429) {
                  console.error(
                    "Too many attempts. Try again in a few minutes.",
                  );
                  return;
                }
                if (!resp.ok) {
                  let detail: string;
                  try {
                    const body = (await resp.json()) as Record<string, unknown>;
                    detail = String(body.error ?? resp.statusText);
                  } catch {
                    detail = resp.statusText;
                  }
                  console.error(`Verification failed: ${detail}`);
                  return;
                }

                const body = (await resp.json()) as Record<string, unknown>;
                const apiKey = body.api_key as string | undefined;
                if (!apiKey) {
                  console.error(
                    "Auth succeeded but no API key was returned. Contact support.",
                  );
                  return;
                }

                setPlatformAuth(config, apiKey, baseUrl);
                writeMem0Config(config);

                console.log(
                  "Authenticated! Configuration saved to ~/.mem0/config.json",
                );
                return;
              }

              // -- Email only (send code) flow ---------------------------------
              if (opts.email) {
                const email = opts.email.trim().toLowerCase();
                const url = baseUrl.replace(/\/+$/, "");

                let resp: Response;
                try {
                  resp = await fetch(`${url}/api/v1/auth/email_code/`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email }),
                  });
                } catch (err) {
                  console.error(`Could not reach ${url}: ${String(err)}`);
                  return;
                }

                if (resp.status === 429) {
                  console.error(
                    "Too many attempts. Try again in a few minutes.",
                  );
                  return;
                }
                if (!resp.ok) {
                  let detail: string;
                  try {
                    const body = (await resp.json()) as Record<string, unknown>;
                    detail = String(body.error ?? resp.statusText);
                  } catch {
                    detail = resp.statusText;
                  }
                  console.error(`Failed to send code: ${detail}`);
                  return;
                }

                console.log(
                  `Verification code sent! Run:\n  openclaw mem0 login --email ${email} --code <CODE>`,
                );
                return;
              }

              // -- No flags: interactive login flow ------------------------------
              if (!process.stdin.isTTY) {
                console.log("Usage (non-interactive):");
                console.log(
                  "  openclaw mem0 login --api-key <key>             Save API key directly",
                );
                console.log(
                  "  openclaw mem0 login --email <email>             Send verification code",
                );
                console.log(
                  "  openclaw mem0 login --email <email> --code <c>  Verify & authenticate",
                );
                return;
              }

              console.log("\n  Mem0 Login\n");
              console.log("  How would you like to authenticate?");
              console.log("  1. Login with email (recommended)");
              console.log("  2. Enter API key manually\n");

              const choice = await prompt("  Choice (1/2): ");

              if (choice === "1") {
                const email = (await prompt("  Email: ")).toLowerCase();
                if (!email) {
                  console.error("Email is required.");
                  return;
                }

                const url = baseUrl.replace(/\/+$/, "");
                let sendResp: Response;
                try {
                  sendResp = await fetch(`${url}/api/v1/auth/email_code/`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email }),
                  });
                } catch (err) {
                  console.error(`Could not reach ${url}: ${String(err)}`);
                  return;
                }

                if (sendResp.status === 429) {
                  console.error("Too many attempts. Try again later.");
                  return;
                }
                if (!sendResp.ok) {
                  let detail: string;
                  try {
                    const b = (await sendResp.json()) as Record<
                      string,
                      unknown
                    >;
                    detail = String(b.error ?? sendResp.statusText);
                  } catch {
                    detail = sendResp.statusText;
                  }
                  console.error(`Failed to send code: ${detail}`);
                  return;
                }

                console.log("  Verification code sent! Check your email.\n");
                const code = await prompt("  Code: ");
                if (!code) {
                  console.error("Code is required.");
                  return;
                }

                let verifyResp: Response;
                try {
                  verifyResp = await fetch(
                    `${url}/api/v1/auth/email_code/verify/`,
                    {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ email, code }),
                    },
                  );
                } catch (err) {
                  console.error(`Could not reach ${url}: ${String(err)}`);
                  return;
                }

                if (verifyResp.status === 429) {
                  console.error("Too many attempts. Try again later.");
                  return;
                }
                if (!verifyResp.ok) {
                  let detail: string;
                  try {
                    const b = (await verifyResp.json()) as Record<
                      string,
                      unknown
                    >;
                    detail = String(b.error ?? verifyResp.statusText);
                  } catch {
                    detail = verifyResp.statusText;
                  }
                  console.error(`Verification failed: ${detail}`);
                  return;
                }

                const verifyBody = (await verifyResp.json()) as Record<
                  string,
                  unknown
                >;
                const verifiedKey = verifyBody.api_key as string | undefined;
                if (!verifiedKey) {
                  console.error(
                    "Auth succeeded but no API key returned. Contact support.",
                  );
                  return;
                }

                setPlatformAuth(config, verifiedKey, baseUrl);
                writeMem0Config(config);
                console.log(
                  "\n  Authenticated! Configuration saved to ~/.mem0/config.json",
                );
                console.log(
                  "  Restart the gateway: openclaw gateway restart\n",
                );
              } else if (choice === "2") {
                const key = await prompt("  API Key: ");
                if (!key) {
                  console.error("API key is required.");
                  return;
                }

                setPlatformAuth(config, key, baseUrl);
                writeMem0Config(config);

                try {
                  const resp = await fetch(`${baseUrl}/v1/ping/`, {
                    headers: { Authorization: `Token ${key}` },
                  });
                  if (resp.ok) {
                    console.log(
                      "\n  API key saved and validated. Connected to Mem0 Platform.",
                    );
                  } else {
                    console.warn(
                      `\n  API key saved but validation returned HTTP ${resp.status}.`,
                    );
                  }
                } catch (err) {
                  console.warn(
                    `\n  API key saved but could not reach ${baseUrl}: ${String(err)}`,
                  );
                }
                console.log(
                  "  Restart the gateway: openclaw gateway restart\n",
                );
              } else {
                console.log("Invalid choice. Run `openclaw mem0 login` again.");
              }
            } catch (err) {
              console.error(`Login failed: ${String(err)}`);
            }
          },
        );

      // ====================================================================
      // search
      // ====================================================================

      mem0
        .command("search")
        .description("Search memories in Mem0")
        .argument("<query>", "Search query")
        .option("--limit <n>", "Max results", String(cfg.topK))
        .option(
          "--scope <scope>",
          'Memory scope: "session", "long-term", or "all"',
          "all",
        )
        .option(
          "--agent <agentId>",
          "Search a specific agent's memory namespace",
        )
        .action(
          async (
            query: string,
            opts: { limit: string; scope: string; agent?: string },
          ) => {
            try {
              const limit = parseInt(opts.limit, 10);
              const scope = opts.scope as "session" | "long-term" | "all";
              const currentSessionId = getCurrentSessionId();
              const uid = opts.agent
                ? agentUserId(opts.agent)
                : effectiveUserId(currentSessionId);

              // CLI search: build options WITHOUT source filter so users can
              // find ALL their memories, not just plugin-tagged ones.
              const cliSearchOpts = (
                userIdOverride?: string,
                lim?: number,
                runId?: string,
              ): SearchOptions => {
                const base = buildSearchOptions(userIdOverride, lim, runId);
                delete (base as any).source;
                // Use a lower threshold for explicit CLI searches
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
      // stats
      // ====================================================================

      mem0
        .command("stats")
        .description("Show memory statistics from Mem0")
        .option("--agent <agentId>", "Show stats for a specific agent")
        .action(async (opts: { agent?: string }) => {
          try {
            const uid = opts.agent ? agentUserId(opts.agent) : cfg.userId;
            const memories = await provider.getAll({
              user_id: uid,
              source: "OPENCLAW",
            });
            console.log(`Mode: ${cfg.mode}`);
            console.log(
              `User: ${uid}${opts.agent ? ` (agent: ${opts.agent})` : ""}`,
            );
            console.log(
              `Total memories: ${Array.isArray(memories) ? memories.length : "unknown"}`,
            );
            console.log(`Graph enabled: ${cfg.enableGraph}`);
            console.log(
              `Auto-recall: ${cfg.autoRecall}, Auto-capture: ${cfg.autoCapture}`,
            );
          } catch (err) {
            console.error(`Stats failed: ${String(err)}`);
          }
        });

      // ====================================================================
      // status
      // ====================================================================

      mem0
        .command("status")
        .description("Check Mem0 API connectivity")
        .action(async () => {
          try {
            const result = await backend.status();
            if (result.connected) {
              console.log("Connected to Mem0");
            } else {
              console.log("Not connected to Mem0");
            }
            if (result.mode) {
              console.log(`Mode: ${String(result.mode)}`);
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
              source: "OPENCLAW",
            });
            const count = Array.isArray(memories) ? memories.length : 0;

            if (count === 0) {
              console.log("No memories to consolidate.");
              return;
            }

            // Show current state summary on stderr (keeps stdout clean for piping)
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

            // Load dream prompt and format it with the full memory inventory
            const dreamPrompt = loadDreamPrompt(cfg.skills ?? {});
            if (!dreamPrompt) {
              process.stderr.write(
                "Dream skill file not found at skills/memory-dream/SKILL.md\n",
              );
              return;
            }

            // Build the full dream context: protocol + memory dump
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

            // Only the prompt goes to stdout — safe to pipe directly
            process.stdout.write(fullPrompt + "\n");
            process.stderr.write(
              `Dream prompt written to stdout (${fullPrompt.length} chars). Pipe with: openclaw mem0 dream | openclaw run --stdin\n`,
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
