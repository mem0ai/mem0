import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

interface OpenRouterResponse {
  choices: Array<{
    message: {
      content: string | null;
      role: string;
      tool_calls?: Array<{
        function: {
          name: string;
          arguments: string;
        };
      }>;
    };
  }>;
}

export class OpenRouterLLM implements LLM {
  private config: LLMConfig;
  private model: string;

  constructor(config: LLMConfig) {
    this.config = config;
    this.model = config.model || "anthropic/claude-3-opus-20240229";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const response = await fetch(
      "https://openrouter.ai/api/v1/chat/completions",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.config.apiKey}`,
          "Content-Type": "application/json",
          "HTTP-Referer": this.config.baseUrl || "https://mem0.ai",
        },
        body: JSON.stringify({
          model: this.model,
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
          response_format: responseFormat as { type: "text" | "json_object" },
          ...(tools && { tools, tool_choice: "auto" }),
        }),
      },
    );

    if (!response.ok) {
      throw new Error(`OpenRouter API error: ${response.statusText}`);
    }

    const data = (await response.json()) as OpenRouterResponse;
    const message = data.choices[0].message;

    if (message.tool_calls) {
      return {
        content: message.content || "",
        role: message.role,
        toolCalls: message.tool_calls.map((call) => ({
          name: call.function.name,
          arguments: call.function.arguments,
        })),
      };
    }

    return message.content || "";
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await fetch(
      "https://openrouter.ai/api/v1/chat/completions",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.config.apiKey}`,
          "Content-Type": "application/json",
          "HTTP-Referer": this.config.baseUrl || "https://mem0.ai",
        },
        body: JSON.stringify({
          model: this.model,
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
        }),
      },
    );

    if (!response.ok) {
      throw new Error(`OpenRouter API error: ${response.statusText}`);
    }

    const data = (await response.json()) as OpenRouterResponse;
    const message = data.choices[0].message;
    return {
      content: message.content || "",
      role: message.role,
    };
  }
}
