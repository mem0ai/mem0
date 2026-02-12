/// <reference types="jest" />

jest.mock("@anthropic-ai/sdk", () => {
  return jest.fn().mockImplementation((opts: Record<string, unknown>) => ({
    _opts: opts,
    messages: {
      create: jest.fn().mockResolvedValue({
        content: [{ type: "text", text: "mock response" }],
      }),
    },
  }));
});

import Anthropic from "@anthropic-ai/sdk";
import { isOAuthToken, AnthropicLLM } from "../anthropic";

const MockedAnthropic = Anthropic as unknown as jest.Mock;

beforeEach(() => {
  MockedAnthropic.mockClear();
  delete process.env.ANTHROPIC_API_KEY;
  delete process.env.ANTHROPIC_AUTH_TOKEN;
});

describe("isOAuthToken", () => {
  it("returns true for OAT tokens", () => {
    expect(isOAuthToken("sk-ant-oat01-abc123")).toBe(true);
  });

  it("returns true for OAT tokens with different suffixes", () => {
    expect(isOAuthToken("sk-ant-oat02-xyz789")).toBe(true);
  });

  it("returns false for standard API keys", () => {
    expect(isOAuthToken("sk-ant-api03-abc123")).toBe(false);
  });

  it("returns false for arbitrary strings", () => {
    expect(isOAuthToken("some-random-key")).toBe(false);
  });
});

describe("AnthropicLLM constructor", () => {
  describe("OAT client construction", () => {
    it("uses authToken and sets apiKey to null for OAT tokens", () => {
      new AnthropicLLM({ apiKey: "sk-ant-oat01-test123" });

      expect(MockedAnthropic).toHaveBeenCalledWith(
        expect.objectContaining({
          apiKey: null,
          authToken: "sk-ant-oat01-test123",
          dangerouslyAllowBrowser: true,
        }),
      );
    });

    it("includes all five Claude Code identity headers", () => {
      new AnthropicLLM({ apiKey: "sk-ant-oat01-test123" });

      const callArgs = MockedAnthropic.mock.calls[0][0];
      const headers = callArgs.defaultHeaders;

      expect(headers).toEqual(
        expect.objectContaining({
          accept: "application/json",
          "anthropic-dangerous-direct-browser-access": "true",
          "anthropic-beta": "claude-code-20250219,oauth-2025-04-20",
          "user-agent": expect.stringMatching(
            /^claude-cli\/\d+\.\d+\.\d+ \(external, cli\)$/,
          ),
          "x-app": "cli",
        }),
      );
    });
  });

  describe("API key client construction", () => {
    it("uses apiKey param with no extra headers for standard keys", () => {
      new AnthropicLLM({ apiKey: "sk-ant-api03-test123" });

      expect(MockedAnthropic).toHaveBeenCalledWith({
        apiKey: "sk-ant-api03-test123",
      });
    });

    it("does not set authToken or dangerouslyAllowBrowser", () => {
      new AnthropicLLM({ apiKey: "sk-ant-api03-test123" });

      const callArgs = MockedAnthropic.mock.calls[0][0];
      expect(callArgs.authToken).toBeUndefined();
      expect(callArgs.dangerouslyAllowBrowser).toBeUndefined();
      expect(callArgs.defaultHeaders).toBeUndefined();
    });
  });

  describe("token resolution priority", () => {
    it("config.apiKey takes precedence over env vars", () => {
      process.env.ANTHROPIC_AUTH_TOKEN = "sk-ant-oat01-env-auth";
      process.env.ANTHROPIC_API_KEY = "sk-ant-api03-env-key";

      new AnthropicLLM({ apiKey: "sk-ant-api03-config" });

      const callArgs = MockedAnthropic.mock.calls[0][0];
      expect(callArgs.apiKey).toBe("sk-ant-api03-config");
    });

    it("ANTHROPIC_AUTH_TOKEN takes precedence over ANTHROPIC_API_KEY", () => {
      process.env.ANTHROPIC_AUTH_TOKEN = "sk-ant-oat01-env-auth";
      process.env.ANTHROPIC_API_KEY = "sk-ant-api03-env-key";

      new AnthropicLLM({});

      const callArgs = MockedAnthropic.mock.calls[0][0];
      expect(callArgs.authToken).toBe("sk-ant-oat01-env-auth");
    });

    it("falls back to ANTHROPIC_API_KEY", () => {
      process.env.ANTHROPIC_API_KEY = "sk-ant-api03-env-key";

      new AnthropicLLM({});

      const callArgs = MockedAnthropic.mock.calls[0][0];
      expect(callArgs.apiKey).toBe("sk-ant-api03-env-key");
    });
  });

  describe("missing token error", () => {
    it("throws when no token source is available", () => {
      expect(() => new AnthropicLLM({})).toThrow(
        /Anthropic API key or auth token is required/,
      );
    });

    it("error message mentions all three token sources", () => {
      expect(() => new AnthropicLLM({})).toThrow(/ANTHROPIC_AUTH_TOKEN/);
      expect(() => new AnthropicLLM({})).toThrow(/ANTHROPIC_API_KEY/);
      expect(() => new AnthropicLLM({})).toThrow(/apiKey/);
    });
  });
});
