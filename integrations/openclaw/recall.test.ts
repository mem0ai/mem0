import { describe, expect, it, vi } from "vitest";

import { recall } from "./recall.ts";
import type { Mem0Provider, SearchOptions } from "./types.ts";

describe("recall", () => {
  it("uses configured over-fetch limit for session recall search", async () => {
    const search = vi.fn(async (_query: string, _options: SearchOptions) => []);
    const provider = { search } as unknown as Mem0Provider;

    await recall(
      provider,
      "remember the current project context",
      "user-1",
      { recall: { maxMemories: 8 } },
      "session-1",
    );

    expect(search).toHaveBeenCalledTimes(2);
    expect(search.mock.calls[0]?.[1]).toMatchObject({
      user_id: "user-1",
      source: "OPENCLAW",
      top_k: 16,
    });
    expect(search.mock.calls[1]?.[1]).toMatchObject({
      user_id: "user-1",
      run_id: "session-1",
      source: "OPENCLAW",
      top_k: 16,
    });
  });
});
