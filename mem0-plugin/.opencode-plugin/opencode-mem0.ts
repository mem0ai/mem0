import type { Plugin } from "@opencode-ai/plugin";
import { MemoryClient } from "mem0ai";
import { userInfo } from "os";
import { basename, resolve, dirname } from "path";
import { randomBytes } from "crypto";
import { fileURLToPath } from "url";

async function getUserId(): Promise<string> {
  if (process.env.MEM0_USER_ID) return process.env.MEM0_USER_ID;
  try {
    return userInfo().username;
  } catch {}
  return process.env.USER || process.env.USERNAME || "unknown";
}

async function getProjectId($: any): Promise<string> {
  if (process.env.MEM0_APP_ID) return process.env.MEM0_APP_ID;
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

const SECRET_PATTERNS = [
  /sk-[A-Za-z0-9]{20,}/g,
  /m0-[A-Za-z0-9]{20,}/g,
  /AKIA[0-9A-Z]{16}/g,
  /xox[baprs]-[A-Za-z0-9-]{20,}/g,
  /ghp_[A-Za-z0-9]{36,}/g,
  /gho_[A-Za-z0-9]{36,}/g,
];

function redact(text: string): string {
  let out = text;
  for (const re of SECRET_PATTERNS) {
    out = out.replace(re, "[REDACTED]");
  }
  return out;
}

const NUDGE_RE =
  /\b(remember\s+(this|that)|memorize|save\s+this|note\s+(this|that)|don'?t\s+forget|always\s+remember|never\s+forget|keep\s+(this|that)\s+in\s+(mind|memory)|store\s+(this|that))\b/i;

const RESUME_RE =
  /where\s+(did\s+)?(we|I)\s+(leave|left)\s+off|continue\s+(from\s+)?(where|last)|what\s+were\s+we\s+(working|doing)|pick\s+up\s+where|resume\s+(from\s+|where\s+)|what.s\s+the\s+(current|latest)\s+(state|status)|catch\s+me\s+up|where\s+are\s+we/i;

const ERROR_STRONG_RE =
  /Traceback \(most recent call last\)|panic: |FATAL:|error\[E\d+\]/;
const ERROR_MULTI_RE = /(Error:|Exception:)/g;

const MEM0_MCP_RE = /mem0.*(?:add_memory|search_memories|get_memor|delete_memor|update_memory|delete_entities|list_entities)/i;
const WRITE_TOOLS = new Set(["Write", "Edit", "MultiEdit", "write", "edit", "multiEdit"]);

function isMem0Tool(name: string): boolean {
  return MEM0_MCP_RE.test(name);
}

function isMem0AddMemory(name: string): boolean {
  return /mem0.*add_memory/i.test(name);
}

function isMem0SearchOrGet(name: string): boolean {
  return /mem0.*(search_memories|get_memories)/i.test(name);
}

function isMem0DeleteAll(name: string): boolean {
  return /mem0.*delete_all_memories/i.test(name);
}

function extractUserText(input: any, output: any): string {
  const parts: any[] = output?.parts;
  if (Array.isArray(parts)) {
    return parts
      .filter((p: any) => p.type === "text" && !p.synthetic)
      .map((p: any) => p.text ?? "")
      .join("\n");
  }
  const msg = output?.message ?? input?.message;
  if (typeof msg?.content === "string") return msg.content;
  if (typeof msg?.text === "string") return msg.text;
  return "";
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const skillsDir = resolve(__dirname, "..", "opencode-skills");

export const Mem0Plugin: Plugin = async (ctx) => {
  const { $, client } = ctx;
  const apiKey = process.env.MEM0_API_KEY;

  if (!apiKey) {
    try {
      await client.app.log({
        body: {
          service: "mem0",
          level: "warn",
          message:
            "MEM0_API_KEY not set. Get one at https://app.mem0.ai/dashboard/api-keys",
        },
      });
    } catch {}
    return {};
  }

  const mem0 = new MemoryClient({ apiKey });
  const userId = await getUserId();
  const appId = await getProjectId($);
  const branch = await getBranch($);
  const stats = { adds: 0, searches: 0, messages: 0 };
  const sessionId = generateSessionId();

  let initialized = false;
  let memoryCount = 0;
  let msgCount = 0;

  const systemContext: string[] = [];

  return {
    config: async (config: any) => {
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      if (!config.skills.paths.includes(skillsDir)) {
        config.skills.paths.push(skillsDir);
      }
    },

    "chat.message": async (input: any, output: any) => {
      const userText = extractUserText(input, output);
      if (!userText || userText.length < 10) return;

      const safeText = redact(userText);
      msgCount++;
      stats.messages++;

      if (!initialized) {
        initialized = true;

        try {
          const all = await mem0.getAll({
            filters: {
              AND: [{ user_id: userId }, { app_id: appId }],
            },
            page: 1,
            pageSize: 1,
          });
          memoryCount =
            (all as any)?.count ??
            (all as any)?.results?.length ??
            0;

          systemContext.push(
            `Mem0 Active | user=${userId} | project=${appId} | branch=${branch} | memories=${memoryCount}`,
          );
          systemContext.push(
            `Always include user_id="${userId}" and app_id="${appId}" in every search_memories filter and add_memory call.`,
          );

          if (memoryCount === 0) {
            systemContext.push(
              "New project with 0 memories. Suggest running /mem0:onboard to import project files and install coding categories.",
            );
          }

          if (memoryCount > 0) {
            systemContext.push(
              "Search mem0 for recent decisions and task learnings before responding. Run 2 parallel searches: one for decision type, one for task_learning type.",
            );
            try {
              const res = await mem0.search(
                "recent session state decisions and learnings",
                {
                  filters: {
                    AND: [{ user_id: userId }, { app_id: appId }],
                  },
                  topK: 5,
                },
              );
              stats.searches++;
              const memories = extractMemories(res);
              if (memories.length > 0) {
                const memLines = memories
                  .map((m) => `- ${m.memory}`)
                  .join("\n");
                systemContext.push(`Prior context from mem0:\n${memLines}`);
              }
            } catch {}
          }

          systemContext.push(
            "Mem0 searches apply when user references past work, decision questions, errors, or non-trivial tasks. Queries use noun-phrases, 2-4 parallel calls with different metadata.type filters, and include user_id + app_id.",
          );
        } catch (err: any) {
          try {
            await client.app.log({
              body: {
                service: "mem0",
                level: "error",
                message: `Session init error: ${err?.message}`,
              },
            });
          } catch {}
        }
      }

      if (NUDGE_RE.test(safeText)) {
        systemContext.push(
          "[MEMORY TRIGGER] User asked to remember something. Call add_memory with the user's statement, confidence=1.0, infer=false.",
        );
      }

      const hasResume = RESUME_RE.test(safeText);
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
            const memLines = unique.map((m) => `- ${m.memory}`).join("\n");
            systemContext.push(
              `Session resume context:\n${memLines}\n\nThese memories provide context for resuming work.`,
            );
          }
        } catch {}
      }

      if (!hasResume && memoryCount > 0) {
        try {
          const res = await mem0.search(safeText, {
            filters: { AND: [{ user_id: userId }, { app_id: appId }] },
            topK: 5,
          });
          stats.searches++;
          const memories = extractMemories(res);
          if (memories.length > 0) {
            const memLines = memories.map((m) => `- ${m.memory}`).join("\n");
            systemContext.push(`Relevant memories:\n${memLines}`);
          }
        } catch {}
      }

      if (msgCount % 3 === 0) {
        Promise.resolve().then(async () => {
          try {
            await mem0.add([{ role: "user", content: safeText }], {
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
            } as any);
            stats.adds++;
          } catch {}
        });
      }

      if (msgCount % 5 === 0 && stats.adds < Math.floor(msgCount / 3)) {
        systemContext.push(
          "After responding, store any new decisions, learnings, or preferences from this exchange via add_memory. Keep it to 1 sentence per memory.",
        );
      }
    },

    "experimental.chat.messages.transform": async (
      _input: any,
      output: { messages: { info: any; parts: any[] }[] },
    ) => {
      if (systemContext.length === 0 || !output?.messages?.length) return;

      const firstUser = output.messages.find(
        (m) => m.info.role === "user",
      );
      if (!firstUser || !firstUser.parts.length) return;

      const marker = "## Mem0 Memory Context";
      if (firstUser.parts.some((p: any) => p.type === "text" && p.text?.includes(marker))) return;

      const block = `${marker}\n\n${systemContext.join("\n\n")}`;
      const ref = firstUser.parts[0];
      firstUser.parts.unshift({ ...ref, type: "text", text: block });
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

      if (isMem0Tool(toolName) && output?.args) {
        if (!output.args.user_id) output.args.user_id = userId;
        if (!output.args.app_id) output.args.app_id = appId;

        if (isMem0AddMemory(toolName)) {
          if (!output.args.metadata) output.args.metadata = {};
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

        if (isMem0SearchOrGet(toolName)) {
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

        if (isMem0DeleteAll(toolName)) {
          if (!output.args.user_id) output.args.user_id = userId;
          if (!output.args.app_id) output.args.app_id = appId;
        }

        if (!isMem0AddMemory(toolName) && !output.args.metadata) {
          output.args.metadata = { source: "opencode", branch };
        }
      }
    },

    "tool.execute.after": async (input: any, _output: any) => {
      const toolName: string = input?.tool ?? "";
      const toolOutput: string = input?.output ?? _output?.output ?? "";

      if (MEM0_MCP_RE.test(toolName)) {
        if (toolName.includes("add_memory")) stats.adds++;
        if (toolName.includes("search")) stats.searches++;
      }

      if (toolName === "bash" && toolOutput.length >= 50) {
        const command: string = input?.args?.command ?? "";
        if (/git\s+(commit|merge|rebase)/.test(command)) return;

        const hasStrongError = ERROR_STRONG_RE.test(toolOutput);
        const multiErrors = (toolOutput.match(ERROR_MULTI_RE) ?? []).length;
        if (!hasStrongError && multiErrors < 2) return;

        try {
          const errorLine =
            toolOutput
              .split("\n")
              .find((l: string) =>
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
          stats.searches += 2;

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

          let ctx = `Error detected: \`${command.slice(0, 100)}\` produced:\n> ${errorLine}`;
          if (traceFiles.length > 0) {
            ctx += `\nFiles in stack trace: ${traceFiles.join(", ")}`;
          }
          if (unique.length > 0) {
            const lines = unique.map((m) => `- ${m.memory}`).join("\n");
            ctx += `\nPrior error memories:\n${lines}`;
          }
          ctx +=
            "\nStore resolved errors as anti_pattern or bug_fix memories for future reference.";
          systemContext.push(ctx);
        } catch {}
      }
    },

    "experimental.session.compacting": async (
      input: { sessionID?: string },
      output: { context: string[]; prompt?: string },
    ) => {
      try {
        const compactSessionId = input?.sessionID ?? sessionId;
        const summaryContent = `Session compacting. Project: ${appId}. Branch: ${branch}. Session: ${compactSessionId}. Stats: ${stats.adds} memories stored, ${stats.searches} searches, ${stats.messages} messages.`;
        Promise.resolve().then(async () => {
          try {
            await mem0.add([{ role: "user", content: summaryContent }], {
              user_id: userId,
              app_id: appId,
              metadata: {
                type: "session_state",
                source: "pre-compaction",
                session_id: compactSessionId,
                branch,
              },
              infer: true,
            } as any);
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
      _input: { cwd: string; sessionID?: string },
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
