import {readFileSync} from "fs";
import {homedir} from "os";
import {join} from "path";

const PROFILE_FILES = [".zshrc", ".bashrc", ".zprofile", ".bash_profile", ".profile"];

export function parseApiKeyLine(line: string): string | undefined {
  const match = line.match(/^\s*(?:export\s+)?MEM0_API_KEY=(.*)$/);
  if (!match) return undefined;

  const value = match[1].replace(/#.*$/, "").trim().replace(/^("|')(.*)\1$/, "$2").trim();
  return value && !value.startsWith("$") ? value : undefined;
}

export function resolveApiKey(env: NodeJS.ProcessEnv = process.env, homeDir = homedir()): string {
  const explicit = env.MEM0_API_KEY?.trim();
  if (explicit) return explicit;

  for (const profile of PROFILE_FILES) {
    try {
      for (const line of readFileSync(join(homeDir, profile), "utf8").split(/\r?\n/)) {
        const key = parseApiKeyLine(line);
        if (key) return key;
      }
    } catch {
    }
  }

  return "";
}
