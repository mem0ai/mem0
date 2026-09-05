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
let nextMutationFailure: "add" | "delete" | "deleteAll" | "deleteUsers" | undefined;

function rejectArmedMutation(name: typeof nextMutationFailure): void {
  if (nextMutationFailure !== name) return;
  nextMutationFailure = undefined;
  throw new Error(`${name} failed`);
}

mock.module("os", () => ({
  homedir: () => testHome,
  userInfo: () => ({ username: "test-user" }),
}));

class FakeMemoryClient {
  client = {
    get: async (path: string) => {
      calls.push(["event.get", path]);
      return {data: {path}};
    },
  };
  constructor(public opts: unknown) {}
  async add(messages: unknown, params: unknown) {
    activeAdds++;
    maxActiveAdds = Math.max(maxActiveAdds, activeAdds);
    try {
      await addGate;
      rejectArmedMutation("add");
      calls.push(["add", messages, params]);
      return {id: "mem_1"};
    } finally {
      activeAdds--;
    }
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
    rejectArmedMutation("deleteUsers");
    calls.push(["deleteUsers", params]);
    return { message: "deleted" };
  }
  async deleteAll(params: unknown) {
    rejectArmedMutation("deleteAll");
    calls.push(["deleteAll", params]);
    return { message: "deleted" };
  }
  async delete(id: unknown) {
    rejectArmedMutation("delete");
    calls.push(["delete", id]);
    return {message: "deleted"};
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
            : command.includes("branch --show-current")
              ? "main\n"
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
    nextMutationFailure = undefined;
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

  test("add_memory sanitizes nested metadata before calling the SDK", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const secret = "s" + "k-" + "abcdefghijklmnopqrstuvwxyz";

    await hooks.tool.add_memory.execute(
      {
        text: "store safe metadata",
        metadata: {
          owner: "team-a",
          nested: {token: "short-value", notes: ["safe", `credential ${secret}`]},
        },
      },
      {sessionID: "session-a"} as any,
    );

    const call = calls.find((candidate) => candidate[0] === "add");
    expect((call![2] as any).metadata).toMatchObject({
      owner: "team-a",
      nested: {token: "[REDACTED]", notes: ["safe", "credential [REDACTED]"]},
      session_id: "session-a",
      branch: "main",
    });
  });

  test("update_memory sanitizes nested metadata before calling the SDK", async () => {
    const hooks: any = await Mem0Plugin(ctx());

    await hooks.tool.update_memory.execute(
      {id: "mem_1", metadata: {credentials: {password: "short-value"}, owner: "team-a"}},
      {sessionID: "session-a"} as any,
    );

    const call = calls.find((candidate) => candidate[0] === "update");
    expect((call![2] as any).metadata).toEqual({
      credentials: "[REDACTED]",
      owner: "team-a",
    });
  });

  test("delete_entities rejects an empty selector without calling the SDK", async () => {
    const hooks: any = await Mem0Plugin(ctx());

    await expect(hooks.tool.delete_entities.execute({}, { sessionID: "session-a" } as any)).rejects.toThrow(
      "at least one",
    );
    expect(calls.some((c) => c[0] === "deleteUsers")).toBe(false);
  });

  test("bulk deletion requires confirmation and rejects foreign identity selectors", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const context = {sessionID: "session-a"} as any;

    await expect(hooks.tool.delete_all_memories.execute({}, context)).rejects.toThrow("confirmation");
    await expect(
      hooks.tool.delete_all_memories.execute({confirm: true, user_id: "another-user"}, context),
    ).rejects.toThrow("active user");
    await expect(
      hooks.tool.delete_entities.execute({confirm: true, app_id: "another-project"}, context),
    ).rejects.toThrow("active project");
    expect(calls.some((c) => c[0] === "deleteAll" || c[0] === "deleteUsers")).toBe(false);
  });

  test("destructive tools reject an invalid explicit scope without SDK deletion", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const context = {sessionID: "session-a"} as any;

    await expect(
      hooks.tool.delete_all_memories.execute({confirm: true, scope: "sessionn"}, context),
    ).rejects.toThrow("invalid scope");
    await expect(
      hooks.tool.delete_entities.execute(
        {confirm: true, scope: "projectt", app_id: "mem0ai-mem0"},
        context,
      ),
    ).rejects.toThrow("invalid scope");

    expect(calls.some((call) => call[0] === "deleteAll" || call[0] === "deleteUsers")).toBe(false);
  });

  test("confirmed entity deletion sends exactly the active project selector", async () => {
    const hooks: any = await Mem0Plugin(ctx());

    await hooks.tool.delete_entities.execute(
      {confirm: true, app_id: "mem0ai-mem0"},
      {sessionID: "session-a"} as any,
    );

    const call = calls.find((c) => c[0] === "deleteUsers");
    expect(call?.[1]).toMatchObject({appId: "mem0ai-mem0"});
    expect((call?.[1] as any).userId).toBeUndefined();
    expect((call?.[1] as any).agentId).toBeUndefined();
    expect((call?.[1] as any).runId).toBeUndefined();
  });

  test("entity deletion rejects ambiguous selectors and scope mismatches", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const context = {sessionID: "session-a", agent: "build-agent"} as any;

    await expect(
      hooks.tool.delete_entities.execute(
        {confirm: true, user_id: "test-user"},
        context,
      ),
    ).rejects.toThrow('scope="global"');
    await expect(
      hooks.tool.delete_entities.execute(
        {confirm: true, app_id: "mem0ai-mem0", run_id: "session-a"},
        context,
      ),
    ).rejects.toThrow("exactly one");
    expect(calls.some((c) => c[0] === "deleteUsers")).toBe(false);
  });

  test("entity deletion routes user, run, and agent scopes as single SDK selectors", async () => {
    const hooks: any = await Mem0Plugin(ctx());
    const context = {sessionID: "session-a", agent: "build-agent"} as any;

    await hooks.tool.delete_entities.execute(
      {confirm: true, scope: "global", user_id: "test-user"},
      context,
    );
    await hooks.tool.delete_entities.execute(
      {confirm: true, scope: "session", run_id: "session-a"},
      context,
    );
    await hooks.tool.delete_entities.execute(
      {confirm: true, agent_id: "build-agent"},
      context,
    );

    expect(calls.filter((c) => c[0] === "deleteUsers").map((c) => c[1])).toEqual([
      {userId: "test-user"},
      {runId: "session-a"},
      {agentId: "build-agent"},
    ]);
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

  for (const mutation of ["add", "delete", "deleteAll", "deleteUsers"] as const) {
    test(`failed dream ${mutation} mutation does not record consolidation completion`, async () => {
      delete process.env.MEM0_DREAM;
      const stateDir = join(testHome, ".mem0");
      mkdirSync(stateDir, {recursive: true});
      writeFileSync(
        join(stateDir, "settings.json"),
        JSON.stringify({dream: {enabled: true, auto: true, minHours: 0, minSessions: 0, minMemories: 0}}),
      );
      const hooks: any = await Mem0Plugin(ctx());

      await hooks["chat.message"](
        {sessionID: "session-a"},
        {parts: [{type: "text", text: "Please remember the tested decision."}]},
      );
      expect(existsSync(join(stateDir, "mem0-dream.lock"))).toBe(true);

      nextMutationFailure = mutation;
      const mutationCall = mutation === "add"
        ? hooks.tool.add_memory.execute(
            {text: "The tested decision", scope: "session"},
            {sessionID: "session-a"} as any,
          )
        : mutation === "delete"
          ? hooks.tool.delete_memory.execute(
              {id: "mem_1"},
              {sessionID: "session-a"} as any,
            )
          : mutation === "deleteAll"
            ? hooks.tool.delete_all_memories.execute(
                {confirm: true, scope: "project"},
                {sessionID: "session-a"} as any,
              )
            : hooks.tool.delete_entities.execute(
                {confirm: true, scope: "project", app_id: "mem0ai-mem0"},
                {sessionID: "session-a"} as any,
              );

      await expect(mutationCall).rejects.toThrow(`${mutation} failed`);
      await hooks.event({event: {type: "session.idle", properties: {sessionID: "session-a"}}});

      expect(existsSync(join(stateDir, "mem0-dream.lock"))).toBe(false);
      const state = JSON.parse(readFileSync(join(stateDir, "mem0-dream-state.json"), "utf8"));
      expect(state.lastConsolidatedAt).toBe(0);
      expect(state.sessionsSince).toBeGreaterThan(0);
    });
  }

  test("a later failed dream mutation prevents completion after an earlier success", async () => {
    delete process.env.MEM0_DREAM;
    const stateDir = join(testHome, ".mem0");
    mkdirSync(stateDir, {recursive: true});
    writeFileSync(
      join(stateDir, "settings.json"),
      JSON.stringify({dream: {enabled: true, auto: true, minHours: 0, minSessions: 0, minMemories: 0}}),
    );
    const hooks: any = await Mem0Plugin(ctx());

    await hooks["chat.message"](
      {sessionID: "session-a"},
      {parts: [{type: "text", text: "Please remember the tested decision."}]},
    );
    await hooks.tool.add_memory.execute(
      {text: "The consolidated decision", scope: "session"},
      {sessionID: "session-a"} as any,
    );

    nextMutationFailure = "delete";
    await expect(
      hooks.tool.delete_memory.execute(
        {id: "mem_1"},
        {sessionID: "session-a"} as any,
      ),
    ).rejects.toThrow("delete failed");
    await hooks.event({event: {type: "session.idle", properties: {sessionID: "session-a"}}});

    expect(existsSync(join(stateDir, "mem0-dream.lock"))).toBe(false);
    const state = JSON.parse(readFileSync(join(stateDir, "mem0-dream-state.json"), "utf8"));
    expect(state.lastConsolidatedAt).toBe(0);
    expect(state.sessionsSince).toBeGreaterThan(0);
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

  test("does not capture tools that expose sensitive files or environment variables", async () => {
    const hooks: any = await Mem0Plugin(ctx());

    await hooks["tool.execute.after"](
      {tool: "read", sessionID: "session-a", args: {file_path: "/workspace/.env"}},
      {title: "Environment", output: "DATABASE_PASSWORD=do-not-store", metadata: {}},
    );
    await hooks["tool.execute.after"](
      {tool: "bash", sessionID: "session-a", args: {command: "printenv"}},
      {title: "Environment", output: "DATABASE_PASSWORD=do-not-store", metadata: {}},
    );
    await hooks.event({
      event: {type: "session.deleted", properties: {info: {id: "session-a"}}},
    });

    expect(calls.some((c) => c[0] === "add" && (c[2] as any)?.metadata?.type === "tool_output")).toBe(false);
  });

  test("session.idle waits for its queued summary write", async () => {
    const messages = [{
      info: {id: "message-1", role: "user", sessionID: "session-a"},
      parts: [{type: "text", text: "Remember the validated lifecycle decision."}],
    }];
    addGate = new Promise<void>((resolve) => {
      releaseAddGate = resolve;
    });
    const hooks: any = await Mem0Plugin(ctx(messages));
    let settled = false;

    const idle = hooks.event({
      event: {type: "session.idle", properties: {sessionID: "session-a"}},
    }).then(() => {
      settled = true;
    });
    await Promise.resolve();
    await Promise.resolve();
    expect(settled).toBe(false);

    releaseAddGate!();
    await idle;
    expect(settled).toBe(true);
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
    const eventId = "3c90c3cc-0d44-4b50-8888-8dd25736052a";
    const res = await hooks.tool.get_event_status.execute({event_id: eventId}, {} as any);

    expect(JSON.parse(res)).toEqual({path: `/v1/event/${eventId}/`});
  });

  test("get_event_status rejects non-UUID path input before the authenticated client", async () => {
    const hooks: any = await Mem0Plugin(ctx());

    await expect(
      hooks.tool.get_event_status.execute({event_id: "../memories"}, {} as any),
    ).rejects.toThrow("valid event UUID");
    expect(calls.some((call) => call[0] === "event.get")).toBe(false);
  });
});
