import {
  DELETE_RELATIONS_SYSTEM_PROMPT,
  getDeleteMessages,
} from "../src/graphs/utils";

/**
 * Regression tests for graph prompts.
 *
 * When response_format: { type: "json_object" } is used, OpenAI requires
 * the word "json" (case-insensitive) to appear in at least one message.
 * Missing it produces a 400 error.
 *
 * See: https://github.com/mem0ai/mem0/issues/4248
 */
describe("Graph prompts — JSON keyword requirement", () => {
  it("DELETE_RELATIONS_SYSTEM_PROMPT contains 'json'", () => {
    expect(DELETE_RELATIONS_SYSTEM_PROMPT.toLowerCase()).toContain("json");
  });

  it("getDeleteMessages includes JSON keyword in system message", () => {
    const [systemContent] = getDeleteMessages("existing data", "new data", "user-1");
    expect(systemContent.toLowerCase()).toContain("json");
  });
});
