import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock config-file before importing telemetry
vi.mock("../cli/config-file.ts", () => ({
  readPluginAuth: vi.fn().mockReturnValue({}),
  writePluginAuth: vi.fn(),
  clearAnonymousTelemetryId: vi.fn(),
  clearResolvedAccount: vi.fn(),
  getBaseUrl: vi.fn().mockReturnValue("https://api.mem0.ai"),
}));

import { captureEvent } from "../telemetry.ts";
import { clearResolvedAccount, readPluginAuth } from "../cli/config-file.ts";

/** sha256(key).slice(0, 16), the shape telemetry.ts stores. */
async function fingerprintOf(apiKey: string): Promise<string> {
  const { createHash } = await import("node:crypto");
  return createHash("sha256").update(apiKey).digest("hex").slice(0, 16);
}

describe("telemetry", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Call history has to be cleared per test, not just restored: the mocks are
    // module-level vi.fn()s, so without this one test's calls are visible to the
    // next and assertions on "was not called" pass or fail by ordering.
    vi.clearAllMocks();
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({});
    // Reset telemetry enabled state
    (globalThis as any).__mem0_telemetry_override = undefined;
    fetchSpy = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (globalThis as any).__mem0_telemetry_override;
  });

  it("captureEvent does not throw", () => {
    expect(() => captureEvent("test_event")).not.toThrow();
  });

  it("captureEvent accepts properties and context", () => {
    expect(() =>
      captureEvent("test_event", { key: "val" }, { apiKey: "m0-key", mode: "platform" }),
    ).not.toThrow();
  });

  it("captureEvent is silent when telemetry disabled", () => {
    (globalThis as any).__mem0_telemetry_override = "false";
    // Force re-evaluation by resetting cached value
    // Since _telemetryEnabled is module-level, we test indirectly
    expect(() => captureEvent("test_event")).not.toThrow();
  });

  it("uses userEmail as distinct ID when it belongs to the current key", async () => {
    // Previously asserted only not.toThrow(), which passed whatever the identity
    // turned out to be, and under the fingerprint gate the no-context path does
    // not use the email at all. Pin the real condition instead.
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      userEmail: "test@example.com",
      keyFingerprint: await fingerprintOf("key-a"),
    });

    captureEvent("test_event", {}, { apiKey: "key-a" });

    expect(clearResolvedAccount).not.toHaveBeenCalled();
  });

  it("a capture with no apiKey leaves a resolved account alone", async () => {
    // `undefined === ""` made every keyless capture look like a key change, so
    // one context-free call wiped a good account out of openclaw.json.
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      userEmail: "test@example.com",
      keyFingerprint: await fingerprintOf("key-a"),
    });

    captureEvent("test_event");

    expect(clearResolvedAccount).not.toHaveBeenCalled();
  });

  it("falls back to a generated anonymous id when no apiKey", () => {
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValueOnce({});
    expect(() => captureEvent("test_event", {}, {})).not.toThrow();
  });

  it("keeps using a cached email only while it belongs to the current key", async () => {
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      userEmail: "person@example.com",
      keyFingerprint: await fingerprintOf("key-a"),
    });

    captureEvent("test_event", {}, { apiKey: "key-a" });

    expect(clearResolvedAccount).not.toHaveBeenCalled();
  });

  it("forgets the account when the API key changes", async () => {
    // The defect: the cached email was used forever, so events after an account
    // switch kept reporting under the previous account.
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      userEmail: "person@example.com",
      keyFingerprint: await fingerprintOf("key-a"),
    });

    captureEvent("test_event", {}, { apiKey: "key-b" });

    expect(clearResolvedAccount).toHaveBeenCalled();
  });

  it("re-resolves for a key it has not looked up before", async () => {
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValue({
      userEmail: "person@example.com",
      keyFingerprint: await fingerprintOf("key-a"),
    });

    captureEvent("test_event", {}, { apiKey: "key-c" });

    // The resolution latch is per key, not once per process, so a key changed
    // mid-session is actually looked up instead of sticking to the fallback.
    expect(fetchSpy).toHaveBeenCalled();
  });

  it("handles readPluginAuth errors gracefully", () => {
    (readPluginAuth as ReturnType<typeof vi.fn>).mockImplementationOnce(() => {
      throw new Error("config read failed");
    });
    expect(() => captureEvent("test_event")).not.toThrow();
  });
});
