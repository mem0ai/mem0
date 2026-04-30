/**
 * Best-effort read/write of ~/.mem0/config.json from the TS SDK.
 *
 * Used to stitch PostHog identities: the OSS Python SDK and the Python CLI
 * each persist an anonymous distinct_id here, and the TS MemoryClient needs
 * to read those on init so it can fire $identify and merge them into the
 * email-based identity.
 *
 * Node-only. In browsers (or any environment without `process.versions.node`)
 * every function returns null/no-ops without attempting `fs` access.
 */

export interface Mem0AnonIds {
  oss?: string;
  cli?: string;
  aliasedTo?: string;
}

function isNode(): boolean {
  try {
    return (
      typeof process !== "undefined" &&
      !!process.versions &&
      !!process.versions.node
    );
  } catch {
    return false;
  }
}

async function loadNodeModules(): Promise<{
  fs: typeof import("fs");
  path: typeof import("path");
  os: typeof import("os");
} | null> {
  if (!isNode()) return null;
  try {
    const [fs, path, os] = await Promise.all([
      import("fs"),
      import("path"),
      import("os"),
    ]);
    return {
      fs: fs.default ?? fs,
      path: path.default ?? path,
      os: os.default ?? os,
    };
  } catch {
    return null;
  }
}

async function configPath(): Promise<{
  path: string;
  modules: NonNullable<Awaited<ReturnType<typeof loadNodeModules>>>;
} | null> {
  const modules = await loadNodeModules();
  if (!modules) return null;
  try {
    const dir =
      process.env.MEM0_DIR || modules.path.join(modules.os.homedir(), ".mem0");
    return { path: modules.path.join(dir, "config.json"), modules };
  } catch {
    return null;
  }
}

async function loadRawConfig(): Promise<Record<string, unknown> | null> {
  const resolved = await configPath();
  if (!resolved) return null;
  try {
    if (!resolved.modules.fs.existsSync(resolved.path)) return null;
    const raw = resolved.modules.fs.readFileSync(resolved.path, "utf8");
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export async function readMem0AnonIds(): Promise<Mem0AnonIds | null> {
  const config = await loadRawConfig();
  if (!config) return null;
  const telemetry =
    config.telemetry && typeof config.telemetry === "object"
      ? (config.telemetry as Record<string, unknown>)
      : {};
  const oss = typeof config.user_id === "string" ? config.user_id : undefined;
  const cli =
    typeof telemetry.anonymous_id === "string"
      ? telemetry.anonymous_id
      : undefined;
  const aliasedTo =
    typeof telemetry.aliased_to === "string" ? telemetry.aliased_to : undefined;
  return { oss, cli, aliasedTo };
}

export async function markMem0Aliased(email: string): Promise<void> {
  const resolved = await configPath();
  if (!resolved) return;
  try {
    const dirname = resolved.modules.path.dirname(resolved.path);
    resolved.modules.fs.mkdirSync(dirname, { recursive: true });
    const config = (await loadRawConfig()) ?? {};
    const telemetry =
      config.telemetry && typeof config.telemetry === "object"
        ? (config.telemetry as Record<string, unknown>)
        : {};
    telemetry.aliased_to = email;
    config.telemetry = telemetry;
    resolved.modules.fs.writeFileSync(
      resolved.path,
      JSON.stringify(config, null, 4),
    );
  } catch {
    // Read-only filesystem (Lambda, container) — alias is best-effort.
  }
}
