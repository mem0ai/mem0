import assert from "node:assert/strict";
import test from "node:test";

import { entityAddParams, entitySearchFilters, parseProjectFromRemote } from "../src/identity.ts";

test("parses common git remote forms", () => {
  assert.equal(parseProjectFromRemote("git@github.com-work:mem0ai/mem0.git"), "mem0ai-mem0");
  assert.equal(parseProjectFromRemote("https://github.com/mem0ai/mem0/"), "mem0ai-mem0");
  assert.equal(parseProjectFromRemote("not-a-remote"), null);
  assert.equal(parseProjectFromRemote(""), null);
});

test("entity filters trim overrides and preserve API casing", () => {
  const params = { userId: " alice ", agentId: " agent ", runId: " " };
  assert.deepEqual(entitySearchFilters(params, "default"), { user_id: "alice", agent_id: "agent" });
  assert.deepEqual(entityAddParams(params, "default"), { userId: "alice", agentId: "agent" });
  assert.deepEqual(entitySearchFilters({ userId: " " }, "default"), { user_id: "default" });
});
