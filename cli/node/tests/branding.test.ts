/**
 * Tests for branding utilities.
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  BRAND_COLOR,
  SUCCESS_COLOR,
  ERROR_COLOR,
  TAGLINE,
  LOGO_MINI,
  printSuccess,
  printError,
  printWarning,
  printInfo,
  printScope,
} from "../src/branding.js";

let output: string;
let errOutput: string;
const originalLog = console.log;
const originalError = console.error;

beforeEach(() => {
  output = "";
  errOutput = "";
  console.log = (...args: unknown[]) => {
    output += args.map(String).join(" ") + "\n";
  };
  console.error = (...args: unknown[]) => {
    errOutput += args.map(String).join(" ") + "\n";
  };
});

afterEach(() => {
  console.log = originalLog;
  console.error = originalError;
});

describe("branding constants", () => {
  it("has correct brand color", () => {
    expect(BRAND_COLOR).toBe("#8b5cf6");
  });

  it("has correct tagline", () => {
    expect(TAGLINE).toBe("The Memory Layer for AI Agents");
  });

  it("has correct logo mini", () => {
    expect(LOGO_MINI).toBe("◆ mem0");
  });
});

describe("printSuccess", () => {
  it("prints success message", () => {
    printSuccess("Operation completed");
    expect(output).toContain("Operation completed");
  });
});

describe("printError", () => {
  it("prints error message to stderr", () => {
    printError("Something failed");
    expect(errOutput).toContain("Something failed");
  });

  it("prints hint when provided to stderr", () => {
    printError("Failed", "Try again");
    expect(errOutput).toContain("Try again");
  });
});

describe("printWarning", () => {
  it("prints warning message to stderr", () => {
    printWarning("Be careful");
    expect(errOutput).toContain("Be careful");
  });
});

describe("printInfo", () => {
  it("prints info message", () => {
    printInfo("Important note");
    expect(errOutput).toContain("Important note");
  });
});

describe("printScope", () => {
  it("prints scope when IDs present", () => {
    printScope({ user_id: "alice", agent_id: "bot" });
    expect(errOutput).toContain("alice");
    expect(errOutput).toContain("bot");
  });

  it("prints nothing when no IDs", () => {
    printScope({});
    expect(errOutput).toBe("");
  });
});
