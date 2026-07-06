import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { Mem0Config, DreamConfig } from "../types.ts";

const AGENT_ROOT = path.join(os.homedir(), ".pi", "agent");
export const CONFIG_DIR = AGENT_ROOT;
const CONFIG_PATH = path.join(AGENT_ROOT, "mem0-config.json");

const DEFAULT_DREAM: DreamConfig = {
  enabled: true,
  auto: true,
  minHours: 24,
  minSessions: 5,
  minMemories: 20,
};

const DEFAULT_CONFIG: Mem0Config = {
  apiKey: "",
  userId: "",
  autoCapture: true,
  defaultScope: "project",
  contextInjection: true,
  searchThreshold: 0.3,
  dream: DEFAULT_DREAM,
};

export function loadConfig(): Mem0Config {
  let fileConfig: Partial<Mem0Config> = {};

  if (fs.existsSync(CONFIG_PATH)) {
    try {
      const raw = fs.readFileSync(CONFIG_PATH, "utf-8");
      fileConfig = JSON.parse(raw);
    } catch {
      // Corrupted config — use defaults
    }
  }

  const dream: DreamConfig = {
    ...DEFAULT_DREAM,
    ...(fileConfig.dream ?? {}),
  };

  const config: Mem0Config = {
    ...DEFAULT_CONFIG,
    ...fileConfig,
    dream,
  };

  if (process.env.MEM0_API_KEY) {
    config.apiKey = process.env.MEM0_API_KEY;
  }
  if (process.env.MEM0_USER_ID) {
    config.userId = process.env.MEM0_USER_ID;
  }

  return config;
}
