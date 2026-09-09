import type {
  MemoryToolsContext,
  MemoryTurnCompletedContext,
  MemoryTurnStartedContext,
} from "eve/memory";
import { describe, expect, it, vi } from "vitest";
import { mem0Provider } from "../src/provider.js";
import { createFakeStore, memoryContext } from "./helpers.js";

function startedContext(
  input?: Parameters<typeof memoryContext>[0],
): MemoryTurnStartedContext {
  return memoryContext(input) as unknown as MemoryTurnStartedContext;
}

function completedContext(
  input?: Parameters<typeof memoryContext>[0],
): MemoryTurnCompletedContext {
  return memoryContext(input) as unknown as MemoryTurnCompletedContext;
}

function toolsContext(
  input?: Parameters<typeof memoryContext>[0],
): MemoryToolsContext {
  return memoryContext(input) as unknown as MemoryToolsContext;
}

async function runTool(
  tool: { execute: (input: never, context: never) => unknown },
  input: object,
): Promise<unknown> {
  return tool.execute(input as never, {} as never);
}

describe("mem0Provider", () => {
  it("recalls memories for the locked scope on turn start", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "User likes tea" }]);
    const provider = mem0Provider({ apiKey: "m0-test", store });
    const result = await provider.recall["turn.started"](
      startedContext({
        turnInput: [{ role: "user", content: "What do I drink?" }],
      }),
    );

    expect(store.searched).toEqual([
      { query: "What do I drink?", userId: "scope_abc" },
    ]);
    expect(result).toEqual({
      messages: [{ id: "mem_1", content: "User likes tea" }],
    });
  });

  it("does not fail the turn when search throws", async () => {
    const store = createFakeStore();
    store.search = async () => {
      throw new Error("mem0 down");
    };
    const provider = mem0Provider({ apiKey: "m0-test", store });
    const error = vi.spyOn(console, "error").mockImplementation(() => {});

    await expect(
      provider.recall["turn.started"](startedContext()),
    ).resolves.toBeNull();

    error.mockRestore();
  });

  it("captures a completed turn once per operation id", async () => {
    const store = createFakeStore();
    const provider = mem0Provider({ apiKey: "m0-test", store });
    const capture = provider.capture?.["turn.completed"];
    expect(capture).toBeTypeOf("function");

    const context = completedContext({ operationId: "op_replay" });
    await capture!(context);
    await capture!(context);

    expect(store.added).toHaveLength(1);
    expect(store.added[0]?.userId).toBe("scope_abc");
  });

  it("omits capture when it is disabled", () => {
    const provider = mem0Provider({
      apiKey: "m0-test",
      store: createFakeStore(),
      capture: { enabled: false },
    });
    expect(provider.capture).toBeUndefined();
  });

  it("binds tools to the locked scope", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "likes tea" }]);
    const provider = mem0Provider({ apiKey: "m0-test", store });
    const tools = await provider.tools!(toolsContext());
    if (!tools) {
      throw new Error("expected tools");
    }

    const searchTool = tools.search;
    const rememberTool = tools.remember;
    const forgetTool = tools.forget;
    if (!searchTool || !rememberTool || !forgetTool) {
      throw new Error("expected search, remember, and forget tools");
    }

    const search = await runTool(searchTool, { query: "drinks" });
    const remember = await runTool(rememberTool, {
      text: "Allergic to peanuts",
    });
    const forget = await runTool(forgetTool, { id: "mem_1" });

    expect(search).toEqual({
      memories: [{ id: "mem_1", memory: "likes tea" }],
    });
    expect(remember).toEqual({ saved: true });
    expect(forget).toEqual({ deleted: true });
    expect(store.searched[0]?.userId).toBe("scope_abc");
    expect(store.added[0]?.userId).toBe("scope_abc");
    expect(store.deleted).toEqual(["mem_1"]);
  });
});
