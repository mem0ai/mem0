import { GoogleGenAI } from "@google/genai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class GoogleLLM implements LLM {
  private google: GoogleGenAI;
  private model: string;

  constructor(config: LLMConfig) {
    this.google = new GoogleGenAI({ apiKey: config.apiKey });
    this.model = config.model || "gemini-2.0-flash";
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
