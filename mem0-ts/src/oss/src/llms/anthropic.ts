import Anthropic from "@anthropic-ai/sdk";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class AnthropicLLM implements LLM {
  private client: Anthropic;
  private model: string;

  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      throw new Error("Anthropic API key is required");
    }
    this.client = new Anthropic({ apiKey });
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
        content: msg.content,
      })),
      system: systemMessage?.content,
      max_tokens: 4096,
    });

    return response.content[0].text;
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await this.generateResponse(messages);
    return {
      content: response,
      role: "assistant",
    };
  }
}
