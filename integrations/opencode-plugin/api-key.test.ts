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

/** Minimal V2 promise-style host: records tool/skill/hook registrations. */
function pluginContext(hooks: Record<string, number>, toolNames: string[]) {
  const registration = {dispose: () => Promise.resolve()};
  return {
    tool: {
      transform: (callback: (editor: {add: (tool: {name: string}) => void}) => void) => {
        callback({add: (tool) => toolNames.push(tool.name)});
        return Promise.resolve(registration);
      },
      hook: (name: string) => {
        hooks[name] = (hooks[name] ?? 0) + 1;
        return Promise.resolve(registration);
      },
    },
    session: {
      hook: (name: string) => {
        hooks[name] = (hooks[name] ?? 0) + 1;
        return Promise.resolve(registration);
      },
    },
    shell: {
      hook: (name: string) => {
        hooks[name] = (hooks[name] ?? 0) + 1;
        return Promise.resolve(registration);
      },
    },
    skill: {transform: () => Promise.resolve(registration)},
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

    // The V2 setup logs the missing key through the server console (the promise
    // Context has no client.app.log) and registers nothing.
    const errors: string[] = [];
    const originalError = console.error;
    console.error = (...args: unknown[]) => {
      errors.push(args.map(String).join(" "));
    };
    const hooks: Record<string, number> = {};
    const toolNames: string[] = [];
    try {
      const cleanup = await Mem0Plugin.setup(pluginContext(hooks, toolNames));

      expect(cleanup).toBeUndefined();
      expect(toolNames).toEqual([]);
      expect(hooks).toEqual({});
      expect(errors).toHaveLength(1);
      expect(errors[0]).toContain("MEM0_API_KEY environment variable not set");
      expect(errors[0]).toContain("https://app.mem0.ai/dashboard/api-keys");
    } finally {
      console.error = originalError;
    }
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

    const hooks: Record<string, number> = {};
    const toolNames: string[] = [];
    const cleanup = await Mem0Plugin.setup(pluginContext(hooks, toolNames));

    // All ten memory tools register, and the lifecycle hooks attach.
    expect(toolNames).toEqual([
      "add_memory",
      "search_memories",
      "get_memories",
      "get_memory",
      "update_memory",
      "delete_memory",
      "delete_all_memories",
      "delete_entities",
      "list_entities",
      "get_event_status",
    ]);
    expect(hooks["prompt"]).toBe(1);
    expect(hooks["context"]).toBe(1);
    expect(hooks["compaction"]).toBe(1);
    expect(hooks["execute.before"]).toBe(1);
    expect(hooks["execute.after"]).toBe(1);
    expect(hooks["create.before"]).toBe(1);
    cleanup?.();
    cleanup?.();
  });
});
