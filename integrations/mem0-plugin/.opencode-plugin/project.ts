import {basename} from "path";

/**
 * Project identity resolution for the Mem0 OpenCode plugin.
 *
 * The project id (`app_id`) scopes memories to a repo. We derive it from the
 * git remote so it is stable across clones, worktrees, and sub-directories,
 * falling back to the git repo root dir name, then the cwd. Keeping the parser
 * pure makes the tricky remote formats testable.
 */

export type ProjectContext = {
  worktree?: string;
  directory?: string;
};

export function selectActiveProjectPath(input: ProjectContext = {}): string {
  const worktree = input.worktree?.trim();
  if (worktree) return worktree;

  const directory = input.directory?.trim();
  if (directory) return directory;

  return process.cwd();
}

type ShellCommand = {
  cwd?: (path: string) => ShellCommand;
  quiet: () => Promise<{ stdout: { toString(): string } }>;
};

function commandInProject(command: ShellCommand, projectPath: string): ShellCommand {
  if (typeof command.cwd === "function") return command.cwd(projectPath);
  return command;
}

export async function getProjectId($: any, projectPath: string): Promise<string> {
  if (process.env.MEM0_APP_ID) return process.env.MEM0_APP_ID;
  try {
    const r = await commandInProject($`git remote get-url origin`, projectPath).quiet();
    const project = parseProjectFromRemote(r.stdout.toString());
    if (project) return project;
  } catch {
  }
  try {
    const r = await commandInProject($`git rev-parse --show-toplevel`, projectPath).quiet();
    const top = r.stdout.toString().trim();
    if (top) return basename(top);
  } catch {
  }
  const selectedBasename = basename(projectPath);
  if (selectedBasename) return selectedBasename;
  return basename(process.cwd());
}

export async function getBranch($: any, projectPath: string): Promise<string> {
  try {
    const r = await commandInProject($`git branch --show-current`, projectPath).quiet();
    return r.stdout.toString().trim() || "main";
  } catch {
  }
  return "main";
}

/**
 * Parse `owner/repo` out of a git remote URL and return it as `owner-repo`.
 * Handles https, scp-style ssh, custom ssh host aliases (e.g.
 * `git@github.com-work:owner/repo.git`), an optional `.git` suffix, and a
 * trailing slash. Returns null when no owner/repo can be found.
 */
export function parseProjectFromRemote(remote: string): string | null {
  const m = remote.trim().match(/[:/]([^/:]+)\/([^/:]+?)(?:\.git)?\/?$/);
  if (!m) return null;
  return `${m[1]}-${m[2]}`;
}
