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

  private formatContents(messages: Message[]): {
    systemInstruction?: string;
    contents: Array<{ parts: Array<{ text: string }>; role: string }>;
  } {
    let systemInstruction: string | undefined;
    const contents: Array<{ parts: Array<{ text: string }>; role: string }> =
      [];

    for (const msg of messages) {
      const text =
        typeof msg.content === "string"
          ? msg.content
          : JSON.stringify(msg.content);

      // Gemini takes the system prompt via `systemInstruction`, not as a
      // content turn. Mapping it to a "model" turn (as this used to) mislabels
      // the extraction instructions as something the model already said, and
      // leaves the conversation without a leading user turn. Mirrors the Python
      // SDK's _reformat_messages (mem0/llms/gemini.py); last system wins.
      if (msg.role === "system") {
        systemInstruction = text;
        continue;
      }

      // Gemini's content roles are "user" and "model"; assistant turns are
      // "model". Previously assistant was mislabeled "user".
      contents.push({
        parts: [{ text }],
        role: msg.role === "assistant" ? "model" : "user",
      });
    }

    return { systemInstruction, contents };
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    await this.ensureClient();
    const { systemInstruction, contents } = this.formatContents(messages);

    // Build config with tools if provided
    const config: Record<string, any> = {};
    if (systemInstruction) {
      config.systemInstruction = systemInstruction;
    }
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

    // Honor a requested JSON response format (parity with the Python SDK's
    // mem0/llms/gemini.py). Gemini's structured output is opt-in via
    // responseMimeType — without it the model is never told to emit JSON, so
    // callers passing json_object silently get free-form text and depend on a
    // fragile markdown-fence strip downstream.
    if (responseFormat?.type === "json_object") {
      config.responseMimeType = "application/json";
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
    const { systemInstruction, contents } = this.formatContents(messages);
    const config: Record<string, any> = {};
    if (systemInstruction) {
      config.systemInstruction = systemInstruction;
    }
    const completion = await this.google.models.generateContent({
      contents,
      model: this.model,
      config,
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
