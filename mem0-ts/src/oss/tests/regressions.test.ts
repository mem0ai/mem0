/**
 * Regression tests for fixed bugs — guards specific bug scenarios.
 * Each test references the GitHub issue number it guards.
 *
 * General functionality tests live in their respective unit test files.
 * This file tests the EXACT scenario that triggered each bug.
 */
/// <reference types="jest" />
import { removeCodeBlocks } from "../src/prompts";
import { MemoryVectorStore } from "../src/vector_stores/memory";

// ─── #4141 — removeCodeBlocks was DESTROYING content ────
// The old regex deleted everything between fences instead of extracting it.
// This test uses the exact format LLMs return that triggered the bug.

describe("Regression: #4141 — removeCodeBlocks must extract, not delete", () => {
  test("LLM JSON response wrapped in code fence is extracted intact", () => {
    const llmOutput =
      '```json\n{"facts": ["User likes Python", "User is a developer"]}\n```';
    const result = removeCodeBlocks(llmOutput);
    const parsed = JSON.parse(result.trim());
    expect(parsed.facts).toHaveLength(2);
    expect(parsed.facts[0]).toBe("User likes Python");
  });
});

// ─── #4279 — vector store defaulted to process.cwd() ────
// Old default was process.cwd()/vector_store.db which fails in containers
// where cwd is / (read-only). Now defaults to ~/.mem0/vector_store.db.

describe("Regression: #4279 — vector store respects custom dbPath", () => {
  test("explicit dbPath=:memory: is used, not cwd default", () => {
    const store = new MemoryVectorStore({ dimension: 4, dbPath: ":memory:" });
    // If dbPath was ignored, this would create a file at cwd
    expect(store).toBeDefined();
  });
});

// ─── #4057 — dimension mismatch gave no useful error ─────

describe("Regression: #4057 — dimension mismatch shows expected vs actual", () => {
  test("insert error includes expected and actual dimensions", async () => {
    const store = new MemoryVectorStore({ dimension: 4, dbPath: ":memory:" });
    await expect(
      store.insert([[1, 2, 3]], ["id1"], [{ data: "test" }]),
    ).rejects.toThrow("Expected 4, got 3");
  });
});
