import type {
  BedrockRuntimeClient,
  ContentBlock,
  ConverseCommandInput,
  Message as BedrockMessage,
  Tool as BedrockTool,
} from "@aws-sdk/client-bedrock-runtime";
import { LLM, LLMResponse } from "./base";
import { AWSBedrockConfig, Message } from "../types";

type BedrockSDK = typeof import("@aws-sdk/client-bedrock-runtime");

// Providers that reject requests including both `temperature` and `topP` in
// `inferenceConfig`. Mirrors the Python provider's `_build_inference_config`.
const TOP_P_INCOMPATIBLE_PROVIDERS = new Set(["anthropic", "minimax"]);

// Cross-region inference profile prefixes that precede the real provider
// segment in a model id (e.g. `us.anthropic.claude-...`).
const REGION_PREFIXES = new Set(["us", "eu", "apac", "global"]);

function extractProvider(model: string): string {
  const parts = model.split(".");
  if (parts.length >= 2 && REGION_PREFIXES.has(parts[0])) {
    return parts[1];
  }
  return parts[0];
}

export class AWSBedrockLLM implements LLM {
  private clientArgs: NonNullable<
    ConstructorParameters<typeof BedrockRuntimeClient>[0]
  >;
  private client?: BedrockRuntimeClient;
  private model: string;
  private provider: string;
  private maxTokens: number;
  private temperature?: number;
  private topP?: number;

  constructor(config: AWSBedrockConfig = {}) {
    // Support both top-level fields and a nested `config` record (used by the
    // Python SDK / OpenClaw config shape).
    const nested = (config.config || {}) as Record<string, any>;
    const region =
      config.awsRegion ??
      nested.awsRegion ??
      nested.region ??
      process.env.AWS_REGION ??
      process.env.AWS_DEFAULT_REGION;

    const clientArgs: NonNullable<
      ConstructorParameters<typeof BedrockRuntimeClient>[0]
    > = {};
    if (region) {
      clientArgs.region = region;
    }
    // Explicit credentials are optional. When omitted, the AWS SDK falls back
    // to its default credential provider chain (env vars, shared config,
    // instance/role credentials).
    const accessKeyId =
      config.awsAccessKeyId ??
      nested.awsAccessKeyId ??
      process.env.AWS_ACCESS_KEY_ID;
    const secretAccessKey =
      config.awsSecretAccessKey ??
      nested.awsSecretAccessKey ??
      process.env.AWS_SECRET_ACCESS_KEY;
    if (accessKeyId && secretAccessKey) {
      clientArgs.credentials = {
        accessKeyId,
        secretAccessKey,
        sessionToken:
          config.awsSessionToken ??
          nested.awsSessionToken ??
          process.env.AWS_SESSION_TOKEN,
      };
    }
    this.clientArgs = clientArgs;

    this.model =
      (typeof config.model === "string" ? config.model : undefined) ||
      "anthropic.claude-3-5-sonnet-20240620-v1:0";
    this.provider = extractProvider(this.model);
    // Defaults mirror the Python provider's AWSBedrockConfig
    // (max_tokens=2000, temperature=0.1, top_p omitted).
    this.maxTokens = config.maxTokens ?? 2000;
    this.temperature = config.temperature ?? 0.1;
    this.topP = config.topP;
  }

  // The AWS SDK is an optional peer dependency; import it lazily so users who
  // don't use Bedrock aren't forced to install it (parity with the Vertex AI
  // and Valkey providers).
  private async getSDK(): Promise<BedrockSDK> {
    try {
      return await import("@aws-sdk/client-bedrock-runtime");
    } catch (error) {
      throw new Error(
        "Failed to import '@aws-sdk/client-bedrock-runtime'. Please install it to use the AWS Bedrock provider: " +
          (error as Error).message,
      );
    }
  }

  private async getClient(): Promise<BedrockRuntimeClient> {
    if (!this.client) {
      const sdk = await this.getSDK();
      this.client = new sdk.BedrockRuntimeClient(this.clientArgs);
    }
    return this.client;
  }

  private buildInferenceConfig(): ConverseCommandInput["inferenceConfig"] {
    const inferenceConfig: NonNullable<
      ConverseCommandInput["inferenceConfig"]
    > = {
      maxTokens: this.maxTokens,
    };
    if (this.temperature !== undefined) {
      inferenceConfig.temperature = this.temperature;
    }
    // Anthropic and MiniMax reasoning models raise a ValidationException when
    // both temperature and topP are present. Prefer temperature for those.
    if (
      this.topP !== undefined &&
      !(
        TOP_P_INCOMPATIBLE_PROVIDERS.has(this.provider) &&
        this.temperature !== undefined
      )
    ) {
      inferenceConfig.topP = this.topP;
    }
    return inferenceConfig;
  }

  private toBedrockMessages(messages: Message[]): {
    system?: { text: string }[];
    messages: BedrockMessage[];
  } {
    const system: { text: string }[] = [];
    const converseMessages: BedrockMessage[] = [];

    for (const msg of messages) {
      const content =
        typeof msg.content === "string"
          ? msg.content
          : JSON.stringify(msg.content);
      if (msg.role === "system") {
        system.push({ text: content });
      } else {
        converseMessages.push({
          role: msg.role === "assistant" ? "assistant" : "user",
          content: [{ text: content }],
        });
      }
    }

    if (converseMessages.length === 0) {
      converseMessages.push({ role: "user", content: [{ text: "" }] });
    }

    return {
      system: system.length > 0 ? system : undefined,
      messages: converseMessages,
    };
  }

  private toToolConfig(
    tools?: any[],
  ): ConverseCommandInput["toolConfig"] | undefined {
    if (!tools || tools.length === 0) {
      return undefined;
    }
    const converseTools: BedrockTool[] = [];
    for (const tool of tools) {
      if (tool.type === "function" && tool.function) {
        const fn = tool.function;
        converseTools.push({
          toolSpec: {
            name: fn.name,
            description: fn.description || "",
            inputSchema: { json: fn.parameters || {} },
          },
        });
      }
    }
    return converseTools.length > 0 ? { tools: converseTools } : undefined;
  }

  async generateResponse(
    messages: Message[],
    _responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const sdk = await this.getSDK();
    const client = await this.getClient();

    const { system, messages: converseMessages } =
      this.toBedrockMessages(messages);
    const toolConfig = this.toToolConfig(tools);

    const input: ConverseCommandInput = {
      modelId: this.model,
      messages: converseMessages,
      inferenceConfig: this.buildInferenceConfig(),
    };
    if (system) {
      input.system = system;
    }
    if (toolConfig) {
      input.toolConfig = toolConfig;
    }

    const response = await client.send(new sdk.ConverseCommand(input));
    const blocks: ContentBlock[] = response.output?.message?.content ?? [];

    if (toolConfig) {
      let content = "";
      const toolCalls: Array<{ name: string; arguments: string }> = [];
      for (const block of blocks) {
        if ("text" in block && block.text !== undefined) {
          content = block.text;
        } else if ("toolUse" in block && block.toolUse) {
          toolCalls.push({
            name: block.toolUse.name ?? "",
            arguments: JSON.stringify(block.toolUse.input ?? {}),
          });
        }
      }
      return { content, role: "assistant", toolCalls };
    }

    for (const block of blocks) {
      if ("text" in block && block.text !== undefined) {
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
