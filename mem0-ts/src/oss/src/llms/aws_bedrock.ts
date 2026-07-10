import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types";

/**
 * Providers recognised in Bedrock model identifiers, mirroring the Python
 * provider's `PROVIDERS` list (`mem0/llms/aws_bedrock.py`).
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
  "minimax",
];

/**
 * Extract the model-family provider from a Bedrock model id
 * (e.g. `anthropic.claude-3-sonnet-...` -> `anthropic`).
 */
export function extractProvider(model: string): string {
  for (const provider of PROVIDERS) {
    const re = new RegExp(
      `\\b${provider.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`,
    );
    if (re.test(model)) return provider;
  }
  throw new Error(`Unknown provider in model: ${model}`);
}

/**
 * AWS Bedrock fields (awsRegion / awsAccessKeyId / awsSecretAccessKey /
 * awsSessionToken / client) now live on the shared `LLMConfig`, so the
 * provider is configurable through the standard typed `Memory` config path.
 */
type AWSBedrockConfig = LLMConfig;

/**
 * AWS Bedrock LLM provider for the TypeScript OSS SDK.
 *
 * Mirrors `mem0/llms/aws_bedrock.py`. Uses the Bedrock **Converse API**
 * (`ConverseCommand`), which provides a uniform message/tool interface across
 * the Anthropic / Amazon (Nova) / Meta / Mistral / Cohere model families, so a
 * single code path serves them all (the Python provider keeps per-family
 * `invoke_model` branches for legacy reasons; Converse supersedes them).
 *
 * The `@aws-sdk/client-bedrock-runtime` dependency is loaded on first use via
 * dynamic `import()` so the package stays optional. Credentials resolve via the
 * standard AWS chain unless provided explicitly in config.
 */
interface BedrockSDK {
  BedrockRuntimeClient: new (config: Record<string, any>) => any;
  ConverseCommand: new (input: Record<string, any>) => any;
}

export class AWSBedrockLLM implements LLM {
  private model: string;
  private provider: string;
  private temperature: number;
  private maxTokens: number;
  private topP?: number;
  private clientConfig: Record<string, any>;
  private clientOverride?: any;
  private sdkPromise?: Promise<BedrockSDK>;
  private clientPromise?: Promise<any>;

  constructor(config: AWSBedrockConfig = {}) {
    this.model =
      (typeof config.model === "string" && config.model) ||
      "anthropic.claude-3-5-sonnet-20240620-v1:0";
    this.provider = extractProvider(this.model);
    this.temperature = config.temperature ?? 0.1;
    this.maxTokens = config.maxTokens ?? 2000;
    this.topP = config.topP;

    const region =
      config.awsRegion ||
      process.env.AWS_REGION ||
      process.env.AWS_DEFAULT_REGION;
    const clientConfig: Record<string, any> = {};
    if (region) clientConfig.region = region;
    if (config.awsAccessKeyId && config.awsSecretAccessKey) {
      clientConfig.credentials = {
        accessKeyId: config.awsAccessKeyId,
        secretAccessKey: config.awsSecretAccessKey,
        ...(config.awsSessionToken && {
          sessionToken: config.awsSessionToken,
        }),
      };
    }

    this.clientConfig = clientConfig;
    this.clientOverride = config.client;
  }

  /**
   * Load the optional AWS SDK on first use.
   *
   * This MUST be a dynamic `import()`, never `require()`: tsup/esbuild rewrite
   * `require()` in the published ESM bundle (`dist/oss/index.mjs`) into a
   * `__require` shim that throws `Dynamic require of "..." is not supported`,
   * so every ESM consumer would hit a dead provider even with the SDK installed.
   */
  private async getSDK(): Promise<BedrockSDK> {
    if (!this.sdkPromise) {
      this.sdkPromise = import("@aws-sdk/client-bedrock-runtime").then(
        (sdk) => sdk as unknown as BedrockSDK,
        (err) => {
          // Let a later call retry rather than caching the rejection forever.
          this.sdkPromise = undefined;
          const detail = err instanceof Error ? err.message : String(err);
          throw new Error(
            "The '@aws-sdk/client-bedrock-runtime' package is required to use the AWS Bedrock LLM provider. " +
              `Install it with: npm install @aws-sdk/client-bedrock-runtime (original error: ${detail})`,
          );
        },
      );
    }
    return this.sdkPromise;
  }

  /** Memoized Bedrock client; an injected `config.client` short-circuits the SDK. */
  private async getClient(): Promise<any> {
    if (this.clientOverride) return this.clientOverride;
    if (!this.clientPromise) {
      this.clientPromise = this.getSDK().then(
        ({ BedrockRuntimeClient }) =>
          new BedrockRuntimeClient(this.clientConfig),
      );
    }
    return this.clientPromise;
  }

  /**
   * Split messages into a top-level `system` block (Converse passes system
   * prompts separately) and role-tagged content blocks for everything else.
   */
  private formatMessages(messages: Message[]): {
    system?: { text: string }[];
    converseMessages: { role: string; content: { text: string }[] }[];
  } {
    const systemParts: string[] = [];
    const converseMessages: { role: string; content: { text: string }[] }[] =
      [];

    for (const msg of messages) {
      const role = msg.role;
      const content =
        typeof msg.content === "string"
          ? msg.content
          : JSON.stringify(msg.content);
      if (role === "system") {
        systemParts.push(content);
      } else {
        converseMessages.push({
          role: role === "assistant" ? "assistant" : "user",
          content: [{ text: content }],
        });
      }
    }

    if (converseMessages.length === 0) {
      converseMessages.push({ role: "user", content: [{ text: "" }] });
    }

    return {
      system: systemParts.length
        ? [{ text: systemParts.join("\n") }]
        : undefined,
      converseMessages,
    };
  }

  /**
   * Build the Converse `inferenceConfig`. Anthropic and MiniMax reasoning
   * models reject requests carrying both `temperature` and `topP`, so `topP`
   * is omitted for those families (mirrors the Python `_build_inference_config`).
   */
  private buildInferenceConfig(): Record<string, any> {
    const inferenceConfig: Record<string, any> = {
      maxTokens: this.maxTokens,
      temperature: this.temperature,
    };
    if (
      this.topP != null &&
      !["anthropic", "minimax"].includes(this.provider)
    ) {
      inferenceConfig.topP = this.topP;
    }
    return inferenceConfig;
  }

  /** Convert OpenAI-style tools to the Converse `toolConfig` shape. */
  private convertToolsToConverse(tools: any[]): any | undefined {
    if (!tools || tools.length === 0) return undefined;
    const converseTools = tools
      .filter((t) => t?.type === "function" && t.function)
      .map((t) => ({
        toolSpec: {
          name: t.function.name,
          description: t.function.description || "",
          inputSchema: { json: t.function.parameters || {} },
        },
      }));
    return converseTools.length ? { tools: converseTools } : undefined;
  }

  private async converse(messages: Message[], tools?: any[]): Promise<any> {
    const { system, converseMessages } = this.formatMessages(messages);
    const input: Record<string, any> = {
      modelId: this.model,
      messages: converseMessages,
      inferenceConfig: this.buildInferenceConfig(),
    };
    if (system) input.system = system;
    const toolConfig = tools ? this.convertToolsToConverse(tools) : undefined;
    if (toolConfig) input.toolConfig = toolConfig;

    const [{ ConverseCommand }, client] = await Promise.all([
      this.getSDK(),
      this.getClient(),
    ]);
    return client.send(new ConverseCommand(input));
  }

  /** Pull the first text block out of a Converse response. */
  private parseText(response: any): string {
    const content = response?.output?.message?.content || [];
    for (const block of content) {
      if (block && typeof block.text === "string") return block.text;
    }
    return "";
  }

  /** Collect any toolUse blocks out of a Converse response. */
  private parseToolCalls(response: any): { name: string; arguments: string }[] {
    const content = response?.output?.message?.content || [];
    const calls: { name: string; arguments: string }[] = [];
    for (const block of content) {
      if (block?.toolUse) {
        calls.push({
          name: block.toolUse.name,
          arguments: JSON.stringify(block.toolUse.input ?? {}),
        });
      }
    }
    return calls;
  }

  async generateResponse(
    messages: Message[],
    _responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    try {
      const response = await this.converse(messages, tools);
      if (tools && tools.length) {
        const toolCalls = this.parseToolCalls(response);
        if (toolCalls.length) {
          return {
            content: this.parseText(response),
            role: "assistant",
            toolCalls,
          };
        }
      }
      return this.parseText(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`AWS Bedrock LLM failed: ${message}`);
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    try {
      const response = await this.converse(messages);
      return { content: this.parseText(response), role: "assistant" };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`AWS Bedrock LLM failed: ${message}`);
    }
  }
}
