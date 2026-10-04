import { extractEntities } from "../src/utils/entity_extraction";

describe("extractEntities", () => {
  it("handles product lists, coordinated names, and identifiers", () => {
    const text =
      "User reported top inbound integration pages: OpenClaw 25,443, " +
      "Claude Code 8,916, Codex 2,573, Dify 656. " +
      "User compared Cartesia and Deepgram. " +
      "The email field for Mem0 lives at person.properties.email. " +
      "The qwen endpoint uses person.properties.email. " +
      "Johnson & Johnson was mentioned. " +
      "Glasses around my window. " +
      "On 2026-05-27 there were 90 days of stats.";

    const entityTexts = new Set(
      extractEntities(text).map((entity) => entity.text),
    );
    const normalized = new Set(
      [...entityTexts].map((entityText) => entityText.toLowerCase()),
    );

    for (const expected of [
      "OpenClaw",
      "Claude Code",
      "Codex",
      "Dify",
      "Cartesia",
      "Deepgram",
      "Mem0",
    ]) {
      expect(entityTexts.has(expected)).toBe(true);
    }
    expect(entityTexts.has("person.properties.email")).toBe(true);
    expect(entityTexts.has("qwen endpoint")).toBe(true);
    expect(entityTexts.has("Johnson & Johnson")).toBe(true);
    expect(entityTexts.has("Johnson")).toBe(false);
    expect(normalized.has("top")).toBe(false);
    expect(normalized.has("glasses")).toBe(false);
    expect(entityTexts.has("Cartesia and Deepgram")).toBe(false);
    expect(entityTexts.has("Claude Code 8,916")).toBe(false);
    for (const rejected of ["8,916", "2,573", "656", "2026-05-27", "90"]) {
      expect(entityTexts.has(rejected)).toBe(false);
    }
  });
});
