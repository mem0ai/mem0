import { readFileSync } from "node:fs";
import { join } from "node:path";

export function mem0CliApiKey(homeDir: string): string {
  try {
    const key = JSON.parse(readFileSync(join(homeDir, ".mem0", "config.json"), "utf8"))?.platform?.api_key;
    return typeof key === "string" ? key.trim() : "";
  } catch {
    return "";
  }
}
