/**
 * Tests for path traversal prevention in skill-loader.
 */
import { describe, it, expect } from "vitest";
import {
  safePath,
  normalizeModuleUrlToPath,
  loadSkill,
  loadTriagePrompt,
  loadCompactTriagePrompt,
} from "./skill-loader.ts";
import { fileURLToPath, pathToFileURL } from "node:url";

// ---------------------------------------------------------------------------
// safePath — path containment
// ---------------------------------------------------------------------------
describe("safePath", () => {
  it("rejects parent directory traversal", () => {
    expect(safePath("../../etc/passwd")).toBeNull();
  });

  it("rejects deep traversal", () => {
    expect(safePath("../../../etc/shadow")).toBeNull();
  });

  it("rejects traversal in nested segment", () => {
    expect(safePath("valid", "../../etc")).toBeNull();
  });

  it("rejects bare '..' as segment", () => {
    expect(safePath("..")).toBeNull();
  });

  it("accepts valid skill paths", () => {
    expect(safePath("memory-triage", "SKILL.md")).not.toBeNull();
  });

  it("accepts valid domain overlay paths", () => {
    expect(safePath("memory-triage", "domains", "companion.md")).not.toBeNull();
  });

  it("returns null for empty segments that resolve to skills root with subpath escape", () => {
    // path.resolve("skills", "", "../../etc") still escapes
    expect(safePath("", "../../etc")).toBeNull();
  });

  it("rejects traversal disguised with valid prefix", () => {
    expect(safePath("memory-triage/../../etc/passwd")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// loadSkill — integration tests for traversal prevention
// ---------------------------------------------------------------------------
describe("loadSkill path traversal", () => {
  it("returns null for traversal skillName", () => {
    expect(loadSkill("../../etc/passwd")).toBeNull();
  });

  it("returns null for deep traversal skillName", () => {
    expect(loadSkill("../../../..")).toBeNull();
  });

  it("loads a valid skill", () => {
    const result = loadSkill("memory-triage");
    expect(result).not.toBeNull();
    expect(result?.prompt).toBeTruthy();
  });

  it("blocks domain traversal while loading valid skill", () => {
    // Valid skill name, malicious domain — should load skill but skip the overlay
    const result = loadSkill("memory-triage", { domain: "../../etc/passwd" });
    // Should still succeed (skill itself is valid), domain overlay is just skipped
    expect(result).not.toBeNull();
    expect(result?.prompt).toBeTruthy();
  });
});

describe("normalizeModuleUrlToPath", () => {
  it("normalizes raw Windows paths before fileURLToPath conversion", () => {
    const rawWindowsMetaUrl = "C:\\Users\\example\\openclaw\\index.ts";
    const result = normalizeModuleUrlToPath(rawWindowsMetaUrl);
    // Assert the decoded property directly rather than reconstructing via the function body
    expect(typeof result).toBe("string");
    expect(result).not.toContain("%5C");
  });

  it("leaves already-correct file URLs unchanged", () => {
    const fileMetaUrl = "file:///C:/Users/example/openclaw/index.ts";
    const expected = fileURLToPath(fileMetaUrl);

    expect(normalizeModuleUrlToPath(fileMetaUrl)).toBe(expected);
  });

  it.skipIf(process.platform === "win32")(
    "passes POSIX absolute paths through unchanged",
    () => {
      const posixPath = "/home/user/openclaw/index.ts";
      expect(normalizeModuleUrlToPath(posixPath)).toBe(posixPath);
    },
  );
});

describe("loadCompactTriagePrompt", () => {
  it("keeps the core triage instructions without inlining the full skill body", () => {
    const prompt = loadCompactTriagePrompt();

    expect(prompt).toContain("Use `memory_add` tool for ALL user facts");
    expect(prompt).toContain("Batch facts by CATEGORY");
    expect(prompt).toContain("ALWAYS rewrite the query");
    expect(prompt).not.toContain("## Worked Examples");
    expect(prompt).not.toContain("### memory_search");
    expect(prompt).not.toContain("Conference requires at least 4 breakout rooms");
    expect(prompt.length).toBeLessThan(3500);
  });

  it("keeps the always-recall guidance aligned with the full triage prompt", () => {
    const config = { recall: { strategy: "always" as const } };
    const expected =
      "Automatic recall runs for both long-term and session memory. Use manual searches only when you need more specific context.";

    expect(loadCompactTriagePrompt(config)).toContain(expected);
    expect(loadTriagePrompt(config)).toContain(expected);
  });

  it("keeps the manual-recall guidance in compact mode", () => {
    const prompt = loadCompactTriagePrompt({
      recall: { strategy: "manual" },
    });

    expect(prompt).toContain("No automatic recall happens in manual mode.");
  });

  it("includes short config summaries and truncates oversized custom rules", () => {
    const prompt = loadCompactTriagePrompt({
      categories: {
        travel: { importance: 0.7, ttl: "30d" },
      },
      customRules: {
        include: [
          "Always remember workshop venue requirements.",
          "Keep track of recurring conference planning constraints.",
          "Capture every catering preference, transit note, and presenter dependency in detail.",
        ],
        exclude: [
          "Never store one-off demo logs, temporary ETA chatter, or transitory checklist updates.",
          "Skip verbose retrospectives unless the user explicitly says the lesson should persist.",
        ],
      },
    });

    expect(prompt).toContain("travel (importance 0.7, expires: 30d)");
    expect(prompt).toContain("include rule(s) and 2 exclude rule(s) are configured");
    expect(prompt).toContain("Prompt kept compact, full rule text omitted");
    expect(prompt).toContain('Preview: include "Always remember workshop venue requirements."');
  });

  it("omits default credential patterns in compact mode unless custom patterns are configured", () => {
    const defaultPrompt = loadCompactTriagePrompt();
    const customPrompt = loadCompactTriagePrompt({
      triage: {
        credentialPatterns: ["mem0-secret=", "Bearer "],
      },
    });

    expect(defaultPrompt).not.toContain("Credential patterns to scan");
    expect(customPrompt).toContain("Credential patterns to scan");
    expect(customPrompt).toContain("mem0-secret=");
  });
});
