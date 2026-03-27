/**
 * mem0 init — interactive setup wizard.
 */

import readline from "node:readline";
import {
  printBanner,
  printError,
  printInfo,
  printSuccess,
  colors,
} from "../branding.js";
import { type Mem0Config, createDefaultConfig, saveConfig } from "../config.js";
import { PlatformBackend } from "../backend/platform.js";

const { brand, dim } = colors;

function promptSecret(label: string): Promise<string> {
  return new Promise((resolve, reject) => {
    process.stdout.write(label);

    if (process.stdin.isTTY) {
      process.stdin.setRawMode(true);
    }
    process.stdin.resume();
    process.stdin.setEncoding("utf-8");

    const chars: string[] = [];

    const onData = (key: string) => {
      for (const ch of key) {
        if (ch === "\r" || ch === "\n") {
          cleanup();
          process.stdout.write("\n");
          resolve(chars.join(""));
          return;
        }
        if (ch === "\x03") {
          cleanup();
          reject(new Error("Interrupted"));
          return;
        }
        if (ch === "\x7f" || ch === "\x08") {
          // backspace
          if (chars.length > 0) {
            chars.pop();
            process.stdout.write("\b \b");
          }
        } else if (ch === "\x15") {
          // Ctrl+U — clear line
          process.stdout.write("\b \b".repeat(chars.length));
          chars.length = 0;
        } else if (ch >= " ") {
          chars.push(ch);
          process.stdout.write("*");
        }
      }
    };

    const cleanup = () => {
      process.stdin.removeListener("data", onData);
      if (process.stdin.isTTY) {
        process.stdin.setRawMode(false);
      }
      process.stdin.pause();
    };

    process.stdin.on("data", onData);
  });
}

function promptLine(label: string, defaultValue?: string): Promise<string> {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const prompt = defaultValue ? `${label} [${defaultValue}]: ` : `${label}: `;
  return new Promise((resolve) => {
    rl.question(prompt, (answer) => {
      rl.close();
      resolve(answer.trim() || defaultValue || "");
    });
  });
}

async function setupPlatform(config: Mem0Config): Promise<void> {
  console.log();
  console.log(`  ${dim("Get your API key at https://app.mem0.ai/dashboard/api-keys")}`);
  console.log();

  process.stdout.write(`  ${brand("API Key")}: `);
  const apiKey = await promptSecret("");
  if (!apiKey) {
    printError("API key is required.");
    process.exit(1);
  }
  config.platform.apiKey = apiKey;
}

async function setupDefaults(config: Mem0Config): Promise<void> {
  console.log();
  printInfo("Set default entity IDs (press Enter to skip).\n");

  const userId = await promptLine(`  ${brand("Default User ID")} ${dim("(recommended)")}`, "mem0-cli");
  if (userId) config.defaults.userId = userId;
}

async function validatePlatform(config: Mem0Config): Promise<void> {
  console.log();
  printInfo("Validating connection...");
  try {
    const backend = new PlatformBackend(config.platform);
    const status = await backend.status({
      userId: config.defaults.userId || undefined,
      agentId: config.defaults.agentId || undefined,
    });
    if (status.connected) {
      printSuccess("Connected to mem0 Platform!");
    } else {
      printError(
        `Could not connect: ${status.error ?? "Unknown error"}`,
        "Check your API key and try again.",
      );
    }
  } catch (e) {
    printError(`Connection test failed: ${e instanceof Error ? e.message : e}`);
  }
}

export async function runInit(opts: { apiKey?: string; userId?: string } = {}): Promise<void> {
  const config = createDefaultConfig();

  // Non-interactive: both flags provided
  if (opts.apiKey && opts.userId) {
    config.platform.apiKey = opts.apiKey;
    config.defaults.userId = opts.userId;
    await validatePlatform(config);
    saveConfig(config);
    printSuccess("Configuration saved to ~/.mem0/config.json");
    return;
  }

  // Non-TTY without full flags: error with usage hint
  if (!process.stdin.isTTY && (!opts.apiKey || !opts.userId)) {
    printError(
      "Non-interactive terminal detected and missing required flags.",
      "Usage: mem0 init --api-key <key> --user-id <id>",
    );
    process.exit(1);
  }

  printBanner();
  console.log();
  printInfo("Welcome! Let's set up your mem0 CLI.\n");

  // Use provided API key or prompt
  if (opts.apiKey) {
    config.platform.apiKey = opts.apiKey;
  } else {
    await setupPlatform(config);
  }

  // Use provided user ID or prompt
  if (opts.userId) {
    config.defaults.userId = opts.userId;
  } else {
    await setupDefaults(config);
  }

  await validatePlatform(config);

  saveConfig(config);
  console.log();
  printSuccess("Configuration saved to ~/.mem0/config.json");
  console.log();
  console.log(`  ${dim("Get started:")}`);
  if (config.defaults.userId) {
    console.log(`  ${dim('  mem0 add "I prefer dark mode"')}`);
    console.log(`  ${dim('  mem0 search "preferences"')}`);
  } else {
    console.log(`  ${dim('  mem0 add "I prefer dark mode" --user-id alice')}`);
    console.log(`  ${dim('  mem0 search "preferences" --user-id alice')}`);
  }
  console.log();
}
