import assert from "node:assert/strict";
import test from "node:test";

import { normalizeScope, resolveToolScope, scopeAddParams, scopeSearchFilters } from "../src/scoping.ts";

const context = { userId: "u", appId: "app", runId: "run" };

test("normalizes unknown scope to project", () => {
  assert.equal(normalizeScope("session"), "session");
  assert.equal(normalizeScope("global"), "global");
  assert.equal(normalizeScope("invalid"), "project");
});

test("resolves project, session, and global search filters", () => {
  assert.deepEqual(scopeSearchFilters("project", context), { user_id: "u", app_id: "app" });
  assert.deepEqual(scopeSearchFilters("session", context), { user_id: "u", app_id: "app", run_id: "run" });
  assert.deepEqual(scopeSearchFilters("global", context), { user_id: "u" });
});

test("resolves camel-case add params", () => {
  assert.deepEqual(scopeAddParams("project", context), { userId: "u", appId: "app" });
  assert.deepEqual(scopeAddParams("session", context), { userId: "u", appId: "app", runId: "run" });
  assert.deepEqual(scopeAddParams("global", context), { userId: "u" });
});

test("rejects empty and wildcard identities before building filters or writes", () => {
  for (const invalid of ["", "  ", "*", "***"]) {
    for (const scope of ["project", "session"] as const) {
      for (const resolve of [scopeSearchFilters, scopeAddParams]) {
        assert.throws(() => resolve(scope, { ...context, appId: invalid }), /appId/);
        assert.throws(() => resolve(scope, { ...context, userId: invalid }), /userId/);
      }
    }
    assert.throws(() => scopeSearchFilters("session", { ...context, runId: invalid }), /runId/);
  }
});


test("tools cannot enable global scope without a user-configured global default", () => {
  assert.throws(() => resolveToolScope("global", "project"), /Select global/);
  assert.throws(() => resolveToolScope("global", "session"), /Select global/);
  assert.equal(resolveToolScope("global", "global"), "global");
  assert.equal(resolveToolScope("session", "project"), "session");
});
