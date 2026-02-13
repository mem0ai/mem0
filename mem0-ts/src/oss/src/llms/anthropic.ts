import Anthropic from "@anthropic-ai/sdk";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";
import { LLM, LLMResponse, ResponseFormat } from "./base";
import { LLMConfig, Message } from "../types";

const STRUCTURED_OUTPUT_PREFIXES = [
  "claude-opus-4",
  "claude-sonnet-4",
  "claude-haiku-4",
];

export function supportsStructuredOutputs(model: string): boolean {
  return STRUCTURED_OUTPUT_PREFIXES.some((prefix) => model.startsWith(prefix));
}

export class AnthropicLLM implements LLM {
  private client: Anthropic;
  private model: string;

  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      throw new Error("Anthropic API key is required");
    }
    this.client = new Anthropic({ apiKey });
    this.model = config.model || "claude-3-sonnet-20240229";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: ResponseFormat,
  ): Promise<string> {
    // Extract system message if present
    const systemMessage = messages.find((msg) => msg.role === "system");
    const otherMessages = messages.filter((msg) => msg.role !== "system");

    const params: any = {
      model: this.model,
      messages: otherMessages.map((msg) => ({
        role: msg.role as "user" | "assistant",
        content:
          typeof msg.content === "string"
            ? msg.content
            : msg.content.image_url.url,
      })),
      system:
        typeof systemMessage?.content === "string"
          ? systemMessage.content
          : undefined,
      max_tokens: 4096,
    };

    if (responseFormat?.schema && supportsStructuredOutputs(this.model)) {
      params.output_config = {
        format: zodOutputFormat(responseFormat.schema),
      };
    }

    const response = await this.client.messages.create(params);

    const firstBlock = response.content[0];
    if (firstBlock.type === "text") {
      return firstBlock.text;
    } else {
      throw new Error("Unexpected response type from Anthropic API");
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await this.generateResponse(messages);
    return {
      content: response,
      role: "assistant",
    };
  }
}
