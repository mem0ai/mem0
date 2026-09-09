import { describe, expect, it } from "vitest";
import { resolveOptions } from "../src/options.js";
import { createFakeStore } from "./helpers.js";

describe("resolveOptions", () => {
  it("applies defaults", () => {
    expect(resolveOptions({ apiKey: "m0-test" })).toEqual({
      apiKey: "m0-test",
      host: "https://api.mem0.ai",
      topK: 5,
      threshold: 0.1,
      rerank: false,
      infer: true,
      autoSearch: { enabled: true },
      capture: { enabled: true },
      metadata: {},
    });
  });

  it("rejects an empty api key", () => {
    expect(() => resolveOptions({ apiKey: "   " })).toThrow(/empty/);
  });

  it("requires an api key when no store is provided", () => {
    expect(() => resolveOptions({} as never)).toThrow(/apiKey is required/);
  });

  it("allows a store without an api key", () => {
    const store = createFakeStore();
    expect(resolveOptions({ store }).store).toBe(store);
  });

  it("does not invoke a function api key at resolve time", () => {
    let calls = 0;
    const apiKey = () => {
      calls += 1;
      return "";
    };
    expect(() => resolveOptions({ apiKey })).not.toThrow();
    expect(calls).toBe(0);
  });

  it("rejects an invalid topK", () => {
    expect(() => resolveOptions({ apiKey: "m0-test", topK: 0 })).toThrow(/topK/);
    expect(() => resolveOptions({ apiKey: "m0-test", topK: 101 })).toThrow(/topK/);
    expect(() => resolveOptions({ apiKey: "m0-test", topK: 1.5 })).toThrow(/topK/);
  });

  it("rejects an invalid threshold", () => {
    expect(() => resolveOptions({ apiKey: "m0-test", threshold: -0.1 })).toThrow(
      /threshold/,
    );
    expect(() => resolveOptions({ apiKey: "m0-test", threshold: 1.1 })).toThrow(
      /threshold/,
    );
    expect(() => resolveOptions({ apiKey: "m0-test", threshold: Number.NaN })).toThrow(
      /threshold/,
    );
  });

  it("rejects a non-http host", () => {
    expect(() => resolveOptions({ apiKey: "m0-test", host: "localhost" })).toThrow(
      /host/,
    );
    expect(() => resolveOptions({ apiKey: "m0-test", host: "ftp://mem0.ai" })).toThrow(
      /host/,
    );
  });

  it("treats a blank host as the default", () => {
    expect(resolveOptions({ apiKey: "m0-test", host: "   " }).host).toBe(
      "https://api.mem0.ai",
    );
  });

  it("keeps an injected store", () => {
    const store = createFakeStore();
    expect(resolveOptions({ apiKey: "m0-test", store }).store).toBe(store);
  });
});
