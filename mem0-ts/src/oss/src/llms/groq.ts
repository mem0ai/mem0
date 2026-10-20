import type { Groq } from "groq-sdk";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";
import { loadPeer } from "../utils/load_peer";

export class GroqLLM implements LLM {
  private client!: Groq;
  private model: string;
  private readonly apiKey: string;

  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.GROQ_API_KEY;
    if (!apiKey) {
      throw new Error("Groq API key is required");
    }
    this.apiKey = apiKey;
    this.model = config.model || "llama3-70b-8192";
  }

  private async ensureClient(): Promise<void> {
    if (this.client) return;
    const sdk = await loadPeer(
      "groq-sdk",
      "Groq LLM",
      () => import("groq-sdk"),
    );
    this.client = new sdk.Groq({ apiKey: this.apiKey });
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
  ): Promise<string> {
    await this.ensureClient();
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
    await this.ensureClient();
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
