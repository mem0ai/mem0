// Issue #7602: OpenCode V2's plugin loader only accepts a default export shaped
// { id, effect | setup } (an object). The plugin used to export an async factory
// function (V1 contract), so the V2 loader dropped the module silently. These
// tests pin the V2 module shape and the V2 hook/tool registrations.
//
// V2 loader schema (opencode packages/core/src/plugin/module.ts):
//   default: Union([{id, effect: fn}, {id, setup: fn}])
import {afterEach, describe, expect, test} from "bun:test";
import Mem0Plugin from "./opencode-mem0";

const originalKey = process.env.MEM0_API_KEY;
const originalTelemetry = process.env.MEM0_TELEMETRY;
const originalFetch = globalThis.fetch;
const testCleanups: Array<() => Promise<void> | void> = [];

afterEach(async () => {
  while (testCleanups.length > 0) {
    await testCleanups.pop()?.();
  }
  if (originalKey === undefined) delete process.env.MEM0_API_KEY;
  else process.env.MEM0_API_KEY = originalKey;
  if (originalTelemetry === undefined) delete process.env.MEM0_TELEMETRY;
  else process.env.MEM0_TELEMETRY = originalTelemetry;
  globalThis.fetch = originalFetch;
});

/** Fetch stub so no test touches the network (same pattern as api-key.test.ts). */
function stubFetch(): void {
  globalThis.fetch = (async (input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
    const body = url.includes("/v1/ping/")
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

/** Records every registration the V2 setup makes, mirroring the V2 SDK surface. */
function v2TestContext() {
  const sessionHooks = new Map<string, (input: any) => Promise<void> | void>();
  const toolHooks = new Map<string, (input: any) => Promise<void> | void>();
  const shellHooks = new Map<string, (input: any) => Promise<void> | void>();
  const tools: any[] = [];
  const skills: any[] = [];
  const commands: any[] = [];
  const registration = {dispose: async () => {}};
  const ctx: any = {
    app: {name: "opencode", version: "2.0.26", channel: "stable"},
    session: {
      hook: async (name: string, cb: any) => {
        sessionHooks.set(name, cb);
        return registration;
      },
    },
    tool: {
      hook: async (name: string, cb: any) => {
        toolHooks.set(name, cb);
        return registration;
      },
      transform: async (cb: any) => {
        cb({add: (t: any) => tools.push(t)});
        return registration;
      },
    },
    shell: {
      hook: async (name: string, cb: any) => {
        shellHooks.set(name, cb);
        return registration;
      },
    },
    skill: {
      transform: async (cb: any) => {
        cb({add: (s: any) => skills.push(s)});
        return registration;
      },
    },
    command: {
      transform: async (cb: any) => {
        cb({add: (c: any) => commands.push(c)});
        return registration;
      },
    },
  };
  return {ctx, sessionHooks, toolHooks, shellHooks, tools, skills, commands};
}

describe("V2 module shape (issue #7602)", () => {
  test("default export is a { id, setup } record, not a bare function", () => {
    // OpenCode V2 loader: Schema.Struct({default: Union([{id, effect}, {id, setup}])})
    // rejects a function default with SchemaError(Expected object at ["default"]).
    expect(typeof Mem0Plugin).toBe("object");
    expect(Mem0Plugin).not.toBeNull();
    expect(typeof (Mem0Plugin as any).id).toBe("string");
    expect(((Mem0Plugin as any).id as string).length).toBeGreaterThan(0);
    expect(typeof (Mem0Plugin as any).setup).toBe("function");
  });

  test("keeps the V1 entrypoint reachable via the server key (dual export)", () => {
    expect(typeof (Mem0Plugin as any).server).toBe("function");
  });
});

describe("V2 setup registrations", () => {
  test("registers every migrated V2 hook, the memory tools, skills, and commands", async () => {
    process.env.MEM0_API_KEY = "m0-test-key";
    process.env.MEM0_TELEMETRY = "false";
    stubFetch();
    testCleanups.push(captureDeferredPluginCleanup());

    const plugin = Mem0Plugin as any;
    const {ctx, sessionHooks, toolHooks, shellHooks, tools, skills, commands} = v2TestContext();
    await plugin.setup(ctx);

    // V1 -> V2 hook migration (issue mapping table)
    expect([...sessionHooks.keys()].sort()).toEqual(["compaction", "context", "prompt"]);
    expect([...toolHooks.keys()].sort()).toEqual(["execute.after", "execute.before"]);
    expect([...shellHooks.keys()]).toEqual(["create.before"]);

    // Memory tools surface via ctx.tool.transform
    const toolNames = tools.map((t) => t.name).sort();
    expect(toolNames).toEqual([
      "add_memory",
      "delete_all_memories",
      "delete_entities",
      "delete_memory",
      "get_event_status",
      "get_memories",
      "get_memory",
      "list_entities",
      "search_memories",
      "update_memory",
    ]);
    for (const t of tools) {
      expect(typeof t.description).toBe("string");
      expect(t.input).toBeTruthy();
      expect(typeof t.execute).toBe("function");
    }

    // Bundled skills + /mem0-* slash commands
    expect(skills.length).toBeGreaterThan(0);
    expect(commands.map((c) => c.name).sort()).toEqual(
      skills.map((s: any) => s.id).sort(),
    );
  });

  test("shell create.before injects the MEM0_* identity env vars", async () => {
    process.env.MEM0_API_KEY = "m0-test-key";
    process.env.MEM0_TELEMETRY = "false";
    stubFetch();
    testCleanups.push(captureDeferredPluginCleanup());

    const plugin = Mem0Plugin as any;
    const {ctx, shellHooks} = v2TestContext();
    await plugin.setup(ctx);

    const env: Record<string, string | undefined> = {};
    await shellHooks.get("create.before")!({command: "ls", cwd: "/tmp", env});
    expect(env.MEM0_USER_ID!.length).toBeGreaterThan(0);
    expect(env.MEM0_APP_ID!.length).toBeGreaterThan(0);
    expect(env.MEM0_SESSION_ID!.startsWith("ses_")).toBe(true);
    expect(env.MEM0_BRANCH!.length).toBeGreaterThan(0);
    expect(env.MEM0_GLOBAL_SEARCH).toBe("false");
  });

  test("tool execute.before guards MEMORY.md writes for the V2 payload shape", async () => {
    process.env.MEM0_API_KEY = "m0-test-key";
    process.env.MEM0_TELEMETRY = "false";
    stubFetch();
    testCleanups.push(captureDeferredPluginCleanup());

    const plugin = Mem0Plugin as any;
    const {ctx, toolHooks} = v2TestContext();
    await plugin.setup(ctx);

    const guard = toolHooks.get("execute.before")!;
    expect(guard({tool: "Write", input: {file_path: "src/index.ts"}})).resolves.toBeUndefined();
    expect(guard({tool: "Write", input: {file_path: "MEMORY.md"}})).rejects.toThrow(/add_memory/);
    expect(guard({tool: "Edit", input: {filePath: ".claude/memory/notes.md"}})).rejects.toThrow(/add_memory/);
  });

  test("missing API key skips registration instead of throwing", async () => {
    delete process.env.MEM0_API_KEY;
    process.env.MEM0_TELEMETRY = "false";
    stubFetch();
    testCleanups.push(captureDeferredPluginCleanup());

    const plugin = Mem0Plugin as any;
    const {ctx, sessionHooks, toolHooks, shellHooks, tools} = v2TestContext();
    await plugin.setup(ctx);
    expect(sessionHooks.size).toBe(0);
    expect(toolHooks.size).toBe(0);
    expect(shellHooks.size).toBe(0);
    expect(tools).toHaveLength(0);
  });
});
