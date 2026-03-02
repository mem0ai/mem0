import Anthropic from "@anthropic-ai/sdk";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

const CLAUDE_CODE_VERSION = "2.1.2";

const OAT_HEADERS = {
  accept: "application/json",
  "anthropic-dangerous-direct-browser-access": "true",
  "anthropic-beta": "claude-code-20250219,oauth-2025-04-20",
  "user-agent": `claude-cli/${CLAUDE_CODE_VERSION} (external, cli)`,
  "x-app": "cli",
};

export function isOAuthToken(token: string): boolean {
  return token.includes("sk-ant-oat");
}

export class AnthropicLLM implements LLM {
  private client: Anthropic;
  private model: string;

  constructor(config: LLMConfig) {
    const token =
      config.apiKey ||
      process.env.ANTHROPIC_AUTH_TOKEN ||
      process.env.ANTHROPIC_API_KEY;

    if (!token) {
      throw new Error(
        "Anthropic API key or auth token is required. " +
          "Set apiKey in config, or ANTHROPIC_AUTH_TOKEN / ANTHROPIC_API_KEY env var.",
      );
    }

    if (isOAuthToken(token)) {
      this.client = new Anthropic({
        apiKey: null,
        authToken: token,
        defaultHeaders: OAT_HEADERS,
        dangerouslyAllowBrowser: true,
      });
    } else {
      this.client = new Anthropic({ apiKey: token });
    }

    this.model = config.model || "claude-3-sonnet-20240229";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
  ): Promise<string> {
    // Extract system message if present
    const systemMessage = messages.find((msg) => msg.role === "system");
    const otherMessages = messages.filter((msg) => msg.role !== "system");

    const response = await this.client.messages.create({
      model: this.model,
      messages: otherMessages.map((msg) => ({
        role: msg.role as "user" | "assistant",
        content:
          typeof msg.content === "string"
            ? msg.content
            : msg.content.image_url.url,
      })),
      system:
        typeof systemMessage?.content === "string"
          ? systemMessage.content
          : undefined,
      max_tokens: 4096,
    });

    const firstBlock = response.content[0];
    if (firstBlock.type === "text") {
      return firstBlock.text;
    } else {
      throw new Error("Unexpected response type from Anthropic API");
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await this.generateResponse(messages);
    return {
      content: response,
      role: "assistant",
    };
  }
}
