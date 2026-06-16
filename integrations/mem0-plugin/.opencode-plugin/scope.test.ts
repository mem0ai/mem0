import { describe, expect, test } from "bun:test";
import { scopeSearchFilters, scopeWriteParams, asScope } from "./scope";

describe("memory scope (pi-agent parity)", () => {
  test("project scope = this repo", () => {
    expect(scopeSearchFilters("project", "u", "app", "run")).toEqual({
      user_id: "u",
      app_id: "app",
    });
    expect(scopeWriteParams("project", "u", "app", "run")).toEqual({
      user_id: "u",
      app_id: "app",
    });
  });

  test("session scope adds run_id", () => {
    expect(scopeSearchFilters("session", "u", "app", "run")).toEqual({
      user_id: "u",
      app_id: "app",
      run_id: "run",
    });
    expect(scopeWriteParams("session", "u", "app", "run")).toEqual({
      user_id: "u",
      app_id: "app",
      run_id: "run",
    });
  });

  test("global scope spans all the user's projects (matches pi-agent)", () => {
    expect(scopeSearchFilters("global", "u", "app", "run")).toEqual({
      user_id: "u",
      app_id: "*",
    });
    // global writes drop app_id so the memory is user-wide, not project-bound
    expect(scopeWriteParams("global", "u", "app", "run")).toEqual({ user_id: "u" });
  });

  test("asScope normalizes unknown values to project", () => {
    expect(asScope("global")).toBe("global");
    expect(asScope("session")).toBe("session");
    expect(asScope("project")).toBe("project");
    expect(asScope("nonsense")).toBe("project");
    expect(asScope(undefined)).toBe("project");
  });
});
