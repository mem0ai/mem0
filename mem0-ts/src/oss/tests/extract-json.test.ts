import { extractJson } from "../src/prompts";

describe("extractJson", () => {
  it("returns clean JSON unchanged", () => {
    const input = '{"facts": ["hello", "world"]}';
    expect(extractJson(input)).toBe('{"facts": ["hello", "world"]}');
  });

  it("extracts JSON from ```json code fence", () => {
    const input = '```json\n{"facts": ["hello"]}\n```';
    expect(extractJson(input)).toBe('{"facts": ["hello"]}');
  });

  it("extracts JSON from bare ``` code fence", () => {
    const input = '```\n{"facts": ["test"]}\n```';
    expect(extractJson(input)).toBe('{"facts": ["test"]}');
  });

  it("extracts JSON wrapped in explanation text without code fences", () => {
    const input =
      'Here are the facts I extracted:\n{"facts": ["fact1", "fact2"]}\nI hope this helps!';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["fact1", "fact2"] });
  });

  it("extracts JSON from chatty LLM response with leading text", () => {
    const input =
      'Based on the conversation, here is the JSON output:\n{"facts": ["Name is John", "Is a software engineer"]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      facts: ["Name is John", "Is a software engineer"],
    });
  });

  it("extracts JSON from chatty LLM response with trailing text", () => {
    const input =
      '{"facts": ["Loves pizza"]}\nLet me know if you need anything else!';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["Loves pizza"] });
  });

  it("extracts JSON from text with both leading and trailing explanation", () => {
    const input =
      "Sure! Here's the extracted information:\n" +
      '{"memory": [{"id": "0", "text": "Name is John", "event": "NONE"}]}\n' +
      "I've analyzed the conversation above.";
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      memory: [{ id: "0", text: "Name is John", event: "NONE" }],
    });
  });

  it("extracts JSON from code-fenced response with surrounding text", () => {
    const input =
      'Here is the JSON:\n```json\n{"facts": ["user likes TypeScript"]}\n```\nHope this helps!';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      facts: ["user likes TypeScript"],
    });
  });

  it("handles nested JSON objects", () => {
    const input =
      'The output is: {"memory": [{"id": "0", "text": "test", "event": "ADD"}]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      memory: [{ id: "0", text: "test", event: "ADD" }],
    });
  });

  it("handles multi-line JSON in chatty text", () => {
    const input = `Here are the facts:
{
  "facts": [
    "Sky is blue",
    "Grass is green"
  ]
}
That's all I found.`;
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      facts: ["Sky is blue", "Grass is green"],
    });
  });

  it("returns original text when no JSON boundaries found", () => {
    const input = "No JSON here, just some plain text response.";
    expect(extractJson(input)).toBe("No JSON here, just some plain text response.");
  });

  it("handles JSON array responses", () => {
    const input = 'The results are: ["fact1", "fact2", "fact3"]';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual(["fact1", "fact2", "fact3"]);
  });

  it("returns empty string for empty input", () => {
    expect(extractJson("")).toBe("");
  });

  it("handles truncated code block missing closing fence", () => {
    const input = '```json\n{"facts": ["hello"]}';
    expect(extractJson(input)).toBe('{"facts": ["hello"]}');
  });

  it("handles whitespace-padded JSON", () => {
    const input = '   {"facts": ["test"]}   ';
    expect(extractJson(input)).toBe('{"facts": ["test"]}');
  });

  it("handles LM Studio-style verbose response", () => {
    const input =
      "I'll analyze the conversation and extract the relevant facts.\n\n" +
      '{"facts": ["User prefers dark mode", "User uses VS Code"]}\n\n' +
      "These are the key preferences I identified from the conversation.";
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      facts: ["User prefers dark mode", "User uses VS Code"],
    });
  });

  it("handles Ollama-style response with thinking prefix", () => {
    const input =
      "Let me think about this...\n\n" +
      "After analyzing the input, here is my response:\n" +
      '{"facts": ["Has a dog named Max"]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      facts: ["Has a dog named Max"],
    });
  });
});
