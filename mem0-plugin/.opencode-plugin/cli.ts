#!/usr/bin/env bun
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { homedir } from "os";

const PLUGIN_NAME = "@mem0ai/opencode-plugin";
const MCP_CONFIG = {
  mem0: {
    type: "remote",
    url: "https://mcp.mem0.ai/mcp/",
    headers: {
      Authorization: "Token {env:MEM0_API_KEY}",
    },
    oauth: false,
  },
};

function getConfigPath(): string {
  const configDir = join(homedir(), ".config", "opencode");
  if (!existsSync(configDir)) mkdirSync(configDir, { recursive: true });
  const jsonc = join(configDir, "opencode.jsonc");
  if (existsSync(jsonc)) return jsonc;
  const json = join(configDir, "opencode.json");
  return json;
}

function stripJsonComments(text: string): string {
  return text.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
}

function install() {
  const noTui = process.argv.includes("--no-tui");
  const log = (msg: string) => console.log(msg);

  log("Installing Mem0 plugin for OpenCode...\n");

  const configPath = getConfigPath();
  let config: any = {};

  if (existsSync(configPath)) {
    try {
      const raw = readFileSync(configPath, "utf-8");
      config = JSON.parse(stripJsonComments(raw));
    } catch {
      log(`Warning: could not parse ${configPath}, creating fresh config`);
      config = {};
    }
  }

  if (!Array.isArray(config.plugin)) config.plugin = [];
  if (!config.plugin.includes(PLUGIN_NAME)) {
    config.plugin.push(PLUGIN_NAME);
    log(`  + Added "${PLUGIN_NAME}" to plugin array`);
  } else {
    log(`  ~ "${PLUGIN_NAME}" already in plugin array`);
  }

  if (!config.mcp) config.mcp = {};
  if (!config.mcp.mem0) {
    config.mcp.mem0 = MCP_CONFIG.mem0;
    log("  + Added mem0 MCP server config");
  } else {
    log("  ~ mem0 MCP server already configured");
  }

  writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n");
  log(`\n  Wrote ${configPath}\n`);

  if (!process.env.MEM0_API_KEY) {
    log("Warning: MEM0_API_KEY is not set in your environment.");
    log('  Run: echo \'export MEM0_API_KEY="m0-your-key"\' >> ~/.zshrc && source ~/.zshrc');
    log("  Get a free key at: https://app.mem0.ai/dashboard/api-keys\n");
  } else {
    log("  MEM0_API_KEY detected\n");
  }

  log("Done! Restart OpenCode to activate Mem0.");
}

function uninstall() {
  const configPath = getConfigPath();
  if (!existsSync(configPath)) {
    console.log("No OpenCode config found. Nothing to remove.");
    return;
  }

  const raw = readFileSync(configPath, "utf-8");
  const config = JSON.parse(stripJsonComments(raw));

  if (Array.isArray(config.plugin)) {
    config.plugin = config.plugin.filter((p: string) => p !== PLUGIN_NAME);
    if (config.plugin.length === 0) delete config.plugin;
  }

  if (config.mcp?.mem0) {
    delete config.mcp.mem0;
    if (Object.keys(config.mcp).length === 0) delete config.mcp;
  }

  writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n");
  console.log(`Removed Mem0 from ${configPath}. Restart OpenCode.`);
}

const cmd = process.argv[2];
if (cmd === "uninstall" || cmd === "remove") {
  uninstall();
} else {
  install();
}
