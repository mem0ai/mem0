/**
 * Best-effort read/write of ~/.mem0/config.json from the TS SDK.
 *
 * Used to stitch PostHog identities: SDKs and CLIs persist anonymous
 * distinct_id values here, and the TS MemoryClient reads those on init to
 * fire $identify and merge them into the email identity.
 *
 * Node-only. Browsers (no `process.versions.node`) no-op.
 */

export interface Mem0AnonIds {
  oss?: string;
  cli?: string;
  aliasedPairs: string[];
}

interface NodeFs {
  fs: typeof import("fs");
  path: typeof import("path");
  crypto: typeof import("crypto");
  configPath: string;
}

async function getNodeFs(): Promise<NodeFs | null> {
  if (typeof process === "undefined" || !process.versions?.node) return null;
  try {
    const [fs, path, os, crypto] = await Promise.all([
      import("fs"),
      import("path"),
      import("os"),
      import("crypto"),
    ]);
    const fsMod = (fs as any).default ?? fs;
    const pathMod = (path as any).default ?? path;
    const osMod = (os as any).default ?? os;
    const cryptoMod = (crypto as any).default ?? crypto;
    const dir = process.env.MEM0_DIR || pathMod.join(osMod.homedir(), ".mem0");
    return {
      fs: fsMod,
      path: pathMod,
      crypto: cryptoMod,
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

function writeConfig(node: NodeFs, config: Record<string, any>): void {
  node.fs.mkdirSync(node.path.dirname(node.configPath), { recursive: true });
  node.fs.writeFileSync(node.configPath, JSON.stringify(config, null, 4));
}

function aliasPairMarker(node: NodeFs, anonId: string, email: string): string {
  return node.crypto
    .createHash("sha256")
    .update(`${anonId}\0${email}`, "utf8")
    .digest("hex");
}

function randomUserId(node: NodeFs): string {
  if (typeof node.crypto.randomUUID === "function") {
    return node.crypto.randomUUID();
  }
  return (
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15)
  );
}

export async function getOrCreateMem0UserId(): Promise<string | null> {
  const node = await getNodeFs();
  if (!node) return null;
  try {
    const config = loadConfig(node) ?? {};
    if (typeof config.user_id === "string" && config.user_id) {
      return config.user_id;
    }
    const userId = randomUserId(node);
    config.user_id = userId;
    writeConfig(node, config);
    return userId;
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
    aliasedPairs: Array.isArray(telemetry.aliased_pairs)
      ? telemetry.aliased_pairs.filter(
          (item: unknown) => typeof item === "string",
        )
      : [],
  };
}

export async function isMem0Aliased(
  anonId: string,
  email: string,
): Promise<boolean> {
  if (!anonId || !email) return false;
  const node = await getNodeFs();
  if (!node) return false;
  const config = loadConfig(node);
  if (!config) return false;
  const telemetry =
    config.telemetry && typeof config.telemetry === "object"
      ? config.telemetry
      : {};
  const aliasedPairs = Array.isArray(telemetry.aliased_pairs)
    ? telemetry.aliased_pairs
    : [];
  return aliasedPairs.includes(aliasPairMarker(node, anonId, email));
}

export async function markMem0Aliased(
  anonId: string,
  email: string,
): Promise<void> {
  const node = await getNodeFs();
  if (!node) return;
  try {
    const config = loadConfig(node) ?? {};
    const telemetry =
      config.telemetry && typeof config.telemetry === "object"
        ? config.telemetry
        : {};
    const aliasedPairs = Array.isArray(telemetry.aliased_pairs)
      ? telemetry.aliased_pairs
      : [];
    const marker = aliasPairMarker(node, anonId, email);
    if (!aliasedPairs.includes(marker)) {
      aliasedPairs.push(marker);
    }
    telemetry.aliased_pairs = aliasedPairs;
    config.telemetry = telemetry;
    writeConfig(node, config);
  } catch {
    // Best-effort: read-only filesystems and unwritable paths just skip.
  }
}
