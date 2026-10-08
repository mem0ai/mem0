import type {
  MemoryCompactionCompletedContext,
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

function compactionContext(
  input?: Parameters<typeof memoryContext>[0],
): MemoryCompactionCompletedContext {
  return memoryContext({
    ...input,
    turn: input?.turn === undefined ? null : input.turn,
  }) as unknown as MemoryCompactionCompletedContext;
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

function requireCapture(
  provider: ReturnType<typeof mem0Provider>,
): NonNullable<NonNullable<typeof provider.capture>["turn.completed"]> {
  const capture = provider.capture?.["turn.completed"];
  if (!capture) {
    throw new Error("expected turn.completed");
  }
  return capture;
}

describe("mem0Provider", () => {
  it("recalls memories for the locked scope on turn start", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "User likes tea" }]);
    const provider = mem0Provider({ store });
    const result = await provider.recall["turn.started"](
      startedContext({
        turnInput: [{ role: "user", content: "What do I drink?" }],
      }),
    );

    expect(store.searched).toEqual([
      {
        query: "What do I drink?",
        userId: "scope_abc",
        topK: 5,
        threshold: 0.1,
        rerank: false,
      },
    ]);
    expect(result).toEqual({
      messages: [{ id: "mem_1", content: "User likes tea" }],
    });
  });

  it("forwards recall search options", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "User likes tea" }]);
    const provider = mem0Provider({
      store,
      topK: 3,
      threshold: 0.5,
      rerank: true,
    });
    await provider.recall["turn.started"](
      startedContext({
        turnInput: [{ role: "user", content: "tea" }],
      }),
    );
    expect(store.searched[0]).toMatchObject({
      topK: 3,
      threshold: 0.5,
      rerank: true,
    });
  });

  it("skips search when autoSearch is disabled", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "User likes tea" }]);
    const provider = mem0Provider({ store, autoSearch: { enabled: false } });
    await expect(
      provider.recall["turn.started"](startedContext()),
    ).resolves.toBeNull();
    expect(store.searched).toEqual([]);
  });

  it("recalls after compaction when turn is null", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "User likes tea" }]);
    const provider = mem0Provider({ store });
    const recallAfterCompaction = provider.recall["compaction.completed"];
    if (!recallAfterCompaction) {
      throw new Error("expected compaction.completed");
    }
    const result = await recallAfterCompaction(
      compactionContext({
        messages: [
          { role: "user", content: "What do I drink?" },
          { role: "assistant", content: "tea" },
        ],
      }),
    );

    expect(store.searched).toEqual([
      {
        query: "What do I drink?",
        userId: "scope_abc",
        topK: 5,
        threshold: 0.1,
        rerank: false,
      },
    ]);
    expect(result).toEqual({
      messages: [{ id: "mem_1", content: "User likes tea" }],
    });
  });

  it("fails the turn when search throws", async () => {
    const store = createFakeStore();
    store.search = async () => {
      throw new Error("mem0 down");
    };
    const provider = mem0Provider({ store });
    const error = vi.spyOn(console, "error").mockImplementation(() => {});

    try {
      await expect(
        provider.recall["turn.started"](startedContext()),
      ).rejects.toThrow("mem0 down");
    } finally {
      error.mockRestore();
    }
  });

  it("rethrows when recall is aborted", async () => {
    const store = createFakeStore();
    store.search = async () => {
      throw new Error("cancelled");
    };
    const provider = mem0Provider({ store });

    await expect(
      provider.recall["turn.started"](startedContext({ aborted: true })),
    ).rejects.toThrow("cancelled");
  });

  it("captures a completed turn once per operation id", async () => {
    const store = createFakeStore();
    const provider = mem0Provider({ store });
    const capture = provider.capture?.["turn.completed"];
    expect(capture).toBeTypeOf("function");

    const context = completedContext({ operationId: "op_replay" });
    await capture!(context);
    await capture!(context);

    expect(store.added).toHaveLength(1);
    expect(store.added[0]).toMatchObject({
      userId: "scope_abc",
      infer: true,
      metadata: {
        source: "eve",
        operation_id: "op_replay",
        session_id: "sess_1",
        slot: "mem0",
      },
    });
  });

  it("does not recapture after process restart when operation metadata exists", async () => {
    const store = createFakeStore();
    const first = requireCapture(mem0Provider({ store }));
    await first(completedContext({ operationId: "op_replay" }));

    const restarted = requireCapture(mem0Provider({ store }));
    await restarted(completedContext({ operationId: "op_replay" }));

    expect(store.added).toHaveLength(1);
  });

  it("surfaces capture store failures", async () => {
    const store = createFakeStore();
    store.add = async () => {
      throw new Error("write failed");
    };

    await expect(
      requireCapture(mem0Provider({ store }))(completedContext()),
    ).rejects.toThrow("write failed");
  });

  it("omits capture when it is disabled", () => {
    const provider = mem0Provider({
      store: createFakeStore(),
      capture: { enabled: false },
    });
    expect(provider.capture).toBeUndefined();
  });

  it("binds tools to the locked scope", async () => {
    const store = createFakeStore([{ id: "mem_1", memory: "likes tea" }]);
    const provider = mem0Provider({
      store,
      topK: 3,
      threshold: 0.4,
      rerank: true,
      infer: false,
    });
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
    expect(remember).toEqual({ status: "saved" });
    expect(forget).toEqual({ deleted: true });
    expect(store.searched[0]).toMatchObject({
      userId: "scope_abc",
      topK: 3,
      threshold: 0.4,
      rerank: true,
    });
    expect(store.added[0]).toMatchObject({
      userId: "scope_abc",
      infer: false,
      metadata: { source: "eve-tool" },
      messages: [{ role: "user", content: "Allergic to peanuts" }],
    });
    expect(store.deleted).toEqual(["mem_1"]);
  });

  it("reports remember as queued when the write is still pending", async () => {
    const store = createFakeStore([], { pendingWrites: true });
    const provider = mem0Provider({ store, infer: true });
    const tools = await provider.tools!(toolsContext());
    const rememberTool = tools?.remember;
    if (!rememberTool) {
      throw new Error("expected remember tool");
    }
    const remember = await runTool(rememberTool, { text: "Allergic to peanuts" });
    expect(remember).toEqual({ status: "queued", eventId: "evt_1" });
  });

  it("refuses to forget a memory from another scope", async () => {
    const store = createFakeStore([
      { id: "mem_other", memory: "secret", userId: "scope_other" },
    ]);
    const provider = mem0Provider({ store });
    const tools = await provider.tools!(toolsContext());
    const forgetTool = tools?.forget;
    if (!forgetTool) {
      throw new Error("expected forget tool");
    }

    await expect(runTool(forgetTool, { id: "mem_other" })).rejects.toThrow(
      /Memory not found/,
    );
    expect(store.deleted).toEqual([]);
  });

  it("surfaces tool store failures", async () => {
    const store = createFakeStore();
    store.add = async () => {
      throw new Error("add failed");
    };
    const provider = mem0Provider({ store });
    const tools = await provider.tools!(toolsContext());
    const rememberTool = tools?.remember;
    if (!rememberTool) {
      throw new Error("expected remember tool");
    }

    await expect(
      runTool(rememberTool, { text: "remember this" }),
    ).rejects.toThrow("add failed");
  });
});
