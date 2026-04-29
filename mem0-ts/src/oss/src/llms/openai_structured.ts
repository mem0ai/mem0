import OpenAI from "openai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class OpenAIStructuredLLM implements LLM {
  private openai: OpenAI;
  private model: string;
  private extraHeaders?: Record<string, string>;

  constructor(config: LLMConfig) {
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseURL,
      ...(config.timeout != null && { timeout: config.timeout }),
    });
    this.model = config.model || "gpt-5-mini";
    this.extraHeaders = config.extraHeaders;
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string } | null,
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const params = {
      messages: messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content:
          typeof msg.content === "string"
            ? msg.content
            : JSON.stringify(msg.content),
      })),
      model: this.model,
      ...(tools
        ? {
            tools: tools.map((tool) => ({
              type: "function" as const,
              function: {
                name: tool.function.name,
                description: tool.function.description,
                parameters: tool.function.parameters,
              },
            })),
            tool_choice: "auto" as const,
          }
        : responseFormat
          ? {
              response_format: {
                type: responseFormat.type as "text" | "json_object",
              },
            }
          : {}),
    };
    const completion = this.extraHeaders
      ? await this.openai.chat.completions.create(params, {
          headers: this.extraHeaders,
        })
      : await this.openai.chat.completions.create(params);

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
    const params = {
      messages: messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content:
          typeof msg.content === "string"
            ? msg.content
            : JSON.stringify(msg.content),
      })),
      model: this.model,
    };
    const completion = this.extraHeaders
      ? await this.openai.chat.completions.create(params, {
          headers: this.extraHeaders,
        })
      : await this.openai.chat.completions.create(params);
    const response = completion.choices[0].message;
    return {
      content: response.content || "",
      role: response.role,
    };
  }
}
