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
 * The `@aws-sdk/client-bedrock-runtime` dependency is lazily required so the
 * package stays optional. Credentials resolve via the standard AWS chain
 * unless provided explicitly in config.
 */
/**
 * Bedrock API path. `converse` (default) uses the uniform Converse API and
 * covers the large majority of current chat models. `invoke_model` uses the
 * legacy `InvokeModelCommand` for older models that are not reachable through
 * Converse (opt-in — follow-up to #5890, see #6023).
 */
export type BedrockApi = "converse" | "invoke_model";

export class AWSBedrockLLM implements LLM {
  private client: any;
  private model: string;
  private provider: string;
  private temperature: number;
  private maxTokens: number;
  private topP?: number;
  private api: BedrockApi;
  private ConverseCommand: any;
  private InvokeModelCommand: any;

  constructor(config: AWSBedrockConfig = {}) {
    this.model =
      (typeof config.model === "string" && config.model) ||
      "anthropic.claude-3-5-sonnet-20240620-v1:0";
    this.provider = extractProvider(this.model);
    this.temperature = config.temperature ?? 0.1;
    this.maxTokens = config.maxTokens ?? 2000;
    this.topP = config.topP;
    this.api =
      (config as { bedrockApi?: BedrockApi }).bedrockApi === "invoke_model"
        ? "invoke_model"
        : "converse";

    let BedrockRuntimeClient: any;
    let ConverseCommand: any;
    let InvokeModelCommand: any;
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const sdk = require("@aws-sdk/client-bedrock-runtime");
      BedrockRuntimeClient = sdk.BedrockRuntimeClient;
      ConverseCommand = sdk.ConverseCommand;
      InvokeModelCommand = sdk.InvokeModelCommand;
    } catch (_) {
      throw new Error(
        "The '@aws-sdk/client-bedrock-runtime' package is required to use the AWS Bedrock LLM provider. " +
          "Install it with: npm install @aws-sdk/client-bedrock-runtime",
      );
    }
    this.ConverseCommand = ConverseCommand;
    this.InvokeModelCommand = InvokeModelCommand;

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

    if (config.client) {
      this.client = config.client;
    } else {
      this.client = new BedrockRuntimeClient(clientConfig);
    }
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

  /**
   * Build a provider-family-specific request body for the legacy InvokeModel
   * path. Unlike Converse, each model family has its own body shape. Mirrors
   * the per-family branches in the Python provider (`mem0/llms/aws_bedrock.py`).
   */
  private buildInvokeBody(messages: Message[]): Record<string, any> {
    const systemParts: string[] = [];
    const turns: { role: string; content: string }[] = [];
    for (const msg of messages) {
      const content =
        typeof msg.content === "string"
          ? msg.content
          : JSON.stringify(msg.content);
      if (msg.role === "system") systemParts.push(content);
      else
        turns.push({
          role: msg.role === "assistant" ? "assistant" : "user",
          content,
        });
    }
    const system = systemParts.join("\n");
    const prompt = turns.map((t) => `${t.role}: ${t.content}`).join("\n");

    switch (this.provider) {
      case "anthropic":
        return {
          anthropic_version: "bedrock-2023-05-31",
          max_tokens: this.maxTokens,
          temperature: this.temperature,
          ...(this.topP != null ? { top_p: this.topP } : {}),
          ...(system ? { system } : {}),
          messages: turns.map((t) => ({
            role: t.role,
            content: [{ type: "text", text: t.content }],
          })),
        };
      case "amazon":
      case "titan":
        return {
          inputText: `${system ? system + "\n" : ""}${prompt}`,
          textGenerationConfig: {
            maxTokenCount: this.maxTokens,
            temperature: this.temperature,
            ...(this.topP != null ? { topP: this.topP } : {}),
          },
        };
      case "meta":
      case "llama":
        return {
          prompt: `${system ? system + "\n" : ""}${prompt}`,
          max_gen_len: this.maxTokens,
          temperature: this.temperature,
          ...(this.topP != null ? { top_p: this.topP } : {}),
        };
      case "mistral":
        return {
          prompt: `${system ? system + "\n" : ""}${prompt}`,
          max_tokens: this.maxTokens,
          temperature: this.temperature,
          ...(this.topP != null ? { top_p: this.topP } : {}),
        };
      case "cohere":
        return {
          message: prompt,
          max_tokens: this.maxTokens,
          temperature: this.temperature,
          ...(this.topP != null ? { p: this.topP } : {}),
        };
      case "ai21":
      case "j2":
        return {
          prompt: `${system ? system + "\n" : ""}${prompt}`,
          maxTokens: this.maxTokens,
          temperature: this.temperature,
          ...(this.topP != null ? { topP: this.topP } : {}),
        };
      default:
        throw new Error(
          `InvokeModel body not implemented for provider '${this.provider}'. ` +
            `Use the default Converse API for this model, or add a body builder for '${this.provider}'.`,
        );
    }
  }

  /** Parse a provider-family-specific InvokeModel response body into text. */
  private parseInvokeResponse(body: any): string {
    switch (this.provider) {
      case "anthropic":
        return body?.content?.[0]?.text ?? body?.completion ?? "";
      case "amazon":
      case "titan":
        return body?.results?.[0]?.outputText ?? "";
      case "meta":
      case "llama":
        return body?.generation ?? "";
      case "mistral":
        return body?.outputs?.[0]?.text ?? "";
      case "cohere":
        return body?.text ?? body?.generations?.[0]?.text ?? "";
      case "ai21":
      case "j2":
        return body?.completions?.[0]?.data?.text ?? "";
      default:
        return "";
    }
  }

  /** Legacy InvokeModel path for models not covered by Converse (#6023). */
  private async invokeModel(messages: Message[]): Promise<string> {
    const body = this.buildInvokeBody(messages);
    const response = await this.client.send(
      new this.InvokeModelCommand({
        modelId: this.model,
        contentType: "application/json",
        accept: "application/json",
        body: JSON.stringify(body),
      }),
    );
    const raw =
      typeof response?.body === "string"
        ? response.body
        : new TextDecoder().decode(response?.body);
    let parsed: any = {};
    try {
      parsed = JSON.parse(raw);
    } catch (_) {
      parsed = {};
    }
    return this.parseInvokeResponse(parsed);
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

    return this.client.send(new this.ConverseCommand(input));
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
      if (this.api === "invoke_model") {
        // Legacy InvokeModel path does not support Converse-style tool config;
        // tools are ignored here (Converse remains the tool-capable path).
        return await this.invokeModel(messages);
      }
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
      if (this.api === "invoke_model") {
        const text = await this.invokeModel(messages);
        return { content: text, role: "assistant" };
      }
      const response = await this.converse(messages);
      return { content: this.parseText(response), role: "assistant" };
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      throw new Error(`AWS Bedrock LLM failed: ${message}`);
    }
  }
}
