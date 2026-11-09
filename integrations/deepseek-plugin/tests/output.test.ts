import { describe, it, expect } from "vitest";
import { truncateOutput, MAX_OUTPUT_LINES } from "../src/output.ts";

describe("truncateOutput", () => {
  it("passes small output through untouched", () => {
    expect(truncateOutput("a\nb\nc")).toBe("a\nb\nc");
  });

  it("caps output at MAX_OUTPUT_LINES and appends a notice", () => {
    const many = Array.from({ length: MAX_OUTPUT_LINES + 50 }, (_, i) => `line ${i}`).join("\n");
    const out = truncateOutput(many);
    expect(out.split("\n").length).toBeLessThanOrEqual(MAX_OUTPUT_LINES + 3);
    expect(out).toContain("[Output truncated:");
    expect(out).toContain(`of ${MAX_OUTPUT_LINES + 50} lines`);
  });

  it("caps output that is few lines but very large by bytes", () => {
    const huge = "x".repeat(60_000);
    const out = truncateOutput(huge);
    expect(out.length).toBeLessThan(huge.length);
    expect(out).toContain("[Output truncated:");
  });

  it("reports both reasons when the line cap and the byte cap fire together", () => {
    const wide = Array.from({ length: MAX_OUTPUT_LINES + 50 }, () => "x".repeat(300)).join("\n");
    const out = truncateOutput(wide);
    expect(out).toContain(`of ${MAX_OUTPUT_LINES + 50} lines`);
    expect(out).toContain("cut at 50KB");
  });
});
