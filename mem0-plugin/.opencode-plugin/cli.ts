#!/usr/bin/env bun
import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  copyFileSync,
  readdirSync,
  rmSync,
  statSync,
} from "fs";
import { join, dirname } from "path";
import { homedir } from "os";

const PLUGIN_NAME = "@mem0/opencode-plugin";
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

const SKILLS_NAMESPACE = "mem0";

function getConfigDir(): string {
  const dir = join(homedir(), ".config", "opencode");
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  return dir;
}

function getConfigPath(): string {
  const configDir = getConfigDir();
  const jsonc = join(configDir, "opencode.jsonc");
  if (existsSync(jsonc)) return jsonc;
  return join(configDir, "opencode.json");
}

function stripJsonComments(text: string): string {
  let result = "";
  let i = 0;
  let inString = false;
  let escape = false;
  while (i < text.length) {
    const ch = text[i];
    if (escape) {
      result += ch;
      escape = false;
      i++;
      continue;
    }
    if (inString) {
      if (ch === "\\") escape = true;
      else if (ch === '"') inString = false;
      result += ch;
      i++;
      continue;
    }
    if (ch === '"') {
      inString = true;
      result += ch;
      i++;
      continue;
    }
    if (ch === "/" && text[i + 1] === "/") {
      while (i < text.length && text[i] !== "\n") i++;
      continue;
    }
    if (ch === "/" && text[i + 1] === "*") {
      i += 2;
      while (i < text.length && !(text[i] === "*" && text[i + 1] === "/")) i++;
      i += 2;
      continue;
    }
    result += ch;
    i++;
  }
  return result;
}

function resolvePluginDir(): string {
  try {
    return dirname(new URL(import.meta.url).pathname);
  } catch {}
  return __dirname ?? process.cwd();
}

function findSkillsDir(): string {
  const base = resolvePluginDir();
  const candidates = [
    join(base, "opencode-skills"),
    join(dirname(base), "opencode-skills"),
    join(base, "..", "opencode-skills"),
  ];
  for (const c of candidates) {
    try {
      if (existsSync(c) && statSync(c).isDirectory()) return c;
    } catch {}
  }
  return "";
}

function installSkills(): number {
  const skillsSource = findSkillsDir();
  if (!skillsSource) {
    console.log("  ! Skills directory not found — skipping slash command install");
    return 0;
  }

  const skillsTarget = join(getConfigDir(), "skills");
  if (!existsSync(skillsTarget)) mkdirSync(skillsTarget, { recursive: true });

  let count = 0;
  const entries = readdirSync(skillsSource);

  for (const name of entries) {
    const skillDir = join(skillsSource, name);
    try {
      if (!statSync(skillDir).isDirectory()) continue;
    } catch {
      continue;
    }

    const skillFile = join(skillDir, "SKILL.md");
    if (!existsSync(skillFile)) continue;

    const targetDir = join(skillsTarget, `${SKILLS_NAMESPACE}-${name}`);
    if (!existsSync(targetDir)) mkdirSync(targetDir, { recursive: true });

    copyFileSync(skillFile, join(targetDir, "SKILL.md"));
    count++;
  }

  return count;
}

function uninstallSkills(): number {
  const skillsTarget = join(getConfigDir(), "skills");
  if (!existsSync(skillsTarget)) return 0;

  let count = 0;
  const entries = readdirSync(skillsTarget);

  for (const name of entries) {
    if (!name.startsWith(`${SKILLS_NAMESPACE}-`)) continue;
    const fullPath = join(skillsTarget, name);
    try {
      if (!statSync(fullPath).isDirectory()) continue;
      rmSync(fullPath, { recursive: true });
      count++;
    } catch {}
  }

  return count;
}

function install() {
  console.log("Installing Mem0 plugin for OpenCode...\n");

  const configPath = getConfigPath();
  let config: any = {};

  if (existsSync(configPath)) {
    try {
      const raw = readFileSync(configPath, "utf-8");
      config = JSON.parse(stripJsonComments(raw));
    } catch {
      console.log(`  ! Could not parse ${configPath}, creating fresh config`);
      config = {};
    }
  }

  if (!Array.isArray(config.plugin)) config.plugin = [];
  if (!config.plugin.includes(PLUGIN_NAME)) {
    config.plugin.push(PLUGIN_NAME);
    console.log(`  + Added "${PLUGIN_NAME}" to plugin array`);
  } else {
    console.log(`  ~ "${PLUGIN_NAME}" already in plugin array`);
  }

  if (!config.mcp) config.mcp = {};
  if (!config.mcp.mem0) {
    config.mcp.mem0 = MCP_CONFIG.mem0;
    console.log("  + Added mem0 MCP server config");
  } else {
    console.log("  ~ mem0 MCP server already configured");
  }

  writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n");
  console.log(`\n  Wrote ${configPath}`);

  const skillCount = installSkills();
  if (skillCount > 0) {
    console.log(`  + Installed ${skillCount} slash commands to ~/.config/opencode/skills/`);
  }

  console.log("");

  if (!process.env.MEM0_API_KEY) {
    console.log("  ! MEM0_API_KEY is not set in your environment.");
    console.log(
      '  Run: echo \'export MEM0_API_KEY="m0-your-key"\' >> ~/.zshrc && source ~/.zshrc',
    );
    console.log(
      "  Get a free key at: https://app.mem0.ai/dashboard/api-keys\n",
    );
  } else {
    console.log("  MEM0_API_KEY detected\n");
  }

  console.log("Done! Restart OpenCode to activate Mem0.");
  console.log("  Then run /mem0-onboard in the TUI to complete setup.\n");
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
  console.log(`  Removed plugin + MCP from ${configPath}`);

  const skillCount = uninstallSkills();
  if (skillCount > 0) {
    console.log(`  Removed ${skillCount} slash commands from ~/.config/opencode/skills/`);
  }

  console.log("Restart OpenCode to complete removal.");
}

const cmd = process.argv[2];
if (cmd === "uninstall" || cmd === "remove") {
  uninstall();
} else {
  install();
}
