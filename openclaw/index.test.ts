/**
 * Tests for per-agent memory isolation helpers.
 */
import { describe, it, expect } from "vitest";
import { agentUserId } from "./index.ts";

// ---------------------------------------------------------------------------
// agentUserId
// ---------------------------------------------------------------------------
describe("agentUserId", () => {
  it("produces the correct namespaced format", () => {
    expect(agentUserId("alice", "researcher")).toBe("alice:agent:researcher");
  });

  it("handles empty agentId (caller is responsible for validation)", () => {
    expect(agentUserId("alice", "")).toBe("alice:agent:");
  });

  it("different agents get different namespaces", () => {
    const alphaId = agentUserId("user-42", "alpha");
    const betaId = agentUserId("user-42", "beta");
    expect(alphaId).not.toBe(betaId);
    expect(alphaId).toBe("user-42:agent:alpha");
    expect(betaId).toBe("user-42:agent:beta");
  });
});
