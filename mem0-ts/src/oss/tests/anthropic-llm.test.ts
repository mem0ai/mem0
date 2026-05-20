/// <reference types="jest" />
/**
 * Anthropic LLM - unit tests (mocked Anthropic SDK).
 */

let capturedConstructorArgs: any;
const mockCreate = jest.fn();

jest.mock("@anthropic-ai/sdk", () => {
  return jest.fn().mockImplementation((args: any) => {
    capturedConstructorArgs = args;
    return {
      messages: { create: mockCreate },
    };
  });
});

import { AnthropicLLM } from "../src/llms/anthropic";

describe("AnthropicLLM (unit)", () => {
  const originalBaseURL = process.env.ANTHROPIC_BASE_URL;

  beforeEach(() => {
    capturedConstructorArgs = undefined;
    mockCreate.mockClear();
    delete process.env.ANTHROPIC_BASE_URL;
  });

  afterAll(() => {
    if (originalBaseURL === undefined) {
      delete process.env.ANTHROPIC_BASE_URL;
    } else {
      process.env.ANTHROPIC_BASE_URL = originalBaseURL;
    }
  });

  it("forwards baseURL to the Anthropic client constructor", () => {
    new AnthropicLLM({
      apiKey: "test-key",
      baseURL: "https://api.config.com",
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      baseURL: "https://api.config.com",
    });
  });

  it("uses ANTHROPIC_BASE_URL when config baseURL is missing", () => {
    process.env.ANTHROPIC_BASE_URL = "https://api.provider.com";

    new AnthropicLLM({ apiKey: "test-key" });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      baseURL: "https://api.provider.com",
    });
  });

  it("prefers config baseURL over ANTHROPIC_BASE_URL", () => {
    process.env.ANTHROPIC_BASE_URL = "https://api.provider.com";

    new AnthropicLLM({
      apiKey: "test-key",
      baseURL: "https://api.config.com",
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      baseURL: "https://api.config.com",
    });
  });
});
