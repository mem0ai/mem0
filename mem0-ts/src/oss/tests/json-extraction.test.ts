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

  it('should extract JSON from "Output:\\n{...}" prefix', () => {
    const input = 'Output:\n{"facts": ["Sky is blue"]}';
    expect(extractJson(input)).toBe('{"facts": ["Sky is blue"]}');
  });

  it("should extract array from text prefix", () => {
    const input = "Here is the result:\n[1,2,3]";
    expect(extractJson(input)).toBe("[1,2,3]");
  });

  it("should extract JSON from multi-line text prefix", () => {
    const input = 'Some preamble text\nMore text\n{"facts": ["Name is John"]}';
    expect(extractJson(input)).toBe('{"facts": ["Name is John"]}');
  });

  it("should prefer code fence over text-prefix when both present", () => {
    const input =
      'Output:\n```json\n{"facts": ["from fence"]}\n```\n{"facts": ["from prefix"]}';
    expect(extractJson(input)).toBe('{"facts": ["from fence"]}');
  });

  it("should return text unchanged when no JSON-like content", () => {
    const input = "This has no JSON at all";
    expect(extractJson(input)).toBe("This has no JSON at all");
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

  it("should fall back to extractJson for text-prefixed JSON", () => {
    const input = 'Output:\n{"facts": ["Sky is blue"]}';
    expect(twoStageParse(input)).toEqual({ facts: ["Sky is blue"] });
  });

  it("should throw when both stages fail", () => {
    const input = "This is not JSON at all";
    expect(() => twoStageParse(input)).toThrow();
  });
});
