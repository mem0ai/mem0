import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

/**
 * Try to import AWS SDK Bedrock Runtime client.
 * This is a peer dependency - users must install @aws-sdk/client-bedrock-runtime.
 */
let BedrockRuntimeClient: any;
let ConverseCommand: any;
let InvokeModelCommand: any;

try {
  const bedrockRuntime = require("@aws-sdk/client-bedrock-runtime");
  BedrockRuntimeClient = bedrockRuntime.BedrockRuntimeClient;
  ConverseCommand = bedrockRuntime.ConverseCommand;
  InvokeModelCommand = bedrockRuntime.InvokeModelCommand;
} catch {
  // Will throw at runtime if AWSBedrockLLM is used without the SDK installed
}

/**
 * Supported Bedrock providers.
 */
const PROVIDERS = [
  "ai21",
  "amazon",
  "anthropic",
  "cohere",
  "meta",
  "mistral",
  "stability",
  "writer",
  "deepseek",
  "gpt-oss",
  "perplexity",
  "snowflake",
  "titan",
  "command",
  "j2",
  "llama",
] as const;

type BedrockProvider = (typeof PROVIDERS)[number];

/**
 * Configuration for AWS Bedrock LLM.
 */
export interface AWSBedrockConfig extends LLMConfig {
  /** AWS region (e.g., "us-east-1") */
  region?: string;
  /** AWS credentials (optional - falls back to environment/IAM) */
  credentials?: {
    accessKeyId: string;
    secretAccessKey: string;
    sessionToken?: string;
  };
  /** Temperature for generation (0-1) */
  temperature?: number;
  /** Maximum tokens to generate */
  maxTokens?: number;
  /** Top-p sampling parameter */
  topP?: number;
}

/**
 * OpenAI-style tool definition.
 */
interface OpenAITool {
  type: "function";
  function: {
    name: string;
    description?: string;
    parameters?: {
      type: string;
      properties?: Record<string, unknown>;
      required?: string[];
    };
  };
}

/**
 * Bedrock Converse API tool format.
 */
interface BedrockTool {
  toolSpec: {
    name: string;
    description: string;
    inputSchema: {
      json: Record<string, unknown>;
    };
  };
}

/**
 * Extract provider from model identifier.
 *
 * @param model - Model identifier (e.g., "anthropic.claude-3-sonnet-20240229-v1:0")
 * @returns Provider name
 */
function extractProvider(model: string): BedrockProvider {
  for (const provider of PROVIDERS) {
    const regex = new RegExp(`\\b${provider}\\b`, "i");
    if (regex.test(model)) {
      return provider;
    }
  }
  throw new Error(`Unknown provider in model: ${model}`);
}

/**
 * AWS Bedrock LLM implementation.
 *
 * Supports all available Bedrock models with automatic provider detection.
 * Uses Converse API for anthropic/amazon models, invoke_model for others.
 *
 * @example
 * ```typescript
 * const llm = new AWSBedrockLLM({
 *   model: "anthropic.claude-3-sonnet-20240229-v1:0",
 *   region: "us-east-1",
 *   maxTokens: 2000,
 * });
 *
 * const response = await llm.generateResponse([
 *   { role: "user", content: "Hello!" }
 * ]);
 * ```
 */
export class AWSBedrockLLM implements LLM {
  private client: InstanceType<typeof BedrockRuntimeClient>;
  private model: string;
  private provider: BedrockProvider;
  private temperature: number;
  private maxTokens: number;
  private topP: number;

  /**
   * Providers that support the Converse API.
   */
  private static readonly CONVERSE_API_PROVIDERS: BedrockProvider[] = [
    "anthropic",
    "amazon",
    "meta",
    "mistral",
    "cohere",
  ];

  /**
   * Providers that support tool calling via Converse API.
   */
  private static readonly TOOL_CAPABLE_PROVIDERS: BedrockProvider[] = [
    "anthropic",
    "amazon",
    "cohere",
  ];

  constructor(config: AWSBedrockConfig) {
    if (!BedrockRuntimeClient) {
      throw new Error(
        "The '@aws-sdk/client-bedrock-runtime' package is required. " +
          "Please install it using 'npm install @aws-sdk/client-bedrock-runtime'.",
      );
    }

    this.model = config.model || "anthropic.claude-3-sonnet-20240229-v1:0";
    this.provider = extractProvider(this.model);
    this.temperature = config.temperature ?? 0.1;
    this.maxTokens = config.maxTokens ?? 2000;
    this.topP = config.topP ?? 0.9;

    const clientConfig: Record<string, unknown> = {};

    if (config.region) {
      clientConfig.region = config.region;
    }

    if (config.credentials) {
      clientConfig.credentials = {
        accessKeyId: config.credentials.accessKeyId,
        secretAccessKey: config.credentials.secretAccessKey,
        ...(config.credentials.sessionToken && {
          sessionToken: config.credentials.sessionToken,
        }),
      };
    }

    this.client = new BedrockRuntimeClient(clientConfig);
  }

  /**
   * Check if provider supports Converse API.
   */
  private supportsConverseAPI(): boolean {
    return AWSBedrockLLM.CONVERSE_API_PROVIDERS.includes(this.provider);
  }

  /**
   * Check if provider supports tool calling.
   */
  private supportsTools(): boolean {
    return AWSBedrockLLM.TOOL_CAPABLE_PROVIDERS.includes(this.provider);
  }

  /**
   * Convert OpenAI-style tools to Bedrock Converse API format.
   */
  private convertToolsToBedrockFormat(tools: OpenAITool[]): BedrockTool[] {
    return tools
      .filter((tool) => tool.type === "function" && tool.function)
      .map((tool) => ({
        toolSpec: {
          name: tool.function.name,
          description: tool.function.description || "",
          inputSchema: {
            json: tool.function.parameters || {
              type: "object",
              properties: {},
            },
          },
        },
      }));
  }

  /**
   * Format messages for Anthropic models (Converse API format).
   *
   * @returns Tuple of [formatted messages, system message or undefined]
   */
  private formatMessagesAnthropic(
    messages: Message[],
  ): [
    Array<{ role: string; content: Array<{ text: string }> }>,
    string | undefined,
  ] {
    const formattedMessages: Array<{
      role: string;
      content: Array<{ text: string }>;
    }> = [];
    let systemMessage: string | undefined;

    for (const message of messages) {
      const content =
        typeof message.content === "string"
          ? message.content
          : message.content.image_url.url;

      if (message.role === "system") {
        systemMessage = content;
      } else if (message.role === "user" || message.role === "assistant") {
        formattedMessages.push({
          role: message.role,
          content: [{ text: content }],
        });
      }
    }

    return [formattedMessages, systemMessage];
  }

  /**
   * Format messages for Amazon models (Converse API format).
   */
  private formatMessagesAmazon(
    messages: Message[],
  ): Array<{ role: string; content: Array<{ text: string }> }> {
    return messages
      .filter((msg) => msg.role !== "system")
      .map((msg) => ({
        role: msg.role as "user" | "assistant",
        content: [
          {
            text:
              typeof msg.content === "string"
                ? msg.content
                : msg.content.image_url.url,
          },
        ],
      }));
  }

  /**
   * Format messages for Meta/Mistral models (Converse API format).
   */
  private formatMessagesConverse(
    messages: Message[],
  ): Array<{ role: string; content: Array<{ text: string }> }> {
    return messages
      .filter((msg) => msg.role !== "system")
      .map((msg) => ({
        role: msg.role as "user" | "assistant",
        content: [
          {
            text:
              typeof msg.content === "string"
                ? msg.content
                : msg.content.image_url.url,
          },
        ],
      }));
  }

  /**
   * Format messages for generic invoke_model API.
   */
  private formatMessagesGeneric(messages: Message[]): string {
    const formattedParts: string[] = [];

    for (const message of messages) {
      const role = message.role.charAt(0).toUpperCase() + message.role.slice(1);
      const content =
        typeof message.content === "string"
          ? message.content
          : message.content.image_url.url;
      formattedParts.push(`\n\n${role}: ${content}`);
    }

    return "\n\nHuman: " + formattedParts.join("") + "\n\nAssistant:";
  }

  /**
   * Prepare input body for invoke_model API based on provider.
   */
  private prepareInvokeModelInput(prompt: string): Record<string, unknown> {
    switch (this.provider) {
      case "anthropic":
        return {
          messages: [
            { role: "user", content: [{ type: "text", text: prompt }] },
          ],
          max_tokens: this.maxTokens,
          temperature: this.temperature,
          top_p: this.topP,
          anthropic_version: "bedrock-2023-05-31",
        };

      case "amazon":
        if (this.model.toLowerCase().includes("nova")) {
          return {
            messages: [{ role: "user", content: prompt }],
            max_tokens: this.maxTokens,
            temperature: this.temperature,
            top_p: this.topP,
          };
        }
        // Legacy Amazon models (Titan)
        return {
          inputText: prompt,
          textGenerationConfig: {
            maxTokenCount: this.maxTokens,
            temperature: this.temperature,
            topP: this.topP,
          },
        };

      case "meta":
        return {
          prompt: prompt,
          max_gen_len: this.maxTokens,
          temperature: this.temperature,
          top_p: this.topP,
        };

      case "mistral":
        return {
          prompt: prompt,
          max_tokens: this.maxTokens,
          temperature: this.temperature,
          top_p: this.topP,
        };

      case "cohere":
        return {
          message: prompt,
          max_tokens: this.maxTokens,
          temperature: this.temperature,
          p: this.topP,
        };

      case "ai21":
        return {
          prompt: prompt,
          maxTokens: this.maxTokens,
          temperature: this.temperature,
          topP: this.topP,
        };

      default:
        return {
          prompt: prompt,
          max_tokens: this.maxTokens,
          temperature: this.temperature,
          top_p: this.topP,
        };
    }
  }

  /**
   * Parse response from invoke_model API based on provider.
   */
  private parseInvokeModelResponse(
    responseBody: Record<string, unknown>,
  ): string {
    switch (this.provider) {
      case "anthropic": {
        const content = responseBody.content as
          | Array<{ text?: string }>
          | undefined;
        return content?.[0]?.text || "";
      }

      case "amazon": {
        if (this.model.toLowerCase().includes("nova")) {
          const content = responseBody.content as
            | Array<{ text?: string }>
            | undefined;
          if (content?.[0]?.text) return content[0].text;
          return (responseBody.completion as string) || "";
        }
        // Legacy Amazon models
        return (responseBody.completion as string) || "";
      }

      case "meta":
        return (responseBody.generation as string) || "";

      case "mistral": {
        const outputs = responseBody.outputs as
          | Array<{ text?: string }>
          | undefined;
        return outputs?.[0]?.text || "";
      }

      case "cohere": {
        const generations = responseBody.generations as
          | Array<{ text?: string }>
          | undefined;
        return generations?.[0]?.text || "";
      }

      case "ai21": {
        const completions = responseBody.completions as
          | Array<{
              data?: { text?: string };
            }>
          | undefined;
        return completions?.[0]?.data?.text || "";
      }

      default: {
        // Try common response fields
        for (const field of ["content", "text", "completion", "generation"]) {
          const value = responseBody[field];
          if (Array.isArray(value) && value.length > 0) {
            return (value[0] as { text?: string })?.text || "";
          }
          if (typeof value === "string") {
            return value;
          }
        }
        return JSON.stringify(responseBody);
      }
    }
  }

  /**
   * Parse Converse API response.
   */
  private parseConverseResponse(
    response: Record<string, unknown>,
    tools?: OpenAITool[],
  ): string | LLMResponse {
    const output = response.output as
      | {
          message?: {
            content?: Array<{
              text?: string;
              toolUse?: { name: string; input: unknown };
            }>;
          };
        }
      | undefined;
    const content = output?.message?.content;

    if (!content || content.length === 0) {
      return "";
    }

    // Check for tool calls
    if (tools && tools.length > 0) {
      const toolCalls: Array<{ name: string; arguments: string }> = [];
      let textContent = "";

      for (const block of content) {
        if (block.toolUse) {
          toolCalls.push({
            name: block.toolUse.name,
            arguments: JSON.stringify(block.toolUse.input),
          });
        } else if (block.text) {
          textContent = block.text;
        }
      }

      if (toolCalls.length > 0) {
        return {
          content: textContent,
          role: "assistant",
          toolCalls,
        };
      }
    }

    // Return text content
    return content[0]?.text || "";
  }

  /**
   * Generate response using Converse API.
   */
  private async generateWithConverseAPI(
    messages: Message[],
    tools?: OpenAITool[],
  ): Promise<string | LLMResponse> {
    let formattedMessages: Array<{
      role: string;
      content: Array<{ text: string }>;
    }>;
    let systemMessage: string | undefined;

    if (this.provider === "anthropic") {
      [formattedMessages, systemMessage] =
        this.formatMessagesAnthropic(messages);
    } else if (this.provider === "amazon") {
      formattedMessages = this.formatMessagesAmazon(messages);
    } else {
      formattedMessages = this.formatMessagesConverse(messages);
    }

    const converseParams: Record<string, unknown> = {
      modelId: this.model,
      messages: formattedMessages,
      inferenceConfig: {
        maxTokens: this.maxTokens,
        temperature: this.temperature,
        topP: this.topP,
      },
    };

    // Add system message for Anthropic
    if (systemMessage) {
      converseParams.system = [{ text: systemMessage }];
    }

    // Add tool config if tools are provided and supported
    if (tools && tools.length > 0 && this.supportsTools()) {
      const bedrockTools = this.convertToolsToBedrockFormat(tools);
      if (bedrockTools.length > 0) {
        converseParams.toolConfig = { tools: bedrockTools };
      }
    }

    const command = new ConverseCommand(converseParams);
    const response = await this.client.send(command);

    return this.parseConverseResponse(
      response as Record<string, unknown>,
      tools,
    );
  }

  /**
   * Generate response using invoke_model API.
   */
  private async generateWithInvokeModelAPI(
    messages: Message[],
  ): Promise<string> {
    const prompt = this.formatMessagesGeneric(messages);
    const inputBody = this.prepareInvokeModelInput(prompt);

    const command = new InvokeModelCommand({
      modelId: this.model,
      body: JSON.stringify(inputBody),
      accept: "application/json",
      contentType: "application/json",
    });

    const response = await this.client.send(command);

    // Parse response body
    const responseBody = JSON.parse(
      new TextDecoder().decode(response.body),
    ) as Record<string, unknown>;

    return this.parseInvokeModelResponse(responseBody);
  }

  /**
   * Generate a response from the LLM.
   *
   * @param messages - Array of messages in the conversation
   * @param responseFormat - Optional response format specification
   * @param tools - Optional array of tools for function calling
   * @returns Generated response (string or LLMResponse with tool calls)
   */
  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: OpenAITool[],
  ): Promise<string | LLMResponse> {
    // Use Converse API for supported providers or when tools are needed
    if (this.supportsConverseAPI() || (tools && this.supportsTools())) {
      return this.generateWithConverseAPI(messages, tools);
    }

    // Fall back to invoke_model API
    return this.generateWithInvokeModelAPI(messages);
  }

  /**
   * Generate a chat response (without tool support).
   *
   * @param messages - Array of messages in the conversation
   * @returns LLMResponse with content and role
   */
  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const response = await this.generateResponse(messages);

    if (typeof response === "string") {
      return {
        content: response,
        role: "assistant",
      };
    }

    return response;
  }
}
