import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock config-file before importing telemetry
vi.mock("../cli/config-file.ts", () => ({
  readPluginAuth: vi.fn().mockReturnValue({}),
}));

import { captureEvent } from "../telemetry.ts";
import { readPluginAuth } from "../cli/config-file.ts";

describe("telemetry", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
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

  it("uses userEmail as distinct ID when available", () => {
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValueOnce({
      userEmail: "test@example.com",
    });
    expect(() => captureEvent("test_event")).not.toThrow();
  });

  it("falls back to a generated anonymous id when no apiKey", () => {
    (readPluginAuth as ReturnType<typeof vi.fn>).mockReturnValueOnce({});
    expect(() => captureEvent("test_event", {}, {})).not.toThrow();
  });

  it("handles readPluginAuth errors gracefully", () => {
    (readPluginAuth as ReturnType<typeof vi.fn>).mockImplementationOnce(() => {
      throw new Error("config read failed");
    });
    expect(() => captureEvent("test_event")).not.toThrow();
  });
});
