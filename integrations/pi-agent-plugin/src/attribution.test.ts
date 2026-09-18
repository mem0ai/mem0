import { describe, expect, it } from "vitest";
import { applySurfaceHeaders, PLATFORM_APPLICATION, PLATFORM_SOURCE } from "./attribution.ts";

function client(headers: Record<string, string> = {}) {
  return { headers: { Authorization: "Token k", ...headers } } as never;
}

describe("applySurfaceHeaders", () => {
  it("stamps the shared client so every path is attributed, not just commands", () => {
    const mem0 = client();
    applySurfaceHeaders(mem0);
    const headers = (mem0 as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-Mem0-Source"]).toBe(PLATFORM_SOURCE);
    expect(headers["X-Application"]).toBe(PLATFORM_APPLICATION);
    expect(headers["X-Mem0-Client"]).toMatch(/^mem0-pi-agent\//);
    expect(headers.Authorization).toBe("Token k");
  });

  it("defers to a surface an outer wrapper already declared", () => {
    const mem0 = client({ "X-Mem0-Source": "OPENCLAW", "X-Application": "vscode" });
    applySurfaceHeaders(mem0);
    const headers = (mem0 as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-Mem0-Source"]).toBe("OPENCLAW");
    expect(headers["X-Application"]).toBe("vscode");
  });

  it("appends to the client stack rather than replacing it", () => {
    const mem0 = client({ "X-Mem0-Client": "openclaw/2.1.0" });
    applySurfaceHeaders(mem0);
    const headers = (mem0 as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-Mem0-Client"]).toMatch(/^openclaw\/2\.1\.0, mem0-pi-agent\//);
  });

  it("treats a blank header as absent", () => {
    const mem0 = client({ "X-Mem0-Source": "   " });
    applySurfaceHeaders(mem0);
    const headers = (mem0 as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-Mem0-Source"]).toBe(PLATFORM_SOURCE);
  });

  it("bounds the stack so a long chain cannot grow the header without limit", () => {
    const mem0 = client({ "X-Mem0-Client": "a/1, b/1, c/1, d/1, e/1" });
    applySurfaceHeaders(mem0);
    const headers = (mem0 as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-Mem0-Client"].split(",").length).toBeLessThanOrEqual(4);
    expect(headers["X-Mem0-Client"].length).toBeLessThanOrEqual(200);
  });
});

describe("client stack bounding", () => {
  it("keeps our own entry when the caller already filled the stack", () => {
    // The defect: pushing then trimming to four dropped exactly the entry this
    // function exists to add, so we vanished from our own stack.
    const mem0 = client({ "X-Mem0-Client": "a/1, b/2, c/3, d/4" });
    applySurfaceHeaders(mem0);
    const stack = (mem0 as unknown as { headers: Record<string, string> }).headers["X-Mem0-Client"];

    expect(stack).toMatch(/mem0-pi-agent\//);
    expect(stack.split(",").length).toBeLessThanOrEqual(4);
  });

  it("drops whole entries at the character cap, never a fragment", () => {
    const long = `${"n".repeat(90)}/1.0, ${"m".repeat(90)}/1.0, ${"o".repeat(90)}/1.0`;
    const mem0 = client({ "X-Mem0-Client": long });
    applySurfaceHeaders(mem0);
    const stack = (mem0 as unknown as { headers: Record<string, string> }).headers["X-Mem0-Client"];

    expect(stack.length).toBeLessThanOrEqual(200);
    expect(stack.endsWith("/0.0.0") || /mem0-pi-agent\/[\w.\-]+$/.test(stack)).toBe(true);
    // Every surviving entry is whole: name/version, no severed tail.
    for (const entry of stack.split(",")) {
      expect(entry.trim()).toMatch(/^[^/]+\/[^/]+$/);
    }
  });
});
