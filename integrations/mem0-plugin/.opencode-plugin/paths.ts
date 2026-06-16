/**
 * Resolve where to install bundled skills so OpenCode discovers them.
 *
 * OpenCode's global config dir differs between installs: the XDG dir
 * (`~/.config/opencode`) on current builds, and the legacy `~/.opencode` on
 * older ones. We install into the XDG dir always (canonical), plus the legacy
 * `~/.opencode` when it already exists — so skills are discovered regardless of
 * which dir a given OpenCode build reads, without creating `~/.opencode` on
 * systems that don't use it.
 */

import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

/**
 * Pure variant (for tests): the skills dirs to install into, given the home
 * dir, the value of `$XDG_CONFIG_HOME`, and whether `~/.opencode` exists.
 */
export function skillInstallDirs(
  home: string,
  xdgConfigHome: string | undefined,
  legacyExists: boolean,
): string[] {
  const dirs = [join(xdgConfigHome || join(home, ".config"), "opencode", "skills")];
  if (legacyExists) {
    const legacy = join(home, ".opencode", "skills");
    if (!dirs.includes(legacy)) dirs.push(legacy);
  }
  return dirs;
}

/** The skills install dirs for the current machine. */
export function resolveSkillInstallDirs(): string[] {
  return skillInstallDirs(
    homedir(),
    process.env.XDG_CONFIG_HOME,
    existsSync(join(homedir(), ".opencode")),
  );
}
