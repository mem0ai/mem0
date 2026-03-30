import OpenAI from "openai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class DeepSeekLLM implements LLM {
  private client: OpenAI;
  private model: string;

  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.DEEPSEEK_API_KEY;
    if (!apiKey) {
      throw new Error("DeepSeek API key is required");
    }
    const baseURL =
      config.baseURL ||
      process.env.DEEPSEEK_API_BASE ||
      "https://api.deepseek.com/v1";

    this.client = new OpenAI({ apiKey, baseURL });
    this.model = config.model || "deepseek-chat";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const completion = await this.client.chat.completions.create({
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
    const completion = await this.client.chat.completions.create({
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
    return {
      content: response.content || "",
      role: response.role,
    };
  }
}
