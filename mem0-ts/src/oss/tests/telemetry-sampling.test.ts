/// <reference types="jest" />
/**
 * Telemetry sampling — unit tests.
 *
 * Sampling lives inside captureClientEvent in src/utils/telemetry.ts. It uses
 * Math.random() compared against MEM0_TELEMETRY_SAMPLE_RATE (default 0.1) to
 * drop hot-path events; lifecycle events ('init', 'reset') always fire.
 *
 * These tests target captureClientEvent directly. Existing OSS tests that mock
 * captureClientEvent (vector-stores-compat, dimension-autodetect, config-manager)
 * are unaffected because the function signature and contract are unchanged.
 */

import type { TelemetryInstance } from "../src/utils/telemetry.types";

// Helper to make a fake TelemetryInstance.
function makeInstance(
  overrides: Partial<TelemetryInstance> = {},
): TelemetryInstance {
  return {
    telemetryId: "test-id",
    constructor: { name: "Memory" },
    host: "https://test.example.com",
    ...overrides,
  };
}

describe("telemetry sampling", () => {
  let originalFetch: typeof global.fetch;
  let fetchMock: jest.Mock;
  let randomSpy: jest.SpyInstance;

  beforeEach(() => {
    originalFetch = global.fetch;
    fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      text: jest.fn().mockResolvedValue(""),
    });
    global.fetch = fetchMock as any;
    randomSpy = jest.spyOn(Math, "random");
  });

  afterEach(() => {
    global.fetch = originalFetch;
    randomSpy.mockRestore();
    jest.resetModules();
  });

  describe("lifecycle events always fire", () => {
    it("init event fires even at the highest random value", async () => {
      randomSpy.mockReturnValue(0.999);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("init", makeInstance());
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("reset event fires even at the highest random value", async () => {
      randomSpy.mockReturnValue(0.999);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("reset", makeInstance());
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("init event payload has sample_rate: 1.0", async () => {
      randomSpy.mockReturnValue(0.999);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("init", makeInstance());
      const body = JSON.parse(fetchMock.mock.calls[0][1].body);
      expect(body.properties.sample_rate).toBe(1.0);
    });
  });

  describe("hot-path events are sampled", () => {
    it("add event is dropped when random > sample_rate", async () => {
      randomSpy.mockReturnValue(0.99); // > 0.1 default rate
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("search event is dropped when random > sample_rate", async () => {
      randomSpy.mockReturnValue(0.99);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("search", makeInstance());
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("add event passes when random < sample_rate", async () => {
      randomSpy.mockReturnValue(0.05); // < 0.1 default rate
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("hot-path event payload has sample_rate: 0.1", async () => {
      randomSpy.mockReturnValue(0.05);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      const body = JSON.parse(fetchMock.mock.calls[0][1].body);
      expect(body.properties.sample_rate).toBe(0.1);
    });

    it("sample_rate cannot be overridden by additionalData", async () => {
      randomSpy.mockReturnValue(0.05);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance(), { sample_rate: 0.99 });
      const body = JSON.parse(fetchMock.mock.calls[0][1].body);
      expect(body.properties.sample_rate).toBe(0.1);
    });
  });

  describe("env var override", () => {
    afterEach(() => {
      delete process.env.MEM0_TELEMETRY_SAMPLE_RATE;
    });

    it("rate 1.0 sends every event including hot-path at high random", async () => {
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = "1.0";
      jest.resetModules();
      randomSpy.mockReturnValue(0.999);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      // 0.999 > 1.0 is false, so the gate never trips
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("rate 0.0 drops every hot-path event including at random 0", async () => {
      // The gate is `random >= rate`, so rate=0 drops at random=0 (0 >= 0 is true).
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = "0.0";
      jest.resetModules();
      randomSpy.mockReturnValue(0.0);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rate 0.0 drops at any random value", async () => {
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = "0.0";
      jest.resetModules();
      randomSpy.mockReturnValue(0.5);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("rate 0.0 still passes lifecycle events", async () => {
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = "0.0";
      jest.resetModules();
      randomSpy.mockReturnValue(0.999);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("init", makeInstance());
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("rate 0.5 passes events at random below 0.5", async () => {
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = "0.5";
      jest.resetModules();
      randomSpy.mockReturnValue(0.3);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("invalid env var falls back to default rate", async () => {
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = "not a number";
      jest.resetModules();
      randomSpy.mockReturnValue(0.05);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("out-of-range env var (negative) falls back to default rate", async () => {
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = "-0.5";
      jest.resetModules();
      randomSpy.mockReturnValue(0.05);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("out-of-range env var (> 1) falls back to default rate", async () => {
      process.env.MEM0_TELEMETRY_SAMPLE_RATE = "5";
      jest.resetModules();
      randomSpy.mockReturnValue(0.05);
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance());
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  describe("contract preservation", () => {
    it("lifecycle event includes additionalData", async () => {
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("init", makeInstance(), {
        api_version: "v1.1",
        client_type: "Memory",
      });
      const body = JSON.parse(fetchMock.mock.calls[0][1].body);
      expect(body.properties.api_version).toBe("v1.1");
      expect(body.properties.client_type).toBe("Memory");
      expect(body.properties.sample_rate).toBe(1.0);
    });

    it("captureClientEvent without telemetryId is a no-op", async () => {
      const { captureClientEvent } = await import("../src/utils/telemetry");
      await captureClientEvent("add", makeInstance({ telemetryId: "" }));
      expect(fetchMock).not.toHaveBeenCalled();
    });
  });
});
