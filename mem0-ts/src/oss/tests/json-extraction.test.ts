/// <reference types="jest" />

import { removeCodeBlocks, extractJson } from "../src/prompts";

describe("removeCodeBlocks", () => {
  it("should extract content from complete code fence with language tag", () => {
    const input = '```json\n{"a":1}\n```';
    expect(removeCodeBlocks(input)).toBe('{"a":1}');
  });

  it("should extract content from complete code fence without language tag", () => {
    const input = '```\n{"a":1}\n```';
    expect(removeCodeBlocks(input)).toBe('{"a":1}');
  });

  it("should extract content from unclosed code fence (truncated response)", () => {
    const input = '```json\n{"a":1';
    expect(removeCodeBlocks(input)).toBe('{"a":1');
  });

  it("should return text unchanged when no code fences", () => {
    const input = '{"a":1}';
    expect(removeCodeBlocks(input)).toBe('{"a":1}');
  });

  it("should preserve backticks in content", () => {
    const input = '```json\n{"code": "use `backticks` here"}\n```';
    expect(removeCodeBlocks(input)).toBe('{"code": "use `backticks` here"}');
  });

  it("should handle empty string", () => {
    expect(removeCodeBlocks("")).toBe("");
  });
});

describe("extractJson", () => {
  it("should extract JSON from fenced code block", () => {
    const input = '```json\n{"facts": ["a", "b"]}\n```';
    expect(extractJson(input)).toBe('{"facts": ["a", "b"]}');
  });

  it("should extract JSON from unclosed code fence", () => {
    const input = '```json\n{"facts": ["a"';
    expect(extractJson(input)).toBe('{"facts": ["a"');
  });

  it("should return raw JSON unchanged", () => {
    const input = '{"facts": ["a", "b"]}';
    expect(extractJson(input)).toBe('{"facts": ["a", "b"]}');
  });

  it("should trim whitespace from raw JSON", () => {
    const input = '  {"facts": ["a"]}  ';
    expect(extractJson(input)).toBe('{"facts": ["a"]}');
  });
});

describe("Two-stage JSON parse", () => {
  function twoStageParse(response: string): any {
    try {
      return JSON.parse(response);
    } catch {
      return JSON.parse(extractJson(response));
    }
  }

  it("should parse well-formed JSON on first attempt", () => {
    const input = '{"facts": ["a", "b"]}';
    expect(twoStageParse(input)).toEqual({ facts: ["a", "b"] });
  });

  it("should fall back to extractJson for fenced JSON", () => {
    const input = '```json\n{"facts": ["a", "b"]}\n```';
    expect(twoStageParse(input)).toEqual({ facts: ["a", "b"] });
  });

  it("should throw when both stages fail", () => {
    const input = "This is not JSON at all";
    expect(() => twoStageParse(input)).toThrow();
  });
});
