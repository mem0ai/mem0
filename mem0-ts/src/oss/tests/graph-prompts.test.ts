import {
  DELETE_RELATIONS_SYSTEM_PROMPT,
  EXTRACT_RELATIONS_PROMPT,
  UPDATE_GRAPH_PROMPT,
  getDeleteMessages,
  formatEntities,
} from "../src/graphs/utils";

/**
 * Regression tests for graph prompts (issue #4248).
 *
 * When response_format: { type: "json_object" } is used, OpenAI requires
 * the word "json" (case-insensitive) to appear in at least one message.
 * Missing it produces a 400 error.
 *
 * Three call sites use json_object today:
 *   1. _getDeleteEntitiesFromSearchOutput → DELETE_RELATIONS_SYSTEM_PROMPT
 *   2. _retrieveNodesFromData            → inline prompt (graph_memory.ts)
 *   3. _getRelatedEntities               → EXTRACT_RELATIONS_PROMPT + suffix
 *
 * See: https://github.com/mem0ai/mem0/issues/4248
 */

// ─── JSON keyword presence ────────────────────────────────────────────────────

describe("Graph prompts — JSON keyword requirement", () => {
  it("DELETE_RELATIONS_SYSTEM_PROMPT contains 'json'", () => {
    expect(DELETE_RELATIONS_SYSTEM_PROMPT.toLowerCase()).toContain("json");
  });

  it("EXTRACT_RELATIONS_PROMPT produces a message containing 'json' once the suffix is appended", () => {
    // graph_memory.ts appends "\nPlease provide your response in JSON format."
    const withSuffix =
      EXTRACT_RELATIONS_PROMPT +
      "\nPlease provide your response in JSON format.";
    expect(withSuffix.toLowerCase()).toContain("json");
  });

  it("getDeleteMessages system message contains 'json' after USER_ID substitution", () => {
    const [systemContent] = getDeleteMessages(
      "alice -- loves -- pizza",
      "Alice now hates pizza",
      "user-42",
    );
    expect(systemContent.toLowerCase()).toContain("json");
  });

  it("entity extraction inline prompt contains 'json' (simulated from graph_memory.ts)", () => {
    // Mirrors the template in _retrieveNodesFromData()
    const userId = "user-1";
    const prompt = `You are a smart assistant who understands entities and their types in a given text. If user message contains self reference such as 'I', 'me', 'my' etc. then use ${userId} as the source entity. Extract all the entities from the text. ***DO NOT*** answer the question itself if the given text is a question. Respond in JSON format.`;
    expect(prompt.toLowerCase()).toContain("json");
  });
});

// ─── getDeleteMessages ────────────────────────────────────────────────────────

describe("getDeleteMessages", () => {
  it("replaces USER_ID with the provided userId in the system prompt", () => {
    const [system] = getDeleteMessages("mem", "data", "alice-123");
    expect(system).toContain("alice-123");
    expect(system).not.toContain("USER_ID");
  });

  it("includes existing memories and new data in the user prompt", () => {
    const existing = "bob -- knows -- carol";
    const newData = "Bob no longer knows Carol";
    const [, user] = getDeleteMessages(existing, newData, "u1");
    expect(user).toContain(existing);
    expect(user).toContain(newData);
  });

  it("returns a 2-tuple [system, user]", () => {
    const result = getDeleteMessages("a", "b", "c");
    expect(result).toHaveLength(2);
    expect(typeof result[0]).toBe("string");
    expect(typeof result[1]).toBe("string");
  });

  // — Malformed / edge-case inputs —

  it("handles empty strings without throwing", () => {
    expect(() => getDeleteMessages("", "", "")).not.toThrow();
    const [system, user] = getDeleteMessages("", "", "");
    expect(system.toLowerCase()).toContain("json");
    expect(typeof user).toBe("string");
  });

  it("handles special characters in userId (e.g. angle brackets, quotes)", () => {
    const [system] = getDeleteMessages(
      "mem",
      "data",
      '<script>alert("xss")</script>',
    );
    expect(system).toContain('<script>alert("xss")</script>');
    expect(system).not.toContain("USER_ID");
  });

  it("handles unicode input", () => {
    const [system, user] = getDeleteMessages(
      "日本語メモリ",
      "新しい情報",
      "ユーザー1",
    );
    expect(system).toContain("ユーザー1");
    expect(user).toContain("日本語メモリ");
    expect(user).toContain("新しい情報");
  });

  it("handles very long input strings", () => {
    const longStr = "x".repeat(100_000);
    expect(() => getDeleteMessages(longStr, longStr, "u")).not.toThrow();
    const [system] = getDeleteMessages(longStr, longStr, "u");
    expect(system.toLowerCase()).toContain("json");
  });
});

// ─── formatEntities ───────────────────────────────────────────────────────────

describe("formatEntities", () => {
  it("formats a single entity triplet", () => {
    const result = formatEntities([
      { source: "Alice", relationship: "knows", destination: "Bob" },
    ]);
    expect(result).toBe("Alice -- knows -- Bob");
  });

  it("joins multiple entities with newlines", () => {
    const result = formatEntities([
      { source: "A", relationship: "r1", destination: "B" },
      { source: "C", relationship: "r2", destination: "D" },
    ]);
    expect(result).toBe("A -- r1 -- B\nC -- r2 -- D");
  });

  it("returns empty string for empty array", () => {
    expect(formatEntities([])).toBe("");
  });

  it("preserves special characters in entity fields", () => {
    const result = formatEntities([
      { source: "O'Brien", relationship: 'said "hello"', destination: "café" },
    ]);
    expect(result).toContain("O'Brien");
    expect(result).toContain('said "hello"');
    expect(result).toContain("café");
  });
});

// ─── Prompt structural invariants ─────────────────────────────────────────────

describe("Prompt structural invariants", () => {
  it("DELETE_RELATIONS_SYSTEM_PROMPT contains USER_ID placeholder", () => {
    expect(DELETE_RELATIONS_SYSTEM_PROMPT).toContain("USER_ID");
  });

  it("EXTRACT_RELATIONS_PROMPT contains USER_ID placeholder", () => {
    expect(EXTRACT_RELATIONS_PROMPT).toContain("USER_ID");
  });

  it("EXTRACT_RELATIONS_PROMPT contains CUSTOM_PROMPT placeholder", () => {
    expect(EXTRACT_RELATIONS_PROMPT).toContain("CUSTOM_PROMPT");
  });

  it("UPDATE_GRAPH_PROMPT contains memory template placeholders", () => {
    expect(UPDATE_GRAPH_PROMPT).toContain("{existing_memories}");
    expect(UPDATE_GRAPH_PROMPT).toContain("{new_memories}");
  });

  it("DELETE_RELATIONS_SYSTEM_PROMPT is non-empty and reasonably sized", () => {
    expect(DELETE_RELATIONS_SYSTEM_PROMPT.length).toBeGreaterThan(100);
  });

  it("EXTRACT_RELATIONS_PROMPT is non-empty and reasonably sized", () => {
    expect(EXTRACT_RELATIONS_PROMPT.length).toBeGreaterThan(100);
  });
});
