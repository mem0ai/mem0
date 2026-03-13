import { removeCodeBlocks } from "../src/prompts";

describe("removeCodeBlocks", () => {
  it("extracts JSON from ```json code fence", () => {
    const input = '```json\n{"facts": ["hello"]}\n```';
    expect(removeCodeBlocks(input)).toBe('{"facts": ["hello"]}');
  });

  it("extracts content from bare ``` code fence", () => {
    const input = '```\n{"key": "value"}\n```';
    expect(removeCodeBlocks(input)).toBe('{"key": "value"}');
  });

  it("returns plain text unchanged", () => {
    const input = '{"facts": ["hello"]}';
    expect(removeCodeBlocks(input)).toBe('{"facts": ["hello"]}');
  });

  it("handles multiple code blocks", () => {
    const input = '```json\n{"a":1}\n```\nsome text\n```json\n{"b":2}\n```';
    expect(removeCodeBlocks(input)).toBe('{"a":1}\n\nsome text\n{"b":2}');
  });

  it("handles Claude-style response with surrounding text", () => {
    const input = 'Here is the JSON:\n```json\n{"facts": ["user likes TypeScript"]}\n```';
    expect(removeCodeBlocks(input)).toContain('"facts"');
    expect(removeCodeBlocks(input)).not.toContain("```");
  });
});
