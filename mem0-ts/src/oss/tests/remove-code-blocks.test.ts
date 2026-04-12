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
    const input =
      'Here is the JSON:\n```json\n{"facts": ["user likes TypeScript"]}\n```';
    expect(removeCodeBlocks(input)).toContain('"facts"');
    expect(removeCodeBlocks(input)).not.toContain("```");
  });

  // Truncated LLM response cases (issue #4401)
  it("handles truncated code block missing closing fence", () => {
    const input = '```json\n{"facts": ["hello"]}';
    expect(removeCodeBlocks(input)).toBe('{"facts": ["hello"]}');
  });

  it("handles truncated code block with incomplete JSON", () => {
    const input = '```json\n{"key": "value"';
    expect(removeCodeBlocks(input)).toBe('{"key": "value"');
  });

  it("handles orphan trailing fence", () => {
    const input = '{"result": true}\n```';
    expect(removeCodeBlocks(input)).toBe('{"result": true}');
  });

  it("handles truncated block with bare fence (no language tag)", () => {
    const input = '```\n{"facts": ["test"]}';
    expect(removeCodeBlocks(input)).toBe('{"facts": ["test"]}');
  });

  it("handles complete block followed by truncated block", () => {
    const input = '```json\n{"a":1}\n```\nsome text\n```python\nprint("hi")';
    const result = removeCodeBlocks(input);
    expect(result).toContain('{"a":1}');
    expect(result).toContain('print("hi")');
    expect(result).not.toMatch(/^```/);
  });

  it("returns empty string for empty input", () => {
    expect(removeCodeBlocks("")).toBe("");
  });

  it("handles CRLF line endings from LLM proxies", () => {
    const input = '```json\r\n{"facts": ["hello"]}\r\n```';
    expect(removeCodeBlocks(input)).toBe('{"facts": ["hello"]}');
  });

  it("strips <think> blocks from reasoning models", () => {
    const input =
      '<think>Let me analyze this conversation...</think>\n{"facts": ["Name is John"]}';
    expect(removeCodeBlocks(input)).toBe('{"facts": ["Name is John"]}');
  });

  it("strips <think> blocks inside code fences", () => {
    const input =
      '```json\n<think>thinking about it</think>\n{"facts": ["test"]}\n```';
    expect(removeCodeBlocks(input)).toBe('{"facts": ["test"]}');
  });

  it("strips multi-line <think> blocks", () => {
    const input =
      "<think>\nStep 1: Read the conversation\nStep 2: Extract facts\n</think>\n" +
      '{"facts": ["Likes pizza"]}';
    expect(removeCodeBlocks(input)).toBe('{"facts": ["Likes pizza"]}');
  });
});
