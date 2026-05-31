import { Groq } from "groq-sdk";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class GroqLLM implements LLM {
  private client: Groq;
  private model: string;

  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.GROQ_API_KEY;
    if (!apiKey) {
      throw new Error("Groq API key is required");
    }
    this.client = new Groq({ apiKey });
    this.model = config.model || "llama3-70b-8192";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
  ): Promise<string> {
    const response = await this.client.chat.completions.create({
      model: this.model,
      messages: messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content:
          typeof msg.content === "string"
            ? msg.content
            : JSON.stringify(msg.content),
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
        content:
          typeof msg.content === "string"
            ? msg.content
            : JSON.stringify(msg.content),
      })),
    });

    const message = response.choices[0].message;
    return {
      content: message.content || "",
      role: message.role,
    };
  }
}
