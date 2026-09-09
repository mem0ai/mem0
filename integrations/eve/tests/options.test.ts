import { describe, expect, it } from "vitest";
import { resolveOptions } from "../src/options.js";
import { createFakeStore } from "./helpers.js";

describe("resolveOptions", () => {
  it("applies defaults", () => {
    expect(resolveOptions({ apiKey: "m0-test" })).toMatchObject({
      host: "https://api.mem0.ai",
      topK: 5,
      threshold: 0.1,
      rerank: false,
      infer: true,
      autoSearch: { enabled: true },
      capture: { enabled: true },
    });
  });

  it("rejects an empty api key", () => {
    expect(() => resolveOptions({ apiKey: "   " })).toThrow(/empty/);
  });

  it("rejects an invalid topK", () => {
    expect(() => resolveOptions({ apiKey: "m0-test", topK: 0 })).toThrow(/topK/);
  });

  it("keeps an injected store", () => {
    const store = createFakeStore();
    expect(resolveOptions({ apiKey: "m0-test", store }).store).toBe(store);
  });
});
