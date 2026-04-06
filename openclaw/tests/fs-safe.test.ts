import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { bootstrapTelemetryFlag } from "../fs-safe.ts";

describe("bootstrapTelemetryFlag", () => {
  const originalEnv = process.env.MEM0_TELEMETRY;

  beforeEach(() => {
    delete (globalThis as any).__mem0_telemetry_override;
    delete process.env.MEM0_TELEMETRY;
  });

  afterEach(() => {
    delete (globalThis as any).__mem0_telemetry_override;
    if (originalEnv !== undefined) {
      process.env.MEM0_TELEMETRY = originalEnv;
    } else {
      delete process.env.MEM0_TELEMETRY;
    }
  });

  it("sets globalThis override when MEM0_TELEMETRY is set", () => {
    process.env.MEM0_TELEMETRY = "false";
    bootstrapTelemetryFlag();
    expect((globalThis as any).__mem0_telemetry_override).toBe("false");
  });

  it("does not set globalThis override when MEM0_TELEMETRY is unset", () => {
    bootstrapTelemetryFlag();
    expect((globalThis as any).__mem0_telemetry_override).toBeUndefined();
  });

  it("passes through truthy values", () => {
    process.env.MEM0_TELEMETRY = "true";
    bootstrapTelemetryFlag();
    expect((globalThis as any).__mem0_telemetry_override).toBe("true");
  });
});
