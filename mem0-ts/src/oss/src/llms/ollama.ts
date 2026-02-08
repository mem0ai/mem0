import type { Ollama } from "ollama";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";
import { logger } from "../utils/logger";

let OllamaClient: typeof Ollama | null = null;

async function getOllamaClient(): Promise<typeof Ollama> {
  if (!OllamaClient) {
    try {
      const ollamaModule = await import("ollama");
      OllamaClient = ollamaModule.Ollama;
    } catch (error) {
      throw new Error(
        "The 'ollama' package is required to use Ollama provider. " +
          "Please install it with: npm install ollama"
      );
    }
  }
  return OllamaClient;
}

export class OllamaLLM implements LLM {
  private ollama: Ollama | null = null;
  private model: string;
  private host: string;
  // Using this variable to avoid calling the Ollama server multiple times
  private initialized: boolean = false;

  constructor(config: LLMConfig) {
    this.host = config.config?.url || "http://localhost:11434";
    this.model = config.model || "llama3.1:8b";
  }

  private async getClient(): Promise<Ollama> {
    if (!this.ollama) {
      const OllamaClass = await getOllamaClient();
      this.ollama = new OllamaClass({ host: this.host });
    }
    return this.ollama;
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const ollama = await this.getClient();
    try {
      await this.ensureModelExists(ollama);
    } catch (err) {
      logger.error(`Error ensuring model exists: ${err}`);
    }

    const completion = await ollama.chat({
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
    const ollama = await this.getClient();
    try {
      await this.ensureModelExists(ollama);
    } catch (err) {
      logger.error(`Error ensuring model exists: ${err}`);
    }

    const completion = await ollama.chat({
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

  private async ensureModelExists(ollama: Ollama): Promise<boolean> {
    if (this.initialized) {
      return true;
    }
    const local_models = await ollama.list();
    if (!local_models.models.find((m: any) => m.name === this.model)) {
      logger.info(`Pulling model ${this.model}...`);
      await ollama.pull({ model: this.model });
    }
    this.initialized = true;
    return true;
  }
}
