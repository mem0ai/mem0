import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_OUTPUT_CHARS,
  MAX_OUTPUT_LINES,
  formatAddResult,
  formatAge,
  formatMemoryCompact,
  formatMemoryList,
  truncateOutput,
} from "../src/formatting.ts";

test("memory formatting preserves the existing compact host output", () => {
  const now = Date.now();
  assert.equal(formatAge(new Date(now - 30 * 60_000)), "30m ago");
  assert.match(
    formatMemoryCompact({ id: "abc", memory: "Dark mode", categories: ["preference"] }),
    /^\[preference\] Dark mode \[mem0:abc\]$/,
  );
  assert.equal(formatMemoryList([]), "No memories found.");
  assert.match(formatMemoryList([{ id: "1", memory: "A" }, { id: "2", memory: "B" }]), /^1\..*\n2\./);
});

test("write formatting handles pending, stored, and empty results", () => {
  assert.equal(
    formatAddResult({ eventId: "evt-9", status: "PENDING" }),
    "Memory queued for background extraction (event evt-9); it will be searchable shortly.",
  );
  assert.match(formatAddResult([{ id: "1" }, { id: "2" }]), /^Stored 2 memories:/);
  assert.equal(formatAddResult([]), "Memory stored.");
});

test("output truncation preserves small output and bounds large output", () => {
  assert.equal(truncateOutput("a\nb"), "a\nb");
  const many = Array.from({ length: MAX_OUTPUT_LINES + 1 }, (_, index) => `line ${index}`).join("\n");
  assert.match(truncateOutput(many), /showing 200 of 201 lines/);
  assert.match(truncateOutput("x".repeat(MAX_OUTPUT_CHARS + 1)), /cut at 50KB/);
});
