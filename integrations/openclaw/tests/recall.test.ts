import { describe, it, expect, vi } from "vitest";
import { recall } from "../recall.ts";
import type { Mem0Provider, SearchOptions } from "../types.ts";

function mockProvider(): { provider: Mem0Provider; calls: SearchOptions[] } {
  const calls: SearchOptions[] = [];
  const provider = {
    search: vi.fn(async (_query: string, opts: SearchOptions) => {
      calls.push(opts);
      return [];
    }),
  } as unknown as Mem0Provider;
  return { provider, calls };
}

describe("recall session search top_k", () => {
  it("uses the default maxMemories (15) instead of a hardcoded 5", async () => {
    const { provider, calls } = mockProvider();
    await recall(provider, "what did we decide?", "user1", {}, "sess-1");

    expect(calls).toHaveLength(2);
    expect(calls[0].top_k).toBe(30); // long-term: maxMemories * 2 over-fetch
    expect(calls[1].top_k).toBe(15); // session: maxMemories
  });

  it("honors recall.maxMemories from config", async () => {
    const { provider, calls } = mockProvider();
    await recall(
      provider,
      "what did we decide?",
      "user1",
      { recall: { maxMemories: 40 } },
      "sess-1",
    );

    expect(calls[0].top_k).toBe(80);
    expect(calls[1].top_k).toBe(40);
  });

  it("skips session search without a sessionId", async () => {
    const { provider, calls } = mockProvider();
    await recall(provider, "what did we decide?", "user1", {});

    expect(calls).toHaveLength(1);
  });
});
