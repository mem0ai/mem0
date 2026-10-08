import { describe, expect, it, vi } from "vitest";

import { recall } from "../recall.ts";

function createProvider() {
  return {
    search: vi.fn().mockResolvedValue([
      {
        id: "m1",
        memory: "User prefers detailed technical explanations",
        score: 0.9,
        metadata: { category: "preference" },
      },
    ]),
  };
}

describe("recall", () => {
  it("requests reranking by default for skills recall", async () => {
    const provider = createProvider();

    await recall(provider as any, "technical explanation style", "alice", {
      recall: { maxMemories: 5 },
    });

    expect(provider.search).toHaveBeenCalledWith(
      "technical explanation style",
      expect.objectContaining({
        user_id: "alice",
        top_k: 10,
        rerank: true,
        source: "OPENCLAW",
      }),
    );
  });

  it("honors explicit rerank opt-out", async () => {
    const provider = createProvider();

    await recall(provider as any, "technical explanation style", "alice", {
      recall: { maxMemories: 5, rerank: false },
    });

    expect(provider.search).toHaveBeenCalledWith(
      "technical explanation style",
      expect.objectContaining({
        rerank: false,
      }),
    );
  });
});
