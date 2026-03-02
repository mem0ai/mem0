import { GoogleGenAI, Type } from "@google/genai";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

export class GoogleLLM implements LLM {
  private google: GoogleGenAI;
  private model: string;

  constructor(config: LLMConfig) {
    this.google = new GoogleGenAI({ apiKey: config.apiKey });
    this.model = config.model || "gemini-2.0-flash";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const completion = await this.google.models.generateContent({
      contents: messages.map((msg) => ({
        parts: [
          {
            text:
              typeof msg.content === "string"
                ? msg.content
                : JSON.stringify(msg.content),
          },
        ],
        role: msg.role === "system" ? "model" : "user",
      })),
      model: this.model,
      config: {
        ...(tools && {
          tools: [
            {
              functionDeclarations: tools.map((tool) => ({
                name: tool.function.name,
                description: tool.function.description,
                parameters: tool.function.parameters,
              })),
            },
          ],
        }),
      },
    });

    const candidate = completion.candidates?.[0];
    const parts = candidate?.content?.parts || [];

    const functionCalls = parts.filter((part) => part.functionCall);
    const textParts = parts.filter((part) => part.text);

    // Extract text content from text parts
    const textContent = textParts.map((part) => part.text).join("");

    // Clean up markdown JSON formatting if present
    const cleanText = textContent
      ?.replace(/^```json\n/, "")
      .replace(/\n```$/, "");

    if (functionCalls?.length) {
      return {
        content: cleanText,
        role: "assistant",
        toolCalls: functionCalls.map((part: any) => ({
          name: part.functionCall.name,
          arguments: JSON.stringify(part.functionCall.args || {}),
        })),
      };
    }

    return cleanText;
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const completion = await this.google.models.generateContent({
      contents: messages,
      model: this.model,
    });
    const response = completion.candidates![0].content;
    return {
      content: response!.parts![0].text || "",
      role: response!.role!,
    };
  }
}
