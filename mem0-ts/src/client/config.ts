/**
 * Best-effort read/write of ~/.mem0/config.json from the TS SDK.
 *
 * Used to stitch PostHog identities: the OSS Python SDK and the Python CLI
 * each persist an anonymous distinct_id here, and the TS MemoryClient reads
 * those on init to fire $identify and merge them into the email identity.
 *
 * Node-only. Browsers (no `process.versions.node`) no-op.
 */

export interface Mem0AnonIds {
  oss?: string;
  cli?: string;
  aliasedTo?: string;
}

interface NodeFs {
  fs: typeof import("fs");
  path: typeof import("path");
  configPath: string;
}

async function getNodeFs(): Promise<NodeFs | null> {
  if (typeof process === "undefined" || !process.versions?.node) return null;
  try {
    const [fs, path, os] = await Promise.all([
      import("fs"),
      import("path"),
      import("os"),
    ]);
    const fsMod = (fs as any).default ?? fs;
    const pathMod = (path as any).default ?? path;
    const osMod = (os as any).default ?? os;
    const dir = process.env.MEM0_DIR || pathMod.join(osMod.homedir(), ".mem0");
    return {
      fs: fsMod,
      path: pathMod,
      configPath: pathMod.join(dir, "config.json"),
    };
  } catch {
    return null;
  }
}

function loadConfig(node: NodeFs): Record<string, any> | null {
  try {
    if (!node.fs.existsSync(node.configPath)) return null;
    const parsed = JSON.parse(node.fs.readFileSync(node.configPath, "utf8"));
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

export async function readMem0AnonIds(): Promise<Mem0AnonIds | null> {
  const node = await getNodeFs();
  if (!node) return null;
  const config = loadConfig(node);
  if (!config) return null;
  const telemetry =
    config.telemetry && typeof config.telemetry === "object"
      ? config.telemetry
      : {};
  return {
    oss: typeof config.user_id === "string" ? config.user_id : undefined,
    cli:
      typeof telemetry.anonymous_id === "string"
        ? telemetry.anonymous_id
        : undefined,
    aliasedTo:
      typeof telemetry.aliased_to === "string"
        ? telemetry.aliased_to
        : undefined,
  };
}

export async function markMem0Aliased(email: string): Promise<void> {
  const node = await getNodeFs();
  if (!node) return;
  try {
    node.fs.mkdirSync(node.path.dirname(node.configPath), { recursive: true });
    const config = loadConfig(node) ?? {};
    const telemetry =
      config.telemetry && typeof config.telemetry === "object"
        ? config.telemetry
        : {};
    telemetry.aliased_to = email;
    config.telemetry = telemetry;
    node.fs.writeFileSync(node.configPath, JSON.stringify(config, null, 4));
  } catch {
    // Best-effort: read-only filesystems and unwritable paths just skip.
  }
}
