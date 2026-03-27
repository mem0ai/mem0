/**
 * Config management commands: show, set, get.
 */

import Table from "cli-table3";
import { printError, printSuccess, colors } from "../branding.js";
import {
  getNestedValue,
  loadConfig,
  redactKey,
  saveConfig,
  setNestedValue,
} from "../config.js";
import { formatJsonEnvelope } from "../output.js";

const { brand, accent, dim } = colors;

export function cmdConfigShow(opts: { output?: string } = {}): void {
  const config = loadConfig();

  if (opts.output === "json") {
    formatJsonEnvelope({
      command: "config show",
      data: {
        defaults: {
          user_id: config.defaults.userId || null,
          agent_id: config.defaults.agentId || null,
          app_id: config.defaults.appId || null,
          run_id: config.defaults.runId || null,
          enable_graph: config.defaults.enableGraph,
        },
        platform: {
          api_key: redactKey(config.platform.apiKey),
          base_url: config.platform.baseUrl,
        },
      },
    });
    return;
  }

  console.log();
  console.log(`  ${brand("◆ mem0 Configuration")}\n`);

  const table = new Table({
    head: [accent("Key"), accent("Value")],
    style: { head: [], border: [] },
  });

  // Defaults
  table.push(["defaults.user_id", config.defaults.userId || dim("(not set)")]);
  table.push(["defaults.agent_id", config.defaults.agentId || dim("(not set)")]);
  table.push(["defaults.app_id", config.defaults.appId || dim("(not set)")]);
  table.push(["defaults.run_id", config.defaults.runId || dim("(not set)")]);
  table.push(["defaults.enable_graph", String(config.defaults.enableGraph)]);
  table.push(["", ""]);

  // Platform
  table.push(["platform.api_key", redactKey(config.platform.apiKey)]);
  table.push(["platform.base_url", config.platform.baseUrl]);

  console.log(table.toString());
  console.log();
}

export function cmdConfigGet(key: string): void {
  const config = loadConfig();
  const value = getNestedValue(config, key);

  if (value === undefined) {
    printError(`Unknown config key: ${key}`);
  } else {
    // Redact secrets
    if (key.includes("api_key") || key.split(".").pop() === "key") {
      console.log(redactKey(String(value)));
    } else {
      console.log(String(value));
    }
  }
}

export function cmdConfigSet(key: string, value: string): void {
  const config = loadConfig();
  if (setNestedValue(config, key, value)) {
    saveConfig(config);
    const display = key.includes("key") ? redactKey(value) : value;
    printSuccess(`${key} = ${display}`);
  } else {
    printError(`Unknown config key: ${key}`);
  }
}
