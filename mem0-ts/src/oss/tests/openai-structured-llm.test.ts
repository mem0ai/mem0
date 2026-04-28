/// <reference types="jest" />
/**
 * OpenAI Structured LLM — unit tests (mocked openai).
 *
 * Sibling fix for #4707: OpenAIStructuredLLM had the same timeout gap.
 */

let capturedConstructorArgs: any;
const mockCreate = jest.fn();

jest.mock("openai", () => {
  return jest.fn().mockImplementation((args: any) => {
    capturedConstructorArgs = args;
    return {
      chat: { completions: { create: mockCreate } },
    };
  });
});

import { OpenAIStructuredLLM } from "../src/llms/openai_structured";

describe("OpenAIStructuredLLM (unit)", () => {
  beforeEach(() => {
    capturedConstructorArgs = undefined;
    mockCreate.mockClear();
  });

  it("forwards timeout to the OpenAI client constructor", () => {
    new OpenAIStructuredLLM({
      apiKey: "test-key",
      timeout: 15000,
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      timeout: 15000,
    });
  });

  it("forwards timeout: 0 to the OpenAI client (explicit zero is valid)", () => {
    new OpenAIStructuredLLM({
      apiKey: "test-key",
      timeout: 0,
    });

    expect(capturedConstructorArgs.timeout).toBe(0);
  });

  it("omits timeout from the OpenAI client when not configured", () => {
    new OpenAIStructuredLLM({
      apiKey: "test-key",
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
    });
    expect(capturedConstructorArgs).not.toHaveProperty("timeout");
  });

  it("passes extraHeaders as request headers for structured chat completions", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: {
            content: '{"ok": true}',
            role: "assistant",
            tool_calls: null,
          },
        },
      ],
    });

    const llm = new OpenAIStructuredLLM({
      apiKey: "test-key",
      extraHeaders: { "Helicone-Auth": "Bearer test" },
    });
    await llm.generateResponse([{ role: "user", content: "Hi" }], {
      type: "json_object",
    });

    expect(mockCreate).toHaveBeenCalledWith(expect.any(Object), {
      headers: { "Helicone-Auth": "Bearer test" },
    });
  });
});
