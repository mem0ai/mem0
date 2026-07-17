import { Ollama } from "ollama";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";
import { logger } from "../utils/logger";

export class OllamaLLM implements LLM {
  private ollama: Ollama;
  private model: string;
  private config: LLMConfig;
  // Using this variable to avoid calling the Ollama server multiple times
  private initialized: boolean = false;

  constructor(config: LLMConfig) {
    this.config = config;
    this.ollama = new Ollama({
      host: config.url || config.baseURL || "http://localhost:11434",
    });
    this.model = config.model || "llama3.1:8b";
    this.ensureModelExists().catch((err) => {
      logger.error(`Error ensuring model exists: ${err}`);
    });
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    try {
      await this.ensureModelExists();
    } catch (err) {
      logger.error(`Error ensuring model exists: ${err}`);
    }

    const modelProps = this.config?.modelProperties ?? {};
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
      ...modelProps,
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
    const local_models = await this.ollama.list();
    if (!local_models.models.find((m: any) => m.name === this.model)) {
      logger.info(`Pulling model ${this.model}...`);
      try {
        await this.ollama.pull({ model: this.model });
      } catch (err) {
        logger.warn(
          `Failed to pull model ${this.model}: ${err}. ` +
            `If the model is already available, this error can be safely ignored.`,
        );
      }
    }
    this.initialized = true;
    return true;
  }
}
