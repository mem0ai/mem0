import { AzureOpenAI } from "openai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class AzureOpenAILLM implements LLM {
  private client: AzureOpenAI;
  private model: string;

  constructor(config: LLMConfig) {
    if (!config.apiKey || !config.modelProperties?.endpoint) {
      throw new Error("Azure OpenAI requires both API key and endpoint");
    }

    const { endpoint, ...rest } = config.modelProperties;

    this.client = new AzureOpenAI({
      apiKey: config.apiKey,
      endpoint: endpoint as string,
      ...rest,
    });
    this.model = config.model || "gpt-4";
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
