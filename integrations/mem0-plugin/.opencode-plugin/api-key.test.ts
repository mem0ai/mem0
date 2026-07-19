import {afterEach, describe, expect, test} from "bun:test";
import {mkdtempSync, mkdirSync, writeFileSync} from "fs";
import {tmpdir} from "os";
import {join} from "path";
import {parseApiKeyLine, resolveApiKey} from "./api-key";
import Mem0Plugin from "./opencode-mem0";

const originalKey = process.env.MEM0_API_KEY;
const originalHome = process.env.HOME;
const originalUserProfile = process.env.USERPROFILE;
const originalTelemetry = process.env.MEM0_TELEMETRY;
const originalFetch = globalThis.fetch;
const testCleanups: Array<() => Promise<void> | void> = [];

afterEach(async () => {
  while (testCleanups.length > 0) {
    await testCleanups.pop()?.();
  }
  if (originalKey === undefined) delete process.env.MEM0_API_KEY;
  else process.env.MEM0_API_KEY = originalKey;
  if (originalHome === undefined) delete process.env.HOME;
  else process.env.HOME = originalHome;
  if (originalUserProfile === undefined) delete process.env.USERPROFILE;
  else process.env.USERPROFILE = originalUserProfile;
  if (originalTelemetry === undefined) delete process.env.MEM0_TELEMETRY;
  else process.env.MEM0_TELEMETRY = originalTelemetry;
  globalThis.fetch = originalFetch;
});

function home(): string {
  return mkdtempSync(join(tmpdir(), "mem0-api-key-"));
}

function pluginContext(logs: unknown[]) {
  return {
    client: {app: {log: async (entry: unknown) => logs.push(entry)}},
    $: () => ({quiet: async () => ({stdout: ""})}),
  } as any;
}

function stubFetch(): void {
  globalThis.fetch = (async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const body =
      url.includes("/v1/ping/")
        ? {status: "ok", userEmail: "plugin-test@mem0.dev"}
        : url.includes("/v1/projects/")
          ? {customCategories: []}
          : {};
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: {"content-type": "application/json"},
    });
  }) as typeof fetch;
}

function captureDeferredPluginCleanup(): () => Promise<void> {
  const baseline = new Set(process.listeners("beforeExit"));
  return async () => {
    await Promise.resolve();
    for (const listener of process.listeners("beforeExit")) {
      if (!baseline.has(listener)) {
        process.off("beforeExit", listener as (...args: any[]) => void);
      }
    }
  };
}

describe("parseApiKeyLine", () => {
  test("accepts literal export and assignment forms", () => {
    expect(parseApiKeyLine('export MEM0_API_KEY="m0-quoted" # comment')).toBe("m0-quoted");
    expect(parseApiKeyLine("MEM0_API_KEY=m0-literal")).toBe("m0-literal");
  });

  test("rejects unrelated, empty, and executable-looking values", () => {
    expect(parseApiKeyLine("OTHER_KEY=value")).toBeUndefined();
    expect(parseApiKeyLine("MEM0_API_KEY=")).toBeUndefined();
    expect(parseApiKeyLine("MEM0_API_KEY=$MEM0_API_KEY")).toBeUndefined();
    expect(parseApiKeyLine("MEM0_API_KEY=$(cat secret)")).toBeUndefined();
  });
});

describe("resolveApiKey", () => {
  test("explicit environment value wins over profiles", () => {
    const dir = home();
    writeFileSync(join(dir, ".zshrc"), "MEM0_API_KEY=profile\n");
    expect(resolveApiKey({MEM0_API_KEY: " explicit "}, dir)).toBe("explicit");
  });

  test("uses the first valid allowlisted profile", () => {
    const dir = home();
    writeFileSync(join(dir, ".zshrc"), "MEM0_API_KEY=$UNSET\n");
    writeFileSync(join(dir, ".bashrc"), "export MEM0_API_KEY='m0-from-bashrc'\n");
    writeFileSync(join(dir, ".profile"), "MEM0_API_KEY=late\n");
    expect(resolveApiKey({}, dir)).toBe("m0-from-bashrc");
  });

  test("continues after an unreadable or absent earlier profile", () => {
    const dir = home();
    mkdirSync(join(dir, ".zshrc"));
    writeFileSync(join(dir, ".profile"), "MEM0_API_KEY=m0-later\n");
    expect(resolveApiKey({}, dir)).toBe("m0-later");
  });

  test("ignores unsupported files and invalid assignments", () => {
    const dir = home();
    writeFileSync(join(dir, ".env"), "MEM0_API_KEY=unsupported\n");
    writeFileSync(join(dir, ".zshrc"), "MEM0_API_KEY= # empty\nMEM0_API_KEY=$(unsafe)\n");
    expect(resolveApiKey({}, dir)).toBe("");
  });

  test("keeps the missing-key guard when no source yields a key", async () => {
    const dir = home();
    writeFileSync(join(dir, ".zshrc"), "MEM0_API_KEY= # empty\nMEM0_API_KEY=$UNSET\n");
    delete process.env.MEM0_API_KEY;
    process.env.HOME = dir;
    process.env.USERPROFILE = dir;
    process.env.MEM0_TELEMETRY = "false";
    stubFetch();
    testCleanups.push(captureDeferredPluginCleanup());

    const logs: unknown[] = [];
    const plugin = await Mem0Plugin(pluginContext(logs));

    expect(logs).toHaveLength(1);
    expect(logs[0]).toMatchObject({
      body: {
        level: "error",
        message: "MEM0_API_KEY environment variable not set. Get one at https://app.mem0.ai/dashboard/api-keys",
      },
    });
    expect(plugin).toEqual({});
  });

  test("recovers the issue's shell-profile startup path", async () => {
    const dir = home();
    // Problem 2 in issue #6003: Desktop has no process key, but .zshrc does.
    writeFileSync(join(dir, ".zshrc"), 'export MEM0_API_KEY="m0-from-profile"\n');
    delete process.env.MEM0_API_KEY;
    process.env.HOME = dir;
    process.env.USERPROFILE = dir;
    process.env.MEM0_TELEMETRY = "false";
    stubFetch();
    testCleanups.push(captureDeferredPluginCleanup());

    const logs: unknown[] = [];
    const plugin = await Mem0Plugin(pluginContext(logs));

    expect(logs).toHaveLength(0);
    expect(Object.keys(plugin)).toContain("chat.message");
    expect(plugin).toHaveProperty("tool");
  });
});
