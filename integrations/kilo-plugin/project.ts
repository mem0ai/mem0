/**
 * Project identity resolution for the Mem0 Kilo plugin.
 *
 * The project id (`app_id`) scopes memories to a repo. We derive it from the
 * git remote so it is stable across clones, worktrees, and sub-directories —
 * falling back (in kilo-mem0.ts) to the git repo root dir name, then the
 * cwd. Keeping the parser pure makes the tricky remote formats testable.
 */

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
