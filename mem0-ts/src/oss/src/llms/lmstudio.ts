import { LMStudioClient, Chat } from "@lmstudio/sdk";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";
import { logger } from "../utils/logger";

export class LMStudioLLM implements LLM {
  private client: LMStudioClient;
  private model: string;
  private modelHandle: any;
  private initialized: boolean = false;

  constructor(config: LLMConfig) {
    this.client = new LMStudioClient({
      baseUrl:
        config.config?.baseUrl || config.baseURL || "http://localhost:1234/v1",
    });
    this.model = config.model || "llama-3.2-1b-instruct";
    this.initializeModel();
  }

  private async initializeModel(): Promise<void> {
    if (this.initialized) {
      return;
    }

    try {
      // Get the model handle from LMStudio client
      this.modelHandle = await this.client.llm.model(this.model);
      this.initialized = true;
      logger.info(`LMStudio model ${this.model} initialized successfully`);
    } catch (error) {
      logger.error(`Error initializing LMStudio model ${this.model}: ${error}`);
      throw error;
    }
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    await this.initializeModel();

    try {
      // Convert messages to LMStudio format
      const lmStudioMessages = messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content:
          typeof msg.content === "string"
            ? msg.content
            : JSON.stringify(msg.content),
      }));

      // Create chat context
      const chat = Chat.from(lmStudioMessages);

      // Configure prediction parameters
      const predictionConfig: any = {};

      if (responseFormat?.type === "json_object") {
        predictionConfig.structured = true;
      }

      // Tools are not directly supported in the same way as OpenAI
      // LMStudio may handle tool calls differently or not at all
      if (tools) {
        logger.warn(
          "Tool calls may not be fully supported by LMStudio integration",
        );
      }

      // Generate response
      const prediction = this.modelHandle.respond(chat, predictionConfig);
      let fullContent = "";

      // Collect the streamed response
      for await (const { content } of prediction) {
        fullContent += content;
      }

      // For simple text responses
      if (!tools) {
        return fullContent;
      }

      // For tool calls (basic support)
      return {
        content: fullContent,
        role: "assistant",
        toolCalls: [], // LMStudio may not support tool calls in the same format
      };
    } catch (error) {
      logger.error(`Error generating response with LMStudio: ${error}`);
      throw error;
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    await this.initializeModel();

    try {
      // Convert messages to LMStudio format
      const lmStudioMessages = messages.map((msg) => ({
        role: msg.role as "system" | "user" | "assistant",
        content:
          typeof msg.content === "string"
            ? msg.content
            : JSON.stringify(msg.content),
      }));

      // Create chat context
      const chat = Chat.from(lmStudioMessages);

      // Generate response
      const prediction = this.modelHandle.respond(chat);
      let fullContent = "";

      // Collect the streamed response
      for await (const { content } of prediction) {
        fullContent += content;
      }

      return {
        content: fullContent,
        role: "assistant",
      };
    } catch (error) {
      logger.error(`Error generating chat response with LMStudio: ${error}`);
      throw error;
    }
  }
}
