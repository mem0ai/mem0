import Anthropic from "@anthropic-ai/sdk";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class AnthropicLLM implements LLM {
  private client: Anthropic;
  private model: string;
  private maxTokens: number;
  private temperature?: number;
  private topP?: number;

  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      throw new Error("Anthropic API key is required");
    }
    this.client = new Anthropic({ apiKey });
    this.model = config.model || "claude-sonnet-4-6";
    // Defaults mirror the Python provider's AnthropicConfig
    // (max_tokens=2000, temperature=0.1, top_p omitted).
    this.maxTokens = config.maxTokens ?? 2000;
    this.temperature = config.temperature ?? 0.1;
    this.topP = config.topP;
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    // Extract system message if present
    const systemMessage = messages.find((msg) => msg.role === "system");
    const otherMessages = messages.filter((msg) => msg.role !== "system");

    const params: Anthropic.MessageCreateParamsNonStreaming = {
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
      max_tokens: this.maxTokens,
    };

    // Anthropic rejects requests that include both temperature and top_p;
    // prefer temperature, matching the Python provider's _get_common_params.
    if (this.temperature !== undefined) {
      params.temperature = this.temperature;
    } else if (this.topP !== undefined) {
      params.top_p = this.topP;
    }

    if (tools) {
      params.tools = tools;
      params.tool_choice = { type: "auto" };
    }

    const response = await this.client.messages.create(params);

    if (tools) {
      let content = "";
      const toolCalls: Array<{ name: string; arguments: string }> = [];

      for (const block of response.content) {
        if (block.type === "text") {
          content = block.text;
        } else if (block.type === "tool_use") {
          toolCalls.push({
            name: block.name,
            arguments: JSON.stringify(block.input),
          });
        }
      }

      return { content, role: "assistant", toolCalls };
    }

    const firstBlock = response.content[0];
    if (firstBlock.type === "text") {
      return firstBlock.text;
    } else {
      throw new Error("Unexpected response type from Anthropic API");
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await this.generateResponse(messages);
    if (typeof response === "string") {
      return { content: response, role: "assistant" };
    }
    return response;
  }
}
