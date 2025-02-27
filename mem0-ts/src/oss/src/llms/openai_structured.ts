import OpenAI from "openai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class OpenAIStructuredLLM implements LLM {
  private client: OpenAI;
  private model: string;

  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.OPENAI_API_KEY;
    if (!apiKey) {
      throw new Error("OpenAI API key is required");
    }
    const baseUrl = process.env.OPENAI_API_BASE || "https://api.openai.com/v1";
    this.client = new OpenAI({ apiKey, baseURL: baseUrl });
    this.model = config.model || "gpt-4-0125-preview";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
  ): Promise<string> {
    const response = await this.client.chat.completions.create({
      model: this.model,
      messages: messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content: msg.content,
      })),
      response_format: responseFormat as { type: "text" | "json_object" },
    });

    return response.choices[0].message.content || "";
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await this.client.chat.completions.create({
      model: this.model,
      messages: messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content: msg.content,
      })),
    });

    const message = response.choices[0].message;
    return {
      content: message.content || "",
      role: message.role,
    };
  }
}
