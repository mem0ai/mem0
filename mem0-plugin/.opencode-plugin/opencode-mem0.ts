import type { Plugin } from "@opencode-ai/plugin";
import { resolve, dirname } from "path";

const PLUGIN_DIR = dirname(new URL(import.meta.url).pathname);
const SCRIPTS_DIR = resolve(PLUGIN_DIR, "scripts");

function scriptPath(name: string): string {
  return resolve(SCRIPTS_DIR, name);
}

const MEM0_MCP_PATTERN = /^mcp__(?:mem0|plugin_mem0_mem0)__/;
const WRITE_TOOLS = new Set(["Write", "Edit", "MultiEdit"]);
const MEM0_PRETOOL_NAMES = new Set([
  "mcp__mem0__add_memory",
  "mcp__plugin_mem0_mem0__add_memory",
  "mcp__mem0__search_memories",
  "mcp__plugin_mem0_mem0__search_memories",
  "mcp__mem0__get_memories",
  "mcp__plugin_mem0_mem0__get_memories",
  "mcp__mem0__delete_all_memories",
  "mcp__plugin_mem0_mem0__delete_all_memories",
]);

async function runScript(
  $: any,
  script: string,
  stdinJson: Record<string, unknown>,
  timeoutMs: number = 30_000,
): Promise<string> {
  const payload = JSON.stringify(stdinJson);
  try {
    const result =
      await $`echo ${payload} | OPENCODE_PLUGIN_ROOT=${PLUGIN_DIR} CLAUDE_PLUGIN_ROOT=${PLUGIN_DIR} bash ${scriptPath(script)}`.timeout(
        timeoutMs,
      );
    return result.stdout?.toString().trim() ?? "";
  } catch {
    return "";
  }
}

export const Mem0Plugin: Plugin = async (ctx) => {
  const { $, client } = ctx;

  client.on("session.created", async (event: any) => {
    const stdinPayload = {
      source: "startup",
      session_id: event?.properties?.sessionID ?? `ses_${Date.now()}`,
    };
    await runScript($, "ensure_deps.sh", {}, 60_000);
    const output = await runScript($, "on_session_start.sh", stdinPayload);
    if (output) {
      client.app.log("info", `[mem0] session start: ${output.slice(0, 200)}`);
    }
  });

  client.on("tui.prompt.append", async (event: any) => {
    const prompt = event?.properties?.content ?? "";
    if (prompt.length < 20) return;
    await runScript(
      $,
      "on_user_prompt.sh",
      { prompt, session_id: event?.properties?.sessionID ?? "" },
      8_000,
    );
  });

  client.on("tool.execute.before", async (event: any) => {
    const toolName: string = event?.properties?.tool ?? "";
    const toolInput: Record<string, unknown> = event?.properties?.input ?? {};

    if (WRITE_TOOLS.has(toolName)) {
      await runScript(
        $,
        "block_memory_write.sh",
        { tool_name: toolName, tool_input: toolInput },
        5_000,
      );
    } else if (MEM0_PRETOOL_NAMES.has(toolName)) {
      await runScript(
        $,
        "enforce_metadata_defaults.sh",
        { tool_name: toolName, tool_input: toolInput },
        3_000,
      );
    }
  });

  client.on("tool.execute.after", async (event: any) => {
    const toolName: string = event?.properties?.tool ?? "";
    const toolInput: Record<string, unknown> = event?.properties?.input ?? {};
    const toolOutput: string = event?.properties?.output ?? "";

    if (MEM0_MCP_PATTERN.test(toolName)) {
      await runScript(
        $,
        "on_post_tool_use.sh",
        { tool_name: toolName, tool_input: toolInput, tool_response: toolOutput },
        3_000,
      );
    } else if (toolName === "Bash") {
      await runScript(
        $,
        "on_bash_output.sh",
        { tool_name: toolName, tool_input: toolInput, tool_response: toolOutput },
        5_000,
      );
    }
  });

  client.on("session.compacted", async (event: any) => {
    await runScript($, "on_pre_compact.sh", {
      source: "compact",
      session_id: event?.properties?.sessionID ?? "",
    });
  });

  return {};
};

export default Mem0Plugin;
