import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Capture every mem0ai SDK call so we can assert the tool -> SDK -> scope wiring
// without a live Mem0 platform or a real API key.
const calls: Array<[string, ...unknown[]]> = [];
let testHome: string;
let searchResults: Array<{ id: string; memory: string }> = [];
let addGate: Promise<void> | undefined;
let releaseAddGate: (() => void) | undefined;
let activeAdds = 0;
let maxActiveAdds = 0;

mock.module("os", () => ({
  homedir: () => testHome,
  userInfo: () => ({ username: "test-user" }),
}));

class FakeMemoryClient {
  client = { get: async (path: string) => ({ data: { path } }) };
  constructor(public opts: unknown) {}
  async add(messages: unknown, params: unknown) {
    activeAdds++;
    maxActiveAdds = Math.max(maxActiveAdds, activeAdds);
    await addGate;
    calls.push(["add", messages, params]);
    activeAdds--;
    return { id: "mem_1" };
  }
  async search(query: unknown, params: unknown) {
    calls.push(["search", query, params]);
    return { results: searchResults };
  }
  async getAll(params: unknown) {
    calls.push(["getAll", params]);
    return { results: searchResults, count: searchResults.length };
  }
  async getProject() {
    return { customCategories: [] };
  }
  async updateProject(params: unknown) {
    calls.push(["updateProject", params]);
    return {};
  }
  async update(id: unknown, params: unknown) {
    calls.push(["update", id, params]);
    return { id };
  }
  async deleteUsers(params: unknown) {
    calls.push(["deleteUsers", params]);
    return { message: "deleted" };
  }
}

mock.module("mem0ai", () => ({ MemoryClient: FakeMemoryClient }));

// Import AFTER the mock so the plugin constructs the fake client.
const pluginModule = await import("./kilo-mem0");
const Mem0Plugin: any = pluginModule.Mem0Plugin;

function ctx(sessionMessages: unknown[] = []) {
  const makeShell = (cwd?: string): any => {
    const shell = (strings: TemplateStringsArray) => {
      const command = strings.join("");
      calls.push(["shell", command, cwd]);
      return {
        quiet: async () => ({
          stdout: command.includes("remote get-url")
            ? "git@github.com:mem0ai/mem0.git\n"
            : "/workspace/mem0\n",
        }),
      };
    };
    shell.cwd = (nextCwd: string) => makeShell(nextCwd);
    return shell;
  };

  return {
    $: makeShell(),
    directory: "/workspace/mem0/integrations/kilo-plugin",
    worktree: "/workspace/mem0",
    client: {
      app: { log: async () => {} },
      session: {
        messages: async (options: unknown) => {
          calls.push(["session.messages", options]);
          return { data: sessionMessages };
        },
      },
    },
  } as any;
}

describe("kilo-mem0 tool execution (mocked mem0ai SDK)", () => {
  beforeEach(() => {
    calls.length = 0;
    searchResults = [];
    addGate = undefined;
    releaseAddGate = undefined;
    activeAdds = 0;
    maxActiveAdds = 0;
    testHome = mkdtempSync(join(tmpdir(), "mem0-kilo-tools-"));
    process.env.MEM0_API_KEY = "m0-testkey1234567890";
    process.env.MEM0_TELEMETRY = "false"; // no PostHog fetch during tests
    process.env.MEM0_DREAM = "false"; // keep lifecycle tests off the user's ~/.mem0 state
  });

  afterEach(() => {
    delete process.env.MEM0_API_KEY;
    delete process.env.MEM0_TELEMETRY;
    delete process.env.MEM0_DREAM;
    rmSync(testHome, { recursive: true, force: true });
  });

  test("search_memories calls the SDK with scoped filters and returns JSON", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const res = await hooks.tool.search_memories.execute({ query: "auth bug", scope: "project" }, {} as any);

    const call = calls.find((c) => c[0] === "search");
    expect(call).toBeDefined();
    expect(call![1]).toBe("auth bug");
    expect((call![2] as any).filters).toBeDefined();
    expect(() => JSON.parse(res)).not.toThrow();
  });

  test("add_memory stamps source=kilo metadata and calls the SDK", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const res = await hooks.tool.add_memory.execute({ text: "use bun for tests" }, {} as any);

    const call = calls.find((c) => c[0] === "add");
    expect(call).toBeDefined();
    expect((call![2] as any).metadata.source).toBe("kilo");
    expect(() => JSON.parse(res)).not.toThrow();
  });

  test("add_memory redacts secret patterns before calling the SDK", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const secret = "s" + "k-" + "abcdefghijklmnopqrstuvwxyz";

    await hooks.tool.add_memory.execute({ text: `token ${secret}` }, { sessionID: "session-a" } as any);

    const call = calls.find((c) => c[0] === "add");
    expect((call![1] as any)[0].content).toBe("token [REDACTED]");
  });

  test("update_memory redacts secret patterns before calling the SDK", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const secret = "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz0123456789";

    await hooks.tool.update_memory.execute(
      { id: "mem_1", text: `credential ${secret}` },
      { sessionID: "session-a" } as any,
    );

    const call = calls.find((c) => c[0] === "update");
    expect((call![2] as any).text).toBe("credential [REDACTED]");
  });

  test("delete_entities rejects an empty selector without calling the SDK", async () => {
    const hooks: any = await Mem0Plugin(ctx());

    await expect(hooks.tool.delete_entities.execute({}, { sessionID: "session-a" } as any)).rejects.toThrow(
      "at least one",
    );
    expect(calls.some((c) => c[0] === "deleteUsers")).toBe(false);
  });

  test("session-scoped tools use the real Kilo session ID", async () => {
    const hooks: any = await Mem0Plugin(ctx());

    await hooks.tool.add_memory.execute(
      { text: "memory from session a", scope: "session" },
      { sessionID: "session-a" } as any,
    );
    await hooks.tool.add_memory.execute(
      { text: "memory from session b", scope: "session" },
      { sessionID: "session-b" } as any,
    );

    const addCalls = calls.filter((c) => c[0] === "add");
    expect((addCalls[0]![2] as any).run_id).toBe("session-a");
    expect((addCalls[1]![2] as any).run_id).toBe("session-b");
    expect((addCalls[0]![2] as any).metadata.session_id).toBe("session-a");
    expect((addCalls[1]![2] as any).metadata.session_id).toBe("session-b");
  });

  test("initializes each Kilo session independently", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const output = { parts: [{ type: "text", text: "A sufficiently long user message" }] };

    await hooks["chat.message"]({ sessionID: "session-a" }, output);
    await hooks["chat.message"]({ sessionID: "session-b" }, output);

    expect(calls.filter((c) => c[0] === "getAll")).toHaveLength(2);
  });

  test("stores a redacted session summary when Kilo reports session.idle", async () => {
    const secret = "m" + "0-" + "abcdefghijklmnopqrstuvwxyz";
    const messages = [
      {
        info: { id: "message-1", role: "user", sessionID: "session-a" },
        parts: [{ type: "text", text: `remember ${secret}` }],
      },
      {
        info: { id: "message-2", role: "assistant", sessionID: "session-a" },
        parts: [{ type: "text", text: "Implemented the requested fix." }],
      },
    ];
    const hooks: any = await Mem0Plugin(ctx(messages));

    await hooks.event({ event: { type: "session.idle", properties: { sessionID: "session-a" } } });
    await Promise.resolve();
    await Promise.resolve();

    const call = calls.find((c) => c[0] === "add");
    expect(call).toBeDefined();
    expect((call![1] as any)[0].content).toContain("[REDACTED]");
    expect((call![1] as any)[0].content).not.toContain(secret);
    expect((call![2] as any).metadata).toMatchObject({
      type: "session_summary",
      source: "kilo",
      session_id: "session-a",
    });

    await hooks.event({ event: { type: "session.idle", properties: { sessionID: "session-a" } } });
    await Promise.resolve();
    await Promise.resolve();
    expect(calls.filter((c) => c[0] === "add")).toHaveLength(1);
    expect(calls.filter((c) => c[0] === "session.messages")).toHaveLength(1);
  });

  test("releases and completes an auto-dream on session.idle", async () => {
    delete process.env.MEM0_DREAM;
    const stateDir = join(testHome, ".mem0");
    mkdirSync(stateDir, { recursive: true });
    writeFileSync(
      join(stateDir, "settings.json"),
      JSON.stringify({ dream: { enabled: true, auto: true, minHours: 0, minSessions: 0, minMemories: 0 } }),
    );
    const messages = [
      {
        info: { id: "message-1", role: "user", sessionID: "session-a" },
        parts: [{ type: "text", text: "Please remember the tested decision." }],
      },
    ];
    const hooks: any = await Mem0Plugin(ctx(messages));

    await hooks["chat.message"](
      { sessionID: "session-a" },
      { parts: [{ type: "text", text: "Please remember the tested decision." }] },
    );
    expect(existsSync(join(stateDir, "mem0-dream.lock"))).toBe(true);

    await hooks.tool.add_memory.execute(
      { text: "The tested decision", scope: "session" },
      { sessionID: "session-a" } as any,
    );
    await hooks.event({ event: { type: "session.idle", properties: { sessionID: "session-a" } } });

    expect(existsSync(join(stateDir, "mem0-dream.lock"))).toBe(false);
    const state = JSON.parse(readFileSync(join(stateDir, "mem0-dream-state.json"), "utf8"));
    expect(state.lastConsolidatedAt).toBeGreaterThan(0);
    expect(state.sessionsSince).toBe(0);
  });

  test("deleting a Kilo session clears its in-memory state", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const output = { parts: [{ type: "text", text: "A sufficiently long user message" }] };

    await hooks["chat.message"]({ sessionID: "session-a" }, output);
    await hooks.event({
      event: { type: "session.deleted", properties: { info: { id: "session-a" } } },
    });
    await hooks["chat.message"]({ sessionID: "session-a" }, output);

    expect(calls.filter((c) => c[0] === "getAll")).toHaveLength(2);
  });

  test("captures a bounded, redacted tool result in the originating session", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const secret = "s" + "k-" + "abcdefghijklmnopqrstuvwxyz";
    const toolOutput = `Build output ${"x".repeat(80)} token ${secret}`;

    await hooks["tool.execute.after"](
      { tool: "bash", sessionID: "session-a", args: { command: "bun test" } },
      { title: "Build", output: toolOutput, metadata: {} },
    );
    await Promise.resolve();
    await Promise.resolve();

    const call = calls.find(
      (candidate) => candidate[0] === "add" && (candidate[2] as any)?.metadata?.type === "tool_output",
    );
    expect(call).toBeDefined();
    expect((call![1] as any)[0].content).toContain("[REDACTED]");
    expect((call![1] as any)[0].content).not.toContain(secret);
    expect((call![2] as any)).toMatchObject({
      run_id: "session-a",
      metadata: { type: "tool_output", source: "kilo", session_id: "session-a" },
    });
  });

  test("serializes tool-result captures and drains them before session deletion", async () => {
    addGate = new Promise<void>((resolve) => {
      releaseAddGate = resolve;
    });
    const hooks: any = await Mem0Plugin(ctx());

    await hooks["tool.execute.after"](
      {tool: "bash", sessionID: "session-a", args: {command: "bun test"}},
      {title: "First", output: "first captured output", metadata: {}},
    );
    await hooks["tool.execute.after"](
      {tool: "read", sessionID: "session-a", args: {}},
      {title: "Second", output: "second captured output", metadata: {}},
    );
    await Promise.resolve();
    expect(maxActiveAdds).toBe(1);

    const deletion = hooks.event({
      event: {type: "session.deleted", properties: {info: {id: "session-a"}}},
    });
    releaseAddGate!();
    await deletion;

    expect(maxActiveAdds).toBe(1);
    expect(calls.filter((c) => c[0] === "add")).toHaveLength(2);
  });

  test("appends the number of unique memories used to completed text", async () => {
    searchResults = [{ id: "memory-1", memory: "Use Bun for this project." }];
    const hooks: any = await Mem0Plugin(ctx());

    await hooks["chat.message"](
      { sessionID: "session-a" },
      { parts: [{ type: "text", text: "What tool should this project use?" }] },
    );
    const output = { text: "Use Bun." };
    await hooks["experimental.text.complete"](
      { sessionID: "session-a", messageID: "message-1", partID: "part-1" },
      output,
    );

    expect(output.text).toBe("Use Bun.\n\n[mem0: 1 memory used]");
  });

  test("get_event_status uses the SDK's authed raw client", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const res = await hooks.tool.get_event_status.execute({ event_id: "evt_42" }, {} as any);

    expect(JSON.parse(res)).toEqual({ path: "/v1/event/evt_42/" });
  });
});
