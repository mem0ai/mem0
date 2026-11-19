import {basename} from "path";
import {parseProjectFromRemote} from "../agent-plugin-core/typescript/src/identity.ts";

export {parseProjectFromRemote};

type ShellCommand = {
  cwd(directory: string): ShellCommand;
  quiet(): Promise<{stdout: {toString(): string}}>;
};

type Shell = (strings: TemplateStringsArray, ...expressions: any[]) => ShellCommand;

export async function resolveProjectId(
  $: Shell,
  directory: string,
  env: NodeJS.ProcessEnv = process.env,
): Promise<string> {
  if (env.MEM0_APP_ID) return env.MEM0_APP_ID;

  try {
    const result = await $`git remote get-url origin`.cwd(directory).quiet();
    const project = parseProjectFromRemote(result.stdout.toString());
    if (project) return project;
  } catch {
  }

  try {
    const result = await $`git rev-parse --show-toplevel`.cwd(directory).quiet();
    const root = result.stdout.toString().trim();
    if (root) return basename(root);
  } catch {
  }

  return basename(directory);
}

export async function resolveBranch($: Shell, directory: string): Promise<string> {
  try {
    const result = await $`git branch --show-current`.cwd(directory).quiet();
    return result.stdout.toString().trim() || "main";
  } catch {
  }
  return "main";
}
