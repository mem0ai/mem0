import type { Ollama } from "ollama";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";
import { logger } from "../utils/logger";
import { loadPeer } from "../utils/load_peer";

export class OllamaLLM implements LLM {
  private ollama!: Ollama;
  private model: string;
  private readonly host: string;
  // Using this variable to avoid calling the Ollama server multiple times
  private initialized: boolean = false;

  constructor(config: LLMConfig) {
    this.host = config.url || config.baseURL || "http://localhost:11434";
    this.model = config.model || "llama3.1:8b";
    this.ensureModelExists().catch((err) => {
      logger.error(`Error ensuring model exists: ${err}`);
    });
  }

  private async ensureClient(): Promise<void> {
    if (this.ollama) return;
    const sdk = await loadPeer("ollama", "Ollama LLM", () => import("ollama"));
    this.ollama = new sdk.Ollama({ host: this.host });
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    await this.ensureClient();
    try {
      await this.ensureModelExists();
    } catch (err) {
      logger.error(`Error ensuring model exists: ${err}`);
    }

    const completion = await this.ollama.chat({
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
      ...(responseFormat?.type === "json_object" && { format: "json" }),
      ...(tools && { tools, tool_choice: "auto" }),
    });

    const response = completion.message;

    if (response.tool_calls) {
      return {
        content: response.content || "",
        role: response.role,
        toolCalls: response.tool_calls.map((call) => ({
          name: call.function.name,
          arguments: JSON.stringify(call.function.arguments),
        })),
      };
    }

    return response.content || "";
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    await this.ensureClient();
    try {
      await this.ensureModelExists();
    } catch (err) {
      logger.error(`Error ensuring model exists: ${err}`);
    }

    const completion = await this.ollama.chat({
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
    const response = completion.message;
    return {
      content: response.content || "",
      role: response.role,
    };
  }

  private async ensureModelExists(): Promise<boolean> {
    if (this.initialized) {
      return true;
    }
    await this.ensureClient();
    const local_models = await this.ollama.list();
    if (!local_models.models.find((m: any) => m.name === this.model)) {
      logger.info(`Pulling model ${this.model}...`);
      await this.ollama.pull({ model: this.model });
    }
    this.initialized = true;
    return true;
  }
}
