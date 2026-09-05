import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  OpenClawPluginApi,
  OpenClawPluginToolContext,
} from "openclaw/plugin-sdk/plugin-entry";
import type { Mem0Provider, MemoryItem } from "../types.ts";
import type { SenderContext } from "../isolation.ts";
import { senderUserId } from "../isolation.ts";

vi.mock("../providers.ts", async (importOriginal) => ({
  ...await importOriginal<typeof import("../providers.ts")>(),
  createProvider: vi.fn(),
}));
vi.mock("../cli/config-file.ts", async (importOriginal) => ({
  ...await importOriginal<typeof import("../cli/config-file.ts")>(),
  readPluginAuth: vi.fn(() => ({})),
}));
vi.mock("../fs-safe.ts", async (importOriginal) => ({
  ...await importOriginal<typeof import("../fs-safe.ts")>(),
  bootstrapTelemetryFlag: vi.fn(),
}));
vi.mock("../telemetry.ts", async (importOriginal) => ({
  ...await importOriginal<typeof import("../telemetry.ts")>(),
  captureEvent: vi.fn(),
}));

import memoryPlugin from "../index.ts";
import { createProvider } from "../providers.ts";
import { createPublicArtifactsProvider } from "../public-artifacts.ts";
import { mem0ConfigSchema } from "../config.ts";

const alice: SenderContext = {
  agentId: "assistant", senderId: "alice", channel: "telegram",
  accountId: "work", sessionKey: "agent:assistant:telegram:direct:alice",
  trigger: "user",
};
const bob: SenderContext = {
  ...alice, senderId: "bob", sessionKey: "agent:assistant:telegram:direct:bob",
};

// These are the actual factory fields, not the agent hook's senderId/channel.
function toolContext(ctx: SenderContext): OpenClawPluginToolContext {
  return {
    requesterSenderId: ctx.senderId, messageChannel: ctx.channel,
    agentAccountId: ctx.accountId, agentId: ctx.agentId, sessionKey: ctx.sessionKey,
  };
}

function deferred() {
  let release: () => void = () => { throw new Error("uninitialized deferred"); };
  const promise = new Promise<void>((resolve) => { release = resolve; });
  return { promise, release };
}

function createMemoryStore() {
  const memories = new Map<string, MemoryItem & { run_id?: string }>();
  const provider = {
    add: vi.fn<Mem0Provider["add"]>(async (messages, options) => {
      const id = `m${memories.size + 1}`;
      const memory = messages.filter((m) => m.role !== "system").map((m) => m.content).join("\n");
      memories.set(id, { id, memory, user_id: options.user_id, run_id: options.run_id, score: 0.95 });
      return { results: [{ id, memory, event: "ADD" }] };
    }),
    search: vi.fn<Mem0Provider["search"]>(async (_query, options) =>
      [...memories.values()].filter((m) => m.user_id === options.user_id &&
        (!options.run_id || options.run_id === m.run_id))),
    getAll: vi.fn<Mem0Provider["getAll"]>(async (options) =>
      [...memories.values()].filter((m) => m.user_id === options.user_id &&
        (!options.run_id || options.run_id === m.run_id))),
    get: vi.fn<Mem0Provider["get"]>(async (id) => {
      const memory = memories.get(id);
      if (!memory) throw new Error("not found");
      return memory;
    }),
    update: vi.fn<Mem0Provider["update"]>(async (id, text) => {
      const memory = memories.get(id);
      if (!memory) throw new Error("not found");
      memories.set(id, { ...memory, memory: text });
    }),
    delete: vi.fn<Mem0Provider["delete"]>(async (id) => { memories.delete(id); }),
    deleteAll: vi.fn<Mem0Provider["deleteAll"]>(async (userId) => {
      for (const [id, memory] of memories) {
        if (memory.user_id === userId) memories.delete(id);
      }
    }),
    history: vi.fn<Mem0Provider["history"]>(async () => []),
  };
  return { provider, memories };
}

type HookEvent = { prompt?: string; messages: unknown[]; success?: boolean };
type RegisteredTool = Parameters<OpenClawPluginApi["registerTool"]>[0];
type PromptHandler = (
  event: { prompt: string; messages: unknown[] }, ctx: SenderContext,
) => unknown;
type EndHandler = (
  event: { success: boolean; messages: unknown[] }, ctx: SenderContext,
) => unknown;

function setup(config: Record<string, unknown> = {}, registrationMode = "full") {
  const { provider, memories } = createMemoryStore();
  vi.mocked(createProvider).mockReturnValue(provider);
  const hooks = new Map<string, (event: HookEvent, ctx: SenderContext) => unknown>();
  const tools = new Map<string, RegisteredTool>();
  function on(...args:
    | [name: "before_prompt_build", handler: PromptHandler]
    | [name: "agent_end", handler: EndHandler]
  ) {
    const [name, handler] = args;
    if (name === "before_prompt_build") {
      hooks.set(name, (event, ctx) => {
        if (typeof event.prompt !== "string") throw new Error("prompt is required");
        return handler({ prompt: event.prompt, messages: event.messages }, ctx);
      });
    } else {
      hooks.set(name, (event, ctx) => {
        if (typeof event.success !== "boolean") throw new Error("success is required");
        return handler({ success: event.success, messages: event.messages }, ctx);
      });
    }
  }
  const api = {
    pluginConfig: {
      mode: "platform", apiKey: "test-only", userId: "deployment",
      userIdScope: "per-sender", ...config,
    },
    registrationMode,
    logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn() },
    resolvePath: (path: string) => path,
    on,
    registerTool(entry: RegisteredTool, options?: { name?: string }) {
      const name = typeof entry === "function" ? options?.name : entry.name;
      if (!name) throw new Error("tool factory must declare its name");
      tools.set(name, entry);
    },
    registerMemoryCapability: vi.fn(),
    registerCli: vi.fn(),
    registerService: vi.fn(),
  } satisfies OpenClawPluginApi;
  memoryPlugin.register(api);

  return {
    provider, memories, api, tools, hooks,
    async hook(name: string, event: HookEvent, ctx: SenderContext) {
      const handler = hooks.get(name);
      if (!handler) throw new Error(`missing hook: ${name}`);
      return handler(event, ctx);
    },
    tool(name: string, ctx: OpenClawPluginToolContext) {
      const entry = tools.get(name);
      const tool = typeof entry === "function" ? entry(ctx) : entry;
      if (!tool || Array.isArray(tool)) throw new Error(`missing tool: ${name}`);
      return tool;
    },
  };
}

function output(result: unknown): string {
  return JSON.stringify(result);
}

const aliceFact = "Alice prefers detailed TypeScript explanations and always uses pnpm for her projects.";
const bobFact = "Bob prefers concise Python examples and uses pytest to validate his own projects.";

beforeEach(() => { vi.clearAllMocks(); vi.useFakeTimers(); });
afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

describe("sender namespaces", () => {
  it("encodes an unambiguous deployment/agent/channel/account/sender tuple, not a session", () => {
    const uid = senderUserId("deployment", alice);
    expect(JSON.parse(Buffer.from(uid.replace("mem0:sender:v1:", ""), "base64url").toString()))
      .toEqual(["deployment", "assistant", "telegram", "work", "alice"]);
    expect(senderUserId("deployment", { ...alice, sessionKey: "agent:assistant:new-session" })).toBe(uid);
    expect(senderUserId("deployment", { ...alice, agentId: undefined })).toBe(uid);
    const variants = [
      uid,
      senderUserId("deployment", bob),
      senderUserId("deployment", { ...alice, channel: "discord" }),
      senderUserId("deployment", { ...alice, accountId: "personal" }),
      senderUserId("deployment", { ...alice, agentId: "researcher" }),
      senderUserId("deployment:agent:assistant", alice),
      senderUserId("deployment", { ...alice, accountId: "work:alice", senderId: "x" }),
      senderUserId("deployment", { ...alice, accountId: "work", senderId: "alice:x" }),
    ];
    expect(new Set(variants).size).toBe(variants.length);
  });

  it.each(["senderId", "channel", "accountId", "agentId"] as const)(
    "fails closed without %s, including empty identity", (field) => {
      for (const value of [undefined, "", " "]) {
        expect(() => senderUserId("deployment", { ...alice, sessionKey: undefined, [field]: value }))
          .toThrow("trusted sender, channel, account and agent identity");
      }
    },
  );
});

describe.each(["platform", "open-source"])("request-local tools (%s)", (mode) => {
  it("isolates two senders across overlapping all-scope searches and stable sessions", async () => {
    const h = setup({ mode, autoRecall: false, autoCapture: false });
    const a = toolContext(alice);
    const b = toolContext(bob);
    await h.tool("memory_add", a).execute("a", { text: aliceFact, longTerm: false });
    await h.tool("memory_add", b).execute("b", { text: bobFact, longTerm: false });
    const [aliceMemory, bobMemory] = [...h.memories.values()];
    expect(aliceMemory.user_id).not.toBe(bobMemory.user_id);
    expect(aliceMemory.run_id).toBe(alice.sessionKey);
    expect(bobMemory.run_id).toBe(bob.sessionKey);

    const gate = deferred();
    const search = h.provider.search.getMockImplementation()!;
    h.provider.search.mockImplementationOnce(async (...args) => {
      await gate.promise;
      return search(...args);
    });
    const aliceTool = h.tool("memory_search", a);
    const pending = aliceTool.execute("a-search", { query: "preferences", scope: "all" });
    Object.assign(a, b); // Host context reuse cannot retarget an existing tool.
    const bobResult = await h.tool("memory_search", b).execute("b-search", { query: "preferences" });
    gate.release();
    const aliceResult = await pending;
    expect(output(aliceResult)).toContain(aliceFact);
    expect(output(aliceResult)).not.toContain(bobFact);
    expect(output(bobResult)).toContain(bobFact);
    expect(output(bobResult)).not.toContain(aliceFact);
    expect(h.provider.search.mock.calls.at(-1)?.[1]).toMatchObject({
      user_id: aliceMemory.user_id, run_id: alice.sessionKey,
    });

    const freshSession = toolContext({ ...alice, sessionKey: "agent:assistant:new" });
    const list = await h.tool("memory_list", freshSession).execute("list", { scope: "long-term" });
    expect(output(list)).toContain(aliceFact);
    expect(output(list)).not.toContain(bobFact);
  });

  it("binds get/update/delete/query-delete/delete-all and blocks cross-sender IDs", async () => {
    const h = setup({ mode });
    const a = toolContext(alice);
    const b = toolContext(bob);
    await h.tool("memory_add", a).execute("a", { text: aliceFact });
    await h.tool("memory_add", b).execute("b", { text: bobFact });
    for (const name of ["memory_get", "memory_update", "memory_delete"]) {
      const result = await h.tool(name, b).execute("denied", { memoryId: "m1", text: "changed" });
      expect(output(result)).toContain("ownership could not be verified");
      expect(output(result)).not.toContain(aliceFact);
    }
    expect(h.provider.update).not.toHaveBeenCalled();
    expect(h.provider.delete).not.toHaveBeenCalled();
    const owned = await h.tool("memory_get", a).execute("get", { memoryId: "m1" });
    expect(output(owned)).toContain(aliceFact);
    await h.tool("memory_update", a).execute("update", { memoryId: "m1", text: "Alice changed preferences" });
    expect(h.memories.get("m1")?.memory).toBe("Alice changed preferences");
    await h.tool("memory_delete", b).execute("delete", { query: "preferences" });
    expect(h.memories.has("m1")).toBe(true);
    expect(h.memories.has("m2")).toBe(false);
    await h.tool("memory_delete", a).execute("all", { all: true, confirm: true });
    expect(h.memories.size).toBe(0);
  });
});

describe("fail-closed tool surfaces", () => {
  it("blocks every tool with missing identity, even after another sender's hook", async () => {
    const h = setup();
    await h.hook("before_prompt_build", { prompt: "recall preferences", messages: [] }, alice);
    vi.clearAllMocks();
    for (const name of h.tools.keys()) {
      const result = await h.tool(name, toolContext({ ...alice, senderId: undefined })).execute("missing", {
        query: "preferences", text: aliceFact, memoryId: "foreign", event_id: "foreign",
      });
      expect(output(result)).toContain("trusted sender, channel, account and agent identity");
      expect(result.isError).toBe(true);
    }
    for (const operation of Object.values(h.provider)) expect(operation).not.toHaveBeenCalled();
  });

  it("removes namespace parameters from schemas and rejects forged overrides and metadata", async () => {
    const h = setup();
    for (const name of h.tools.keys()) {
      const tool = h.tool(name, toolContext(alice));
      expect(tool.parameters).toHaveProperty("properties");
      expect(tool.parameters).not.toHaveProperty("properties.userId");
      expect(tool.parameters).not.toHaveProperty("properties.agentId");
      for (const override of [{ userId: "deployment" }, { agentId: "researcher" }, { userId: "" }]) {
        const result = await tool.execute("override", { text: aliceFact, query: "preferences", ...override });
        expect(output(result)).toContain("overrides are not allowed");
      }
    }
    for (const key of ["user_id", "userId", "agent_id", "agentId", "run_id", "runId"]) {
      const result = await h.tool("memory_add", toolContext(alice)).execute("metadata", {
        text: aliceFact, metadata: { [key]: "foreign" },
      });
      expect(output(result)).toContain("identity fields are not allowed");
    }
    for (const operation of Object.values(h.provider)) expect(operation).not.toHaveBeenCalled();
  });

  it("blocks unscoped event APIs, missing session scope and unverifiable memory ownership", async () => {
    const h = setup();
    for (const name of ["memory_event_list", "memory_event_status"]) {
      expect(output(await h.tool(name, toolContext(alice)).execute("event", { event_id: "any" })))
        .toContain("event API is not sender-scoped");
    }
    const noSession = toolContext({ ...alice, sessionKey: undefined });
    expect(output(await h.tool("memory_add", noSession).execute("session", { text: aliceFact, longTerm: false })))
      .toContain("requires a request sessionKey");
    h.memories.set("unknown-owner", { id: "unknown-owner", memory: "must not be disclosed" });
    const result = await h.tool("memory_get", toolContext(alice)).execute("get", { memoryId: "unknown-owner" });
    expect(output(result)).toContain("ownership could not be verified");
    expect(output(result)).not.toContain("must not be disclosed");
  });
});

describe.each([undefined, "always", "smart", "manual"] as const)("hook isolation (%s)", (strategy) => {
  function config() {
    return strategy ? { skills: { recall: { strategy }, triage: { enabled: true } } } : {};
  }

  it("uses the same sender scope for hooks and tools through async interleaving", async () => {
    const h = setup(config());
    await h.tool("memory_add", toolContext(alice)).execute("a", { text: aliceFact });
    await h.tool("memory_add", toolContext(bob)).execute("b", { text: bobFact });
    const uid = h.provider.add.mock.calls[0][1].user_id;
    const gate = deferred();
    const search = h.provider.search.getMockImplementation()!;
    h.provider.search.mockImplementationOnce(async (...args) => {
      await gate.promise;
      return search(...args);
    });
    const a = h.hook("before_prompt_build", { prompt: "recall preferences", messages: [] }, alice);
    const b = await h.hook("before_prompt_build", { prompt: "recall preferences", messages: [] }, bob);
    gate.release();
    const result = await a;
    if (strategy === "manual") {
      expect(h.provider.search).not.toHaveBeenCalled();
    } else {
      expect(output(result)).toContain(aliceFact);
      expect(output(result)).not.toContain(bobFact);
      expect(output(b)).toContain(bobFact);
      expect(output(b)).not.toContain(aliceFact);
      const senderSearches = h.provider.search.mock.calls.filter(([, options]) => options.user_id === uid);
      expect(senderSearches.length).toBeGreaterThan(0);
      expect(h.provider.search.mock.calls[0][1].user_id).toBe(uid);
      if (strategy === "always") {
        expect(senderSearches.at(-1)?.[1].run_id).toBe(alice.sessionKey);
      }
    }
  });

  it("never recalls/captures from old hooks, missing account or non-user triggers", async () => {
    const h = setup(config());
    const oldHook = { agentId: "assistant", sessionKey: alice.sessionKey, channelId: "chat", trigger: "user" };
    for (const context of [
      oldHook, { ...alice, accountId: undefined },
      { ...alice, trigger: "automation" }, { ...alice, trigger: "subagent" },
    ]) {
      const result = await h.hook("before_prompt_build", { prompt: "recall preferences", messages: [] }, context);
      expect(result).toBeUndefined();
      await h.hook("agent_end", { success: true, messages: [{ role: "user", content: aliceFact }] }, context);
    }
    for (const operation of Object.values(h.provider)) expect(operation).not.toHaveBeenCalled();
    expect(h.api.logger.warn).toHaveBeenCalledWith(expect.stringContaining("v2026.4.24 hooks"));
  });
});

it("captures only the latest user turn and preserves sender scope during overlapping writes", async () => {
  const h = setup({ autoRecall: false });
  const gate = deferred();
  const add = h.provider.add.getMockImplementation()!;
  h.provider.add.mockImplementationOnce(async (...args) => {
    await gate.promise;
    return add(...args);
  });
  await h.hook("agent_end", { success: true, messages: [
    { role: "user", content: bobFact },
    { role: "assistant", content: "## What I Built\nAn older summary about Bob" },
    { role: "user", content: aliceFact },
  ] }, alice);
  await h.hook("agent_end", {
    success: true, messages: [{ role: "user", content: bobFact }],
  }, bob);
  gate.release();
  await Promise.resolve();
  await Promise.resolve();
  expect(h.memories.size).toBe(2);
  expect(h.provider.add.mock.calls[0][0].map((m) => m.content).join("\n")).not.toContain(bobFact);
  const a = await h.tool("memory_search", toolContext(alice)).execute("a", { query: "preferences" });
  const b = await h.tool("memory_search", toolContext(bob)).execute("b", { query: "preferences" });
  expect(output(a)).toContain(aliceFact);
  expect(output(a)).not.toContain(bobFact);
  expect(output(b)).toContain(bobFact);
  expect(output(b)).not.toContain(aliceFact);
});

it("keeps senders isolated even when the host reuses a session key", async () => {
  const h = setup();
  const a = toolContext(alice);
  const b = toolContext({ ...bob, sessionKey: alice.sessionKey });
  await h.tool("memory_add", a).execute("a", { text: aliceFact, longTerm: false });
  await h.tool("memory_add", b).execute("b", { text: bobFact, longTerm: false });
  const aResult = await h.tool("memory_list", a).execute("a-list", { scope: "session" });
  const bResult = await h.tool("memory_list", b).execute("b-list", { scope: "session" });
  expect(output(aResult)).toContain(aliceFact);
  expect(output(aResult)).not.toContain(bobFact);
  expect(output(bResult)).toContain(bobFact);
  expect(output(bResult)).not.toContain(aliceFact);
});

it("keeps subagent writes disabled without retargeting recall to another agent", async () => {
  const h = setup();
  await h.tool("memory_add", toolContext(alice)).execute("a", { text: aliceFact });
  const subagent = { ...alice, sessionKey: "agent:assistant:subagent:ephemeral" };
  const recalled = await h.hook("before_prompt_build", { prompt: "recall preferences", messages: [] }, subagent);
  expect(output(recalled)).toContain(aliceFact);
  h.provider.add.mockClear();
  for (const name of ["memory_add", "memory_update", "memory_delete"]) {
    const result = await h.tool(name, toolContext(subagent)).execute("subagent", {
      text: aliceFact, memoryId: "m1", all: true, confirm: true,
    });
    expect(output(result)).toContain("subagent");
  }
  expect(h.provider.add).not.toHaveBeenCalled();
  expect(h.provider.update).not.toHaveBeenCalled();
  expect(h.provider.delete).not.toHaveBeenCalled();
  expect(h.provider.deleteAll).not.toHaveBeenCalled();
});

describe("registration and static compatibility", () => {
  it.each(["full", "discovery", "tool-discovery", "setup-only", "setup-runtime"])(
    "does not expose shared capabilities in %s", (mode) => {
      const h = setup({}, mode);
      expect(h.api.registerMemoryCapability).not.toHaveBeenCalled();
      expect(h.tools.size).toBe(8);
      expect([...h.tools.values()].every((tool) => typeof tool === "function")).toBe(true);
      for (const operation of Object.values(h.provider)) expect(operation).not.toHaveBeenCalled();
    },
  );

  it("keeps metadata and unconfigured registration free of memory surfaces", () => {
    for (const h of [setup({}, "cli-metadata"), setup({ apiKey: "" })]) {
      expect(h.tools.size).toBe(0);
      expect(h.hooks.size).toBe(0);
      expect(h.api.registerMemoryCapability).not.toHaveBeenCalled();
      expect(h.api.registerCli).toHaveBeenCalledOnce();
    }
  });

  it("preserves default per-agent namespaces, explicit overrides and capabilities", async () => {
    const h = setup({ userIdScope: undefined });
    expect(h.api.registerMemoryCapability).toHaveBeenCalledOnce();
    expect([...h.tools.values()].every((tool) => typeof tool !== "function")).toBe(true);
    await h.hook("before_prompt_build", { prompt: "recall preferences", messages: [] }, {
      sessionKey: "agent:researcher:one",
    });
    await h.tool("memory_add", {}).execute("default", { text: aliceFact });
    await h.tool("memory_add", {}).execute("user", { text: bobFact, userId: "explicit" });
    await h.tool("memory_add", {}).execute("agent", { text: bobFact, userId: "explicit", agentId: "beta" });
    expect(h.provider.add.mock.calls.map(([, opts]) => opts.user_id))
      .toEqual(["deployment:agent:researcher", "explicit", "deployment:agent:beta"]);
  });

  it("refuses direct public-artifact export even with a supplied namespace", async () => {
    const { provider } = createMemoryStore();
    const artifacts = createPublicArtifactsProvider({
      provider, cfg: mem0ConfigSchema.parse({ userIdScope: "per-sender" }),
      effectiveUserId: () => "deployment",
    });
    await expect(artifacts.listArtifacts({ userId: "deployment" })).rejects.toThrow("public artifacts");
    expect(provider.getAll).not.toHaveBeenCalled();
  });
});
