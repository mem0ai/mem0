import type { Plugin } from "@opencode-ai/plugin";
import { MemoryClient } from "mem0ai";
import { userInfo } from "os";
import { basename } from "path";
import { existsSync } from "fs";
import { randomBytes } from "crypto";

async function getUserId($: any): Promise<string> {
  try {
    const r = await $`git config user.email`.quiet();
    const email = r.stdout.toString().trim();
    if (email) return email.split("@")[0];
  } catch {}
  try {
    return userInfo().username;
  } catch {}
  return process.env.USER || process.env.USERNAME || "unknown";
}

async function getProjectId($: any): Promise<string> {
  try {
    const r = await $`git remote get-url origin`.quiet();
    const remote = r.stdout.toString().trim();
    const m = remote.match(/[:/]([^/]+\/[^/]+?)(?:\.git)?$/);
    if (m) return m[1].replace("/", "-");
  } catch {}
  return basename(process.cwd());
}

async function getBranch($: any): Promise<string> {
  try {
    const r = await $`git branch --show-current`.quiet();
    return r.stdout.toString().trim() || "main";
  } catch {}
  return "main";
}

function extractMemories(res: any): Array<{ memory: string; id: string }> {
  const arr = res?.results ?? res;
  if (!Array.isArray(arr)) return [];
  return arr.map((m: any) => ({ memory: m.memory ?? "", id: m.id ?? "" }));
}

function generateSessionId(): string {
  const ts = Math.floor(Date.now() / 1000);
  const rnd = randomBytes(3).toString("hex");
  return `ses_${ts}_${rnd}`;
}

function detectMemoryMd(userId: string): string {
  const cwd = process.cwd();
  const cwdKey = cwd.replace(/\//g, "-").replace(/^-/, "");
  const home = process.env.HOME || process.env.USERPROFILE || "";
  const candidates = [
    `${home}/.claude/projects/${cwdKey}/memory/MEMORY.md`,
    `${home}/.claude/memory/MEMORY.md`,
    `${cwd}/MEMORY.md`,
  ];
  for (const p of candidates) {
    try {
      if (existsSync(p)) return p;
    } catch {}
  }
  return "";
}

const RESUME_RE =
  /where\s+(did\s+)?(we|I)\s+(leave|left)\s+off|continue\s+(from\s+)?(where|last)|what\s+were\s+we\s+(working|doing)|pick\s+up\s+where|resume\s+(from\s+|where\s+)|what.s\s+the\s+(current|latest)\s+(state|status)|catch\s+me\s+up|where\s+are\s+we/i;

const REMEMBER_RE =
  /remember\s+(this|that)|save\s+(this|that)\s+(fact|info|memory|note)|store\s+(this|that)|don.t\s+forget\s+(this|that)|keep\s+(this|that)\s+in\s+(mind|memory)/i;

const ERROR_STRONG_RE = /Traceback \(most recent call last\)|panic: |FATAL:|error\[E\d+\]/;
const ERROR_MULTI_RE = /(Error:|Exception:)/g;

const FILE_PATH_RE =
  /[a-zA-Z0-9_./-]+\.(py|ts|tsx|js|jsx|rs|go|rb|java|sh|json|md)\b/g;

const MEM0_MCP_RE = /^mcp__(?:mem0|plugin_mem0_mem0)__/;
const WRITE_TOOLS = new Set(["Write", "Edit", "MultiEdit"]);
const MEM0_TOOL_NAMES = new Set([
  "mcp__mem0__add_memory",
  "mcp__plugin_mem0_mem0__add_memory",
  "mcp__mem0__search_memories",
  "mcp__plugin_mem0_mem0__search_memories",
  "mcp__mem0__get_memories",
  "mcp__plugin_mem0_mem0__get_memories",
  "mcp__mem0__delete_all_memories",
  "mcp__plugin_mem0_mem0__delete_all_memories",
]);

export const Mem0Plugin: Plugin = async (ctx) => {
  const { $, client } = ctx;
  const apiKey = process.env.MEM0_API_KEY;

  if (!apiKey) {
    await client.app.log({
      body: {
        service: "mem0",
        level: "warn",
        message:
          "MEM0_API_KEY not set. Get one at https://app.mem0.ai/dashboard/api-keys",
      },
    });
    return {};
  }

  const mem0 = new MemoryClient({ apiKey });
  const userId = await getUserId($);
  const appId = await getProjectId($);
  const branch = await getBranch($);
  const stats = { adds: 0, searches: 0, messages: 0 };

  const sessionId = generateSessionId();
  let rubricShown = false;
  let msgCount = 0;

  async function handleSessionCreated() {
    try {
      stats.adds = 0;
      stats.searches = 0;
      stats.messages = 0;
      rubricShown = false;
      msgCount = 0;

      const all = await mem0.getAll({
        filters: { user_id: userId, app_id: appId },
        page: 1,
        pageSize: 1,
      });
      const count =
        (all as any)?.total_memories ??
        (all as any)?.count ??
        (all as any)?.results?.length ??
        0;

      await client.app.log({
        body: {
          service: "mem0",
          level: "info",
          message: `Mem0 Active | user=${userId} | project=${appId} | branch=${branch} | memories=${count}`,
        },
      });

      if (count === 0) {
        await client.app.log({
          body: {
            service: "mem0",
            level: "info",
            message:
              "New project with 0 memories. Run /mem0:onboard to import project files and install coding categories.",
          },
        });
      }

      const memMdPath = detectMemoryMd(userId);
      if (memMdPath) {
        await client.app.log({
          body: {
            service: "mem0",
            level: "warn",
            message: `Native MEMORY.md detected at ${memMdPath}. Consider running /mem0:import to migrate to mem0.`,
          },
        });
      }

      if (count > 0) {
        await client.app.log({
          body: {
            service: "mem0",
            level: "info",
            message:
              "Search mem0 for recent decisions and task learnings before responding. Run 2 parallel searches: one for decision type, one for task_learning type.",
          },
        });
        try {
          const res = await mem0.search(
            "recent session state decisions and learnings",
            { filters: { AND: [{ user_id: userId }, { app_id: appId }] }, topK: 5 },
          );
          const memories = extractMemories(res);
          if (memories.length > 0) {
            const lines = memories.map((m) => `- ${m.memory}`).join("\n");
            await client.app.log({
              body: {
                service: "mem0",
                level: "info",
                message: `Prior context:\n${lines}`,
              },
            });
          }
        } catch {}
      }
    } catch (err: any) {
      await client.app.log({
        body: {
          service: "mem0",
          level: "error",
          message: `Session start error: ${err?.message}`,
        },
      });
    }
  }

  async function handlePromptAppend(text: string) {
    const prompt = text ?? "";
    if (prompt.length < 20) return;

    msgCount++;
    stats.messages++;

    try {
      const hasError =
        ERROR_STRONG_RE.test(prompt) ||
        (prompt.match(ERROR_MULTI_RE) ?? []).length >= 2;

      const filePaths = [...new Set(prompt.match(FILE_PATH_RE) ?? [])].slice(0, 5);
      const hasResume = RESUME_RE.test(prompt);
      const hasRemember = REMEMBER_RE.test(prompt);

      if (!rubricShown) {
        rubricShown = true;
        await client.app.log({
          body: {
            service: "mem0",
            level: "info",
            message:
              "Mem0 searches apply when user references past work, decision questions, errors, or non-trivial tasks. Queries use noun-phrases, 2-4 parallel calls with different metadata.type filters, and include user_id + app_id.",
          },
        });
      }

      if (hasResume) {
        try {
          const [stateRes, decisionsRes] = await Promise.all([
            mem0.search("session state current task", {
              filters: {
                AND: [
                  { user_id: userId },
                  { app_id: appId },
                  { metadata: { type: "session_state" } },
                ],
              },
              topK: 3,
            }),
            mem0.search("recent decisions and learnings", {
              filters: {
                AND: [
                  { user_id: userId },
                  { app_id: appId },
                  { metadata: { type: "decision" } },
                ],
              },
              topK: 3,
            }),
          ]);
          stats.searches += 2;
          const all = [
            ...extractMemories(stateRes),
            ...extractMemories(decisionsRes),
          ];
          const seen = new Set<string>();
          const unique = all.filter((m) => {
            if (seen.has(m.id)) return false;
            seen.add(m.id);
            return true;
          });
          if (unique.length > 0) {
            const lines = unique.map((m) => `- ${m.memory}`).join("\n");
            await client.app.log({
              body: {
                service: "mem0",
                level: "info",
                message: `Session context recovered from mem0:\n${lines}\n\nThese memories provide context for resuming work.`,
              },
            });
          } else {
            await client.app.log({
              body: {
                service: "mem0",
                level: "info",
                message: "No session state found in mem0.",
              },
            });
          }
        } catch {}
      }

      if (hasRemember) {
        await client.app.log({
          body: {
            service: "mem0",
            level: "info",
            message:
              "Remember intent detected. The /mem0:remember skill auto-classifies, sets confidence=1.0, and stores verbatim.",
          },
        });
      }

      if (hasError) {
        await client.app.log({
          body: {
            service: "mem0",
            level: "info",
            message:
              "Error detected in prompt. Prior occurrences are available in mem0 via anti_pattern and task_learning type filters.",
          },
        });
      }

      if (filePaths.length > 0) {
        await client.app.log({
          body: {
            service: "mem0",
            level: "info",
            message: `File paths detected: ${filePaths.join(", ")}`,
          },
        });
      }

      if (!hasResume) {
        try {
          const res = await mem0.search(prompt, {
            filters: { AND: [{ user_id: userId }, { app_id: appId }] },
            topK: 5,
          });
          stats.searches++;
          const memories = extractMemories(res);
          if (memories.length > 0) {
            const lines = memories.map((m) => `- ${m.memory}`).join("\n");
            await client.app.log({
              body: {
                service: "mem0",
                level: "info",
                message: `Relevant memories:\n${lines}`,
              },
            });
          }
        } catch {}
      }

      if (msgCount % 3 === 0) {
        Promise.resolve().then(async () => {
          try {
            await mem0.add(
              [{ role: "user", content: prompt }],
              {
                user_id: userId,
                app_id: appId,
                metadata: {
                  type: "auto_capture",
                  source: "opencode",
                  confidence: 0.7,
                  session_id: sessionId,
                  branch,
                },
                infer: true,
              } as any,
            );
            stats.adds++;
          } catch {}
        });
      }

      if (msgCount % 5 === 0 && stats.adds < Math.floor(msgCount / 3)) {
        await client.app.log({
          body: {
            service: "mem0",
            level: "info",
            message:
              "After responding, store any new decisions, learnings, or preferences from this exchange via add_memory. Keep it to 1 sentence per memory.",
          },
        });
      }
    } catch {}
  }

  return {
    event: async ({ event }: { event: any }) => {
      if (event.type === "session.created") {
        await handleSessionCreated();
      } else if (event.type === "tui.prompt.append") {
        await handlePromptAppend(event.properties?.text ?? "");
      }
    },

    "tool.execute.before": async (input: any, output: any) => {
      const toolName: string = input?.tool ?? "";

      if (WRITE_TOOLS.has(toolName)) {
        const fp = String(
          output?.args?.file_path ?? output?.args?.filePath ?? "",
        );
        if (/MEMORY\.md|\.claude\/memory/i.test(fp)) {
          throw new Error(
            "Use the add_memory MCP tool instead of writing to MEMORY.md",
          );
        }
      }

      if (MEM0_TOOL_NAMES.has(toolName) && output?.args) {
        if (!output.args.user_id) output.args.user_id = userId;
        if (!output.args.app_id) output.args.app_id = appId;

        const isAddMemory =
          toolName === "mcp__mem0__add_memory" ||
          toolName === "mcp__plugin_mem0_mem0__add_memory";
        const isSearchOrGet =
          toolName === "mcp__mem0__search_memories" ||
          toolName === "mcp__plugin_mem0_mem0__search_memories" ||
          toolName === "mcp__mem0__get_memories" ||
          toolName === "mcp__plugin_mem0_mem0__get_memories";
        const isDeleteAll =
          toolName === "mcp__mem0__delete_all_memories" ||
          toolName === "mcp__plugin_mem0_mem0__delete_all_memories";

        if (isAddMemory) {
          if (!output.args.metadata) {
            output.args.metadata = {};
          }
          const meta = output.args.metadata;
          if (meta.confidence === undefined) meta.confidence = 0.7;
          if (!meta.source) meta.source = "opencode";
          if (!meta.type) meta.type = "task_learning";
          if (!meta.session_id) meta.session_id = sessionId;
          if (!meta.files) meta.files = ["*"];
          if (!meta.branch) meta.branch = branch;

          if (meta.confidence >= 1.0 && output.args.infer === undefined) {
            output.args.infer = false;
          }
        }

        if (isSearchOrGet) {
          const existingFilters = output.args.filters;
          if (existingFilters === undefined || existingFilters === null) {
            output.args.filters = {
              AND: [{ user_id: userId }, { app_id: appId }],
            };
          } else if (typeof existingFilters === "object") {
            const andClauses: any[] = existingFilters.AND;
            if (Array.isArray(andClauses)) {
              const hasUid = andClauses.some(
                (c: any) => c && typeof c === "object" && "user_id" in c,
              );
              const hasAid = andClauses.some(
                (c: any) => c && typeof c === "object" && "app_id" in c,
              );
              if (!hasUid) andClauses.push({ user_id: userId });
              if (!hasAid) andClauses.push({ app_id: appId });
            } else if (andClauses === undefined) {
              const hasUid = "user_id" in existingFilters;
              const hasAid = "app_id" in existingFilters;
              if (!hasUid || !hasAid) {
                const existing = Object.entries(existingFilters).map(
                  ([k, v]) => ({ [k]: v }),
                );
                if (!hasUid) existing.push({ user_id: userId });
                if (!hasAid) existing.push({ app_id: appId });
                output.args.filters = { AND: existing };
              }
            }
          }
        }

        if (isDeleteAll) {
          if (!output.args.user_id) output.args.user_id = userId;
          if (!output.args.app_id) output.args.app_id = appId;
        }

        if (!isAddMemory && !output.args.metadata) {
          output.args.metadata = { source: "opencode", branch };
        }
      }
    },

    "tool.execute.after": async (input: any, output: any) => {
      const toolName: string = input?.tool ?? "";
      const toolOutput: string = output?.output ?? "";

      if (MEM0_MCP_RE.test(toolName)) {
        if (toolName.includes("add_memory")) stats.adds++;
        if (toolName.includes("search")) stats.searches++;
      }

      if (
        toolName === "bash" &&
        /(?:Error|Exception|Traceback|FATAL)/i.test(toolOutput)
      ) {
        const command: string = input?.args?.command ?? "";
        if (
          toolOutput.length < 50 ||
          /git\s+(commit|merge|rebase)/.test(command)
        ) {
          return;
        }

        const hasStrongError = ERROR_STRONG_RE.test(toolOutput);
        const multiErrors = (toolOutput.match(ERROR_MULTI_RE) ?? []).length;
        if (!hasStrongError && multiErrors < 2) return;

        try {
          const errorLine =
            toolOutput
              .split("\n")
              .find((l) =>
                /Error:|Exception:|panic:|FAIL:|fatal:/i.test(l),
              )
              ?.replace(/^\s+/, "")
              .slice(0, 120) ?? "";

          const traceFiles = [
            ...new Set(
              toolOutput.match(
                /[a-zA-Z0-9_./-]+\.(py|ts|tsx|js|jsx|rs|go|rb|java|sh)(:\d+)?/g,
              ) ?? [],
            ),
          ].slice(0, 5);

          const errorQuery = errorLine.slice(0, 80);
          if (errorQuery.length < 10) return;

          const [antiPatternRes, bugFixRes] = await Promise.all([
            mem0.search(`error: ${errorQuery}`, {
              filters: {
                AND: [
                  { user_id: userId },
                  { app_id: appId },
                  { metadata: { type: "anti_pattern" } },
                ],
              },
              topK: 3,
            }),
            mem0.search(`error: ${errorQuery}`, {
              filters: {
                AND: [
                  { user_id: userId },
                  { app_id: appId },
                  { metadata: { type: "bug_fix" } },
                ],
              },
              topK: 3,
            }),
          ]);

          const allResults = [
            ...extractMemories(antiPatternRes),
            ...extractMemories(bugFixRes),
          ];
          const seen = new Set<string>();
          const unique = allResults.filter((m) => {
            if (seen.has(m.id)) return false;
            seen.add(m.id);
            return true;
          });

          let contextMsg = `Error detected in command output\n\n\`${command.slice(0, 100)}\` produced an error:\n> ${errorLine}`;

          if (traceFiles.length > 0) {
            contextMsg += `\n\nFiles in stack trace:\n${traceFiles.map((f) => `  - ${f}`).join("\n")}`;
          }

          if (unique.length > 0) {
            const lines = unique.map((m) => `- ${m.memory}`).join("\n");
            contextMsg += `\n\nPrior error memories:\n${lines}`;
          }

          contextMsg +=
            "\n\nResolved errors are stored as anti_pattern or bug_fix memories for future reference.";

          await client.app.log({
            body: {
              service: "mem0",
              level: "info",
              message: contextMsg,
            },
          });
        } catch {}
      }
    },

    "experimental.session.compacting": async (
      input: { sessionID: string },
      output: { context: string[]; prompt?: string },
    ) => {
      try {
        const compactingSessionId = input?.sessionID ?? sessionId;
        const summaryContent = `Session compacting. Project: ${appId}. Branch: ${branch}. Session: ${compactingSessionId}. Stats: ${stats.adds} memories stored, ${stats.searches} searches, ${stats.messages} messages.`;
        Promise.resolve().then(async () => {
          try {
            await mem0.add(
              [{ role: "user", content: summaryContent }],
              {
                user_id: userId,
                app_id: appId,
                metadata: {
                  type: "session_state",
                  source: "pre-compaction",
                  session_id: compactingSessionId,
                  branch,
                },
                infer: true,
              } as any,
            );
          } catch {}
        });

        const res = await mem0.search("session state decisions learnings", {
          filters: { AND: [{ user_id: userId }, { app_id: appId }] },
          topK: 10,
        });
        const memories = extractMemories(res);
        if (memories.length > 0 && output?.context) {
          const lines = memories.map((m) => `- ${m.memory}`).join("\n");
          output.context.push(
            `## Mem0 Memories (preserve across compaction)\n\n${lines}\n\nIMPORTANT: After compaction, store any key decisions or learnings using the add_memory MCP tool.`,
          );
        }
      } catch {}
    },

    "shell.env": async (
      _input: { cwd: string; sessionID?: string; callID?: string },
      output: { env: Record<string, string> },
    ) => {
      if (output?.env) {
        output.env.MEM0_USER_ID = userId;
        output.env.MEM0_APP_ID = appId;
        output.env.MEM0_SESSION_ID = sessionId;
        output.env.MEM0_BRANCH = branch;
      }
    },
  };
};

export default Mem0Plugin;
