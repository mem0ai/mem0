import assert from "node:assert/strict";
import test from "node:test";

import { normalizeScope, scopeAddParams, scopeSearchFilters } from "../src/scoping.ts";

const context = { userId: "u", appId: "app", runId: "run" };

test("normalizes unknown scope to project", () => {
  assert.equal(normalizeScope("session"), "session");
  assert.equal(normalizeScope("global"), "global");
  assert.equal(normalizeScope("invalid"), "project");
});

test("resolves project, session, and global search filters", () => {
  assert.deepEqual(scopeSearchFilters("project", context), { user_id: "u", app_id: "app" });
  assert.deepEqual(scopeSearchFilters("session", context), { user_id: "u", app_id: "app", run_id: "run" });
  assert.deepEqual(scopeSearchFilters("global", context), { user_id: "u", app_id: "*" });
});

test("resolves camel-case add params", () => {
  assert.deepEqual(scopeAddParams("project", context), { userId: "u", appId: "app" });
  assert.deepEqual(scopeAddParams("session", context), { userId: "u", appId: "app", runId: "run" });
  assert.deepEqual(scopeAddParams("global", context), { userId: "u" });
});
