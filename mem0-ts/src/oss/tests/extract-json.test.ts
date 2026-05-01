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
    expect(extractJson(input)).toBe(
      "No JSON here, just some plain text response.",
    );
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

  it("strips <think> blocks from reasoning models before extracting JSON", () => {
    const input =
      "<think>\nLet me analyze the conversation carefully.\n</think>\n" +
      '{"facts": ["User lives in Tokyo"]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      facts: ["User lives in Tokyo"],
    });
  });

  it("handles <think> blocks inside code fences", () => {
    const input =
      '```json\n<think>reasoning here</think>\n{"facts": ["test"]}\n```';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["test"] });
  });

  it("strips <|end_of_text|> tokens from OpenRouter responses", () => {
    const input = '{"facts": ["test"]}<|end_of_text|>';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["test"] });
  });

  it("strips <|eot_id|> tokens from OpenRouter responses", () => {
    const input = '{"facts": ["hello"]}<|eot_id|>';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["hello"] });
  });

  it("strips <|im_end|> tokens from ChatML responses", () => {
    const input = '{"memory": [{"text": "test"}]}<|im_end|>';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ memory: [{ text: "test" }] });
  });

  it("strips multiple noise tokens", () => {
    const input =
      '<|im_start|>assistant\n{"facts": ["data"]}<|im_end|><|end_of_text|>';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["data"] });
  });

  // Issue #4737: Leading text with braces that aren't JSON
  it("handles leading text containing braces before actual JSON", () => {
    const input = 'Here\'s the {formatted} output: {"facts": ["real data"]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["real data"] });
  });

  it("handles multiple fake braces in leading text", () => {
    const input =
      "I'll format this {nicely} with {proper} structure:\n" +
      '{"memory": [{"id": "1", "text": "actual memory"}]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      memory: [{ id: "1", text: "actual memory" }],
    });
  });

  it("handles incomplete JSON-like structures in leading text", () => {
    const input =
      "Based on {user preferences} I found:\n" +
      '{"facts": ["User likes TypeScript"]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["User likes TypeScript"] });
  });

  it("validates JSON and skips malformed candidates", () => {
    const input = 'The result is {broken and {"facts": ["valid"]} is here';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({ facts: ["valid"] });
  });

  it("handles deeply nested valid JSON after invalid starts", () => {
    const input =
      "Here {is some {context}} for you:\n" +
      '{"memory": [{"nested": {"deep": "value"}}]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      memory: [{ nested: { deep: "value" } }],
    });
  });

  it("handles JSON with escaped quotes correctly", () => {
    const input =
      'Output: {"facts": ["User said \\"hello\\"", "Has a \\"test\\" project"]}';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual({
      facts: ['User said "hello"', 'Has a "test" project'],
    });
  });

  it("handles arrays with leading brace-like text", () => {
    const input = 'Here\'s {some context}. The array is: ["fact1", "fact2"]';
    const result = extractJson(input);
    expect(JSON.parse(result)).toEqual(["fact1", "fact2"]);
  });
});
