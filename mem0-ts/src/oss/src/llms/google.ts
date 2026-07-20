import type { GoogleGenAI } from "@google/genai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";
import { loadPeer } from "../utils/load_peer";

export class GoogleLLM implements LLM {
  private google!: GoogleGenAI;
  private model: string;
  private readonly apiKey: string | undefined;

  constructor(config: LLMConfig) {
    this.apiKey = config.apiKey;
    this.model = config.model || "gemini-2.0-flash";
  }

  private async ensureClient(): Promise<void> {
    if (this.google) return;
    const sdk = await loadPeer(
      "@google/genai",
      "Google LLM",
      () => import("@google/genai"),
    );
    this.google = new sdk.GoogleGenAI({ apiKey: this.apiKey });
  }

  private formatContents(messages: Message[]) {
    return messages.map((msg) => ({
      parts: [
        {
          text:
            typeof msg.content === "string"
              ? msg.content
              : JSON.stringify(msg.content),
        },
      ],
      role: msg.role === "system" ? "model" : "user",
    }));
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    await this.ensureClient();
    const contents = this.formatContents(messages);

    // Build config with tools if provided
    const config: Record<string, any> = {};
    if (tools && tools.length > 0) {
      config.tools = [
        {
          functionDeclarations: tools.map((tool) => ({
            name: tool.function.name,
            description: tool.function.description,
            parameters: tool.function.parameters,
          })),
        },
      ];
    }

    const completion = await this.google.models.generateContent({
      contents,
      model: this.model,
      config,
    });

    // Handle function call responses
    if (completion.functionCalls && completion.functionCalls.length > 0) {
      return {
        content: completion.text || "",
        role: "assistant",
        toolCalls: completion.functionCalls.map((call) => ({
          name: call.name!,
          arguments: JSON.stringify(call.args),
        })),
      };
    }

    const text = completion.text
      ?.replace(/^```json\n/, "")
      .replace(/\n```$/, "");

    return text || "";
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    await this.ensureClient();
    const completion = await this.google.models.generateContent({
      contents: this.formatContents(messages),
      model: this.model,
    });
    const response = completion.candidates?.[0]?.content;
    const content =
      response?.parts?.map((part) => part.text || "").join("") ||
      completion.text ||
      "";

    return {
      content,
      role: response?.role || "assistant",
    };
  }
}
