import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { realpathSync } from "node:fs";
import { basename, relative, sep } from "node:path";

export interface EntityParams {
  userId?: string;
  agentId?: string;
  runId?: string;
}

const clean = (value: string | undefined): string | undefined => value?.trim() || undefined;

export function entitySearchFilters(
  params: EntityParams,
  defaultUserId: string,
): Record<string, string> {
  const filters: Record<string, string> = { user_id: clean(params.userId) ?? defaultUserId };
  const agentId = clean(params.agentId);
  const runId = clean(params.runId);
  if (agentId) filters.agent_id = agentId;
  if (runId) filters.run_id = runId;
  return filters;
}

export function entityAddParams(params: EntityParams, defaultUserId: string): Record<string, string> {
  const values: Record<string, string> = { userId: clean(params.userId) ?? defaultUserId };
  const agentId = clean(params.agentId);
  const runId = clean(params.runId);
  if (agentId) values.agentId = agentId;
  if (runId) values.runId = runId;
  return values;
}

export function parseProjectFromRemote(remote: string): string | null {
  const match = remote.trim().match(/[:/]([^/:]+)\/([^/:]+?)(?:\.git)?\/?$/);
  return match ? `${match[1]}-${match[2]}` : null;
}

export interface RepoIdentity {
  appId: string;
  projectId: string;
  projectIds: string[];
}

export function normalizeRemote(remote: string): string {
  let value = remote.trim();
  if (value.startsWith("git@") && value.includes(":")) value = `https://${value.slice(4).replace(":", "/")}`;
  if (value.endsWith(".git")) value = value.slice(0, -4);
  const url = value.match(/^([a-z][a-z0-9+.-]*):\/\/(?:[^@/]*@)?([^/?#]*)(.*)$/i);
  if (url) value = `${url[1].toLowerCase()}://${url[2].toLowerCase()}${url[3]}`;
  return value.replace(/\/+$/, "");
}

const shortHash = (value: string) => createHash("sha256").update(value).digest("hex").slice(0, 10);

/** The Claude Code repository namespace: a hashed project lane plus the pre-upgrade app lane for remotes. */
export function resolveRepoIdentity(appId: string, remote: string, root: string): RepoIdentity {
  const identity = normalizeRemote(remote);
  if (!identity) {
    const projectId = `local-${appId}-${shortHash(root)}`;
    return { appId, projectId, projectIds: [projectId] };
  }
  const projectId = `${appId}-${shortHash(identity)}`;
  return { appId, projectId, projectIds: [projectId, appId] };
}

export interface RepoContext extends RepoIdentity {
  branch: string;
  sha: string;
  dirs: string[];
}

function git(cwd: string, ...args: string[]): string {
  try {
    return execFileSync("git", args, { cwd, encoding: "utf-8", timeout: 3000, stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return "";
  }
}

/** Resolve the working directory's repository the way the Claude Code plugin does. */
export function resolveRepoContext(cwd: string, appIdOverride = ""): RepoContext {
  const directory = realpathSync(cwd);
  const root = realpathSync(git(directory, "rev-parse", "--show-toplevel") || directory);
  const remote = git(root, "config", "--get", "remote.origin.url");
  const appId = appIdOverride.trim() || parseProjectFromRemote(remote) || basename(root);
  const inside = relative(root, directory);
  const parts = !inside || inside.startsWith("..") ? [] : inside.split(sep);
  return {
    ...resolveRepoIdentity(appId, remote, root),
    branch: git(root, "branch", "--show-current"),
    sha: git(root, "rev-parse", "HEAD"),
    dirs: parts.map((_, index) => parts.slice(0, index + 1).join("/")),
  };
}
