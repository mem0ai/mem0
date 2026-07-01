/**
 * Project identity resolution for the Mem0 OpenCode plugin.
 *
 * The project id (`app_id`) scopes memories to a repo. We derive it from the
 * git remote so it is stable across clones, worktrees, and sub-directories —
 * falling back (in opencode-mem0.ts) to the git repo root dir name, then the
 * cwd. Keeping the parser pure makes the tricky remote formats testable.
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
