import OpenAI from "openai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class OpenAILLM implements LLM {
  private openai: OpenAI;
  private model: string;

  constructor(config: LLMConfig) {
    this.openai = new OpenAI({ apiKey: config.apiKey });
    this.model = config.model || "gpt-4-turbo-preview";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const completion = await this.openai.chat.completions.create({
      messages: messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content: msg.content,
      })),
      model: this.model,
      response_format: responseFormat as { type: "text" | "json_object" },
      ...(tools && { tools, tool_choice: "auto" }),
    });

    const response = completion.choices[0].message;

    if (response.tool_calls) {
      return {
        content: response.content || "",
        role: response.role,
        toolCalls: response.tool_calls.map((call) => ({
          name: call.function.name,
          arguments: call.function.arguments,
        })),
      };
    }

    return response.content || "";
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const completion = await this.openai.chat.completions.create({
      messages: messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content: msg.content,
      })),
      model: this.model,
    });
    const response = completion.choices[0].message;
    return {
      content: response.content || "",
      role: response.role,
    };
  }
}
