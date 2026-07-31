import OpenAI from "openai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class OpenAILLM implements LLM {
  private openai: OpenAI;
  private model: string;

  constructor(config: LLMConfig) {
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseURL,
      ...(config.timeout != null && { timeout: config.timeout }),
    });
    this.model = config.model || "gpt-5-mini";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const completion = await this.openai.chat.completions.create({
      messages: messages.map((msg) => {
        const role = msg.role as "system" | "user" | "assistant";
        return {
          role,
          content:
            typeof msg.content === "string"
              ? msg.content
              : JSON.stringify(msg.content),
        };
      }),
      model: this.model,
      response_format: responseFormat as { type: "text" | "json_object" },
      ...(tools && { tools, tool_choice: "auto" }),
    });

    const response = completion.choices[0].message;
    const textContent =
      response.content ||
      // OpenAI-compatible reasoning models may put the answer in reasoning_content (#4932)
      ((response as { reasoning_content?: string | null }).reasoning_content ??
        "");

    if (response.tool_calls) {
      return {
        content: textContent,
        role: response.role,
        toolCalls: response.tool_calls.map((call) => ({
          name: call.function.name,
          arguments: call.function.arguments,
        })),
      };
    }

    return textContent;
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const completion = await this.openai.chat.completions.create({
      messages: messages.map((msg) => {
        const role = msg.role as "system" | "user" | "assistant";
        return {
          role,
          content:
            typeof msg.content === "string"
              ? msg.content
              : JSON.stringify(msg.content),
        };
      }),
      model: this.model,
    });
    const response = completion.choices[0].message;
    const textContent =
      response.content ||
      ((response as { reasoning_content?: string | null }).reasoning_content ??
        "");
    return {
      content: textContent,
      role: response.role,
    };
  }
}
