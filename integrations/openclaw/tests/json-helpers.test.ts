import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { jsonOut, jsonErr, redactSecrets } from "../cli/json-helpers.ts";

describe("jsonOut", () => {
  let writeSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { writeSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true); });
  afterEach(() => { writeSpy.mockRestore(); });

  it("returns false and prints nothing when json is falsy", () => {
    expect(jsonOut({}, { ok: true })).toBe(false);
    expect(writeSpy).not.toHaveBeenCalled();
  });

  it("returns true and prints JSON to stdout when json is true", () => {
    expect(jsonOut({ json: true }, { ok: true, count: 3 })).toBe(true);
    expect(writeSpy).toHaveBeenCalledOnce();
    const parsed = JSON.parse(writeSpy.mock.calls[0][0] as string);
    expect(parsed).toEqual({ ok: true, count: 3 });
  });
});

describe("jsonErr", () => {
  let writeSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => { writeSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true); });
  afterEach(() => { writeSpy.mockRestore(); });

  it("returns false when json is falsy", () => {
    expect(jsonErr({}, "bad")).toBe(false);
  });

  it("returns true and prints error JSON to stdout", () => {
    expect(jsonErr({ json: true }, "Something broke")).toBe(true);
    const parsed = JSON.parse(writeSpy.mock.calls[0][0] as string);
    expect(parsed).toEqual({ ok: false, error: "Something broke" });
  });
});

describe("redactSecrets", () => {
  it("redacts string values for known secret keys", () => {
    const input = { apiKey: "m0-abcdefghijklmnop", name: "test" };
    const result = redactSecrets(input, new Set(["apiKey"]));
    expect(result.apiKey).toBe("m0-a...mnop");
    expect(result.name).toBe("test");
  });

  it("handles short keys", () => {
    const result = redactSecrets({ apiKey: "ab" }, new Set(["apiKey"]));
    expect(result.apiKey).toBe("ab***");
  });

  it("skips non-string values", () => {
    const result = redactSecrets({ count: 5 }, new Set(["count"]));
    expect(result.count).toBe(5);
  });
});
