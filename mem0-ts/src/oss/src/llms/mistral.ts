import { Mistral } from "@mistralai/mistralai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class MistralLLM implements LLM {
  private client: Mistral;
  private model: string;

  constructor(config: LLMConfig) {
    if (!config.apiKey) {
      throw new Error("Mistral API key is required");
    }
    this.client = new Mistral({
      apiKey: config.apiKey,
    });
    this.model = config.model || "mistral-tiny-latest";
  }

  // Helper function to convert content to string
  private contentToString(content: any): string {
    if (typeof content === "string") {
      return content;
    }
    if (Array.isArray(content)) {
      // Handle ContentChunk array - extract text content
      return content
        .map((chunk) => {
          if (chunk.type === "text") {
            return chunk.text;
          } else {
            return JSON.stringify(chunk);
          }
        })
        .join("");
    }
    return String(content || "");
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const response = await this.client.chat.complete({
      model: this.model,
      messages: messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content:
          typeof msg.content === "string"
            ? msg.content
            : JSON.stringify(msg.content),
      })),
      ...(tools && { tools }),
      ...(responseFormat && { response_format: responseFormat }),
    });

    if (!response || !response.choices || response.choices.length === 0) {
      return "";
    }

    const message = response.choices[0].message;

    if (!message) {
      return "";
    }

    if (message.toolCalls && message.toolCalls.length > 0) {
      return {
        content: this.contentToString(message.content),
        role: message.role || "assistant",
        toolCalls: message.toolCalls.map((call) => ({
          name: call.function.name,
          arguments:
            typeof call.function.arguments === "string"
              ? call.function.arguments
              : JSON.stringify(call.function.arguments),
        })),
      };
    }

    return this.contentToString(message.content);
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const formattedMessages = messages.map((msg) => ({
      role: msg.role as "system" | "user" | "assistant",
      content:
        typeof msg.content === "string"
          ? msg.content
          : JSON.stringify(msg.content),
    }));

    const response = await this.client.chat.complete({
      model: this.model,
      messages: formattedMessages,
    });

    if (!response || !response.choices || response.choices.length === 0) {
      return {
        content: "",
        role: "assistant",
      };
    }

    const message = response.choices[0].message;

    return {
      content: this.contentToString(message.content),
      role: message.role || "assistant",
    };
  }
}
