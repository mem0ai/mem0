import type Anthropic from "@anthropic-ai/sdk";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";
import { loadPeer } from "../utils/load_peer";
import { extractJson } from "../prompts";

export class AnthropicLLM implements LLM {
  private client!: Anthropic;
  private readonly clientArgs: { apiKey: string; baseURL?: string };
  private model: string;
  private maxTokens: number;
  private temperature?: number;
  private topP?: number;

  constructor(config: LLMConfig) {
    const apiKey = config.apiKey || process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      throw new Error("Anthropic API key is required");
    }
    // Forward baseURL to the client when set so proxy/gateway users are
    // honored (parity with the OpenAI provider and the Python fix in #5626).
    const clientArgs: { apiKey: string; baseURL?: string } = { apiKey };
    if (config.baseURL) {
      clientArgs.baseURL = config.baseURL;
    }
    this.clientArgs = clientArgs;
    this.model = config.model || "claude-sonnet-4-6";
    // Defaults mirror the Python provider's AnthropicConfig
    // (max_tokens=2000, temperature=0.1, top_p omitted).
    this.maxTokens = config.maxTokens ?? 2000;
    this.temperature = config.temperature ?? 0.1;
    this.topP = config.topP;
  }

  private async ensureClient(): Promise<void> {
    if (this.client) return;
    const sdk = await loadPeer(
      "@anthropic-ai/sdk",
      "Anthropic LLM",
      () => import("@anthropic-ai/sdk"),
    );
    this.client = new sdk.default(this.clientArgs);
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string; json_schema?: any },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    await this.ensureClient();
    // Extract system message if present
    const systemMessage = messages.find((msg) => msg.role === "system");
    const otherMessages = messages.filter((msg) => msg.role !== "system");

    const params: Anthropic.MessageCreateParamsNonStreaming = {
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
      max_tokens: this.maxTokens,
    };

    // Anthropic rejects requests that include both temperature and top_p;
    // prefer temperature, matching the Python provider's _get_common_params.
    if (this.temperature !== undefined) {
      params.temperature = this.temperature;
    } else if (this.topP !== undefined) {
      params.top_p = this.topP;
    }

    if (tools) {
      params.tools = tools;
      params.tool_choice = { type: "auto" };
    }

    // Anthropic has no native response_format param, so translate the shared
    // interface here (parity with the Python provider, #5820 / #6203).
    // response_format is intentionally ignored when tools are active: the
    // tool_use handling below takes precedence, and the JSON prefill would
    // otherwise drop tool_use blocks.
    let wantsJsonPrefill = false;
    if (responseFormat && !tools) {
      if (responseFormat.type === "json_schema" && responseFormat.json_schema) {
        let schema = responseFormat.json_schema;
        if (schema && typeof schema === "object" && "schema" in schema) {
          schema = schema.schema;
        }
        // output_config is newer than the pinned @anthropic-ai/sdk types.
        (params as unknown as { output_config: unknown }).output_config = {
          format: { type: "json_schema", schema },
        };
      } else if (responseFormat.type === "json_object") {
        wantsJsonPrefill = true;
        params.system =
          (params.system ?? "") +
          "\n\nYou must respond with valid JSON only. Do not include any " +
          "other text, markdown formatting, or code fences.";
        // Prefill the assistant turn with "{" so the model continues a JSON
        // object; the leading brace is added back when reconstructing below.
        params.messages = [
          ...params.messages,
          { role: "assistant", content: "{" },
        ];
      }
    }

    const response = await this.client.messages.create(params);

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

    if (wantsJsonPrefill) {
      const text = this.firstTextBlock(response);
      // No text block means there was nothing to continue the prefill with,
      // so don't hand back a bare "{" that no parser can use.
      if (!text) {
        return "";
      }
      // Re-attach the "{" prefill that was sent as the assistant turn.
      return extractJson("{" + text);
    }

    return this.firstTextBlock(response);
  }

  // Thinking-enabled responses put a thinking block before the text block, and
  // a response can carry no text block at all, so find the text block like the
  // tools branch does instead of indexing content[0] (#6506, mirroring the
  // Python provider in #6481).
  private firstTextBlock(response: Anthropic.Message): string {
    for (const block of response.content) {
      if (block.type === "text") {
        return block.text;
      }
    }
    return "";
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await this.generateResponse(messages);
    if (typeof response === "string") {
      return { content: response, role: "assistant" };
    }
    return response;
  }
}
