import Anthropic from "@anthropic-ai/sdk";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

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
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    // Extract system message if present
    const systemMessage = messages.find((msg) => msg.role === "system");
    const otherMessages = messages.filter((msg) => msg.role !== "system");

    const params: Record<string, any> = {
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

    if (tools) {
      params.tools = this._convertTools(tools);
      params.tool_choice = { type: "auto" };
    }

    const response = await this.client.messages.create(params as any);

    if (tools) {
      let content = "";
      const toolCalls: Array<{ name: string; arguments: string }> = [];
      for (const block of response.content) {
        if (block.type === "text") {
          content = block.text;
        } else if (block.type === "tool_use") {
          toolCalls.push({
            name: block.name,
            arguments: JSON.stringify(block.input),
          });
        }
      }
      return { content, role: "assistant", toolCalls };
    }

    const firstBlock = response.content[0];
    // Guard against empty content array before accessing type
    if (!firstBlock) {
      throw new Error("Empty response from Anthropic API");
    }
    if (firstBlock.type === "text") {
      return firstBlock.text;
    } else {
      throw new Error("Unexpected response type from Anthropic API");
    }
  }

  private _convertTools(tools: any[]): any[] {
    // Validate structure before mapping to catch malformed tool definitions early
    return tools.map((tool, i) => {
      if (!tool.function) {
        throw new Error(`Tool at index ${i} is missing required key 'function'`);
      }
      const { name, description, parameters } = tool.function;
      if (!name || !description || !parameters) {
        throw new Error(
          `Tool at index ${i} is missing required function keys (name, description, parameters)`,
        );
      }
      return { name, description, input_schema: parameters };
    });
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await this.generateResponse(messages);
    return {
      // generateResponse returns string when called without tools
      content: response as string,
      role: "assistant",
    };
  }
}
