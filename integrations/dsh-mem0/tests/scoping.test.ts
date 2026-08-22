import { describe, it, expect } from "vitest";
import { resolveEntity } from "../src/scoping.ts";

describe("resolveEntity", () => {
  it("falls back to the configured default userId", () => {
    expect(resolveEntity({}, "default-user")).toEqual({ user_id: "default-user" });
  });

  it("lets a per-call userId override the default", () => {
    expect(resolveEntity({ userId: "alice" }, "default-user")).toEqual({
      user_id: "alice",
    });
  });

  it("treats a blank/whitespace userId as absent and falls back", () => {
    expect(resolveEntity({ userId: "   " }, "default-user")).toEqual({
      user_id: "default-user",
    });
  });

  it("includes agent and run scope only when provided", () => {
    expect(
      resolveEntity({ userId: "alice", agentId: "agent-1", runId: "run-9" }, "default"),
    ).toEqual({ user_id: "alice", agent_id: "agent-1", run_id: "run-9" });
  });

  it("emits snake_case keys the platform expects, omitting blanks", () => {
    const entity = resolveEntity({ agentId: "  ", runId: "run-9" }, "default");
    expect(entity).toEqual({ user_id: "default", run_id: "run-9" });
    expect(entity).not.toHaveProperty("agent_id");
  });
});
