import { RerankerConfig } from "../types";
import { Reranker, RerankResult } from "./base";

const DEFAULT_MODEL = "cohere.rerank-v3-5:0";

/**
 * AWS Bedrock reranker provider for the TypeScript OSS SDK.
 *
 * Calls the Bedrock Agent Runtime `Rerank` API (`RerankCommand`), a distinct
 * service from `@aws-sdk/client-bedrock-runtime` (used by the AWS Bedrock LLM
 * and embedding providers) that exposes both the Cohere Rerank and Amazon
 * Rerank foundation models through one interface, authenticated via the
 * standard AWS credential chain rather than a separate provider API key.
 *
 * The `@aws-sdk/client-bedrock-agent-runtime` dependency is loaded on first
 * use via dynamic `import()` so the package stays optional.
 */
interface BedrockAgentRuntimeSDK {
  BedrockAgentRuntimeClient: new (config: Record<string, any>) => any;
  RerankCommand: new (input: Record<string, any>) => any;
}

export class AWSBedrockReranker implements Reranker {
  private model: string;
  private topK?: number;
  private clientConfig: Record<string, any>;
  private clientOverride?: any;
  private sdkPromise?: Promise<BedrockAgentRuntimeSDK>;
  private clientPromise?: Promise<any>;
  private awsRegion: string;

  constructor(config: RerankerConfig) {
    this.model = config.model || DEFAULT_MODEL;
    this.topK = config.topK;

    this.awsRegion = config.awsRegion || process.env.AWS_REGION || "us-west-2";
    const clientConfig: Record<string, any> = { region: this.awsRegion };
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
   * Bedrock's Rerank API addresses models by a region-scoped foundation-model
   * ARN, not the bare model id the LLM/embedding providers use. A
   * caller-supplied ARN is passed through unchanged.
   */
  private resolveModelArn(): string {
    if (this.model.startsWith("arn:aws")) return this.model;
    return `arn:aws:bedrock:${this.awsRegion}::foundation-model/${this.model}`;
  }

  /**
   * Load the optional AWS SDK on first use.
   *
   * This MUST be a dynamic `import()`, never `require()`: tsup/esbuild rewrite
   * `require()` in the published ESM bundle into a `__require` shim that
   * throws `Dynamic require of "..." is not supported`, so every ESM consumer
   * would hit a dead provider even with the SDK installed.
   */
  private async getSDK(): Promise<BedrockAgentRuntimeSDK> {
    if (!this.sdkPromise) {
      this.sdkPromise = import("@aws-sdk/client-bedrock-agent-runtime").then(
        (sdk) => sdk as unknown as BedrockAgentRuntimeSDK,
        (err) => {
          this.sdkPromise = undefined;
          const detail = err instanceof Error ? err.message : String(err);
          throw new Error(
            "The '@aws-sdk/client-bedrock-agent-runtime' package is required to use the AWS Bedrock reranker. " +
              `Install it with: npm install @aws-sdk/client-bedrock-agent-runtime (original error: ${detail})`,
          );
        },
      );
    }
    return this.sdkPromise;
  }

  /** Memoized Bedrock Agent Runtime client; an injected `config.client` short-circuits the SDK. */
  private async getClient(): Promise<any> {
    if (this.clientOverride) return this.clientOverride;
    if (!this.clientPromise) {
      this.clientPromise = this.getSDK().then(
        ({ BedrockAgentRuntimeClient }) =>
          new BedrockAgentRuntimeClient(this.clientConfig),
      );
    }
    return this.clientPromise;
  }

  async rerank(
    query: string,
    documents: string[],
    topK?: number,
  ): Promise<RerankResult[]> {
    if (documents.length === 0) return [];

    const numberOfResults = topK || this.topK || documents.length;

    try {
      const [{ RerankCommand }, client] = await Promise.all([
        this.getSDK(),
        this.getClient(),
      ]);

      const response = await client.send(
        new RerankCommand({
          queries: [{ textQuery: { text: query }, type: "TEXT" }],
          sources: documents.map((text) => ({
            inlineDocumentSource: {
              textDocument: { text },
              type: "TEXT",
            },
            type: "INLINE",
          })),
          rerankingConfiguration: {
            type: "BEDROCK_RERANKING_MODEL",
            bedrockRerankingConfiguration: {
              modelConfiguration: { modelArn: this.resolveModelArn() },
              numberOfResults,
            },
          },
        }),
      );

      return response.results.map((result: any) => ({
        index: result.index,
        rerankScore: result.relevanceScore,
      }));
    } catch (e) {
      console.warn(
        `AWS Bedrock reranking failed, falling back to original order: ${e}`,
      );
      const scored = documents.map((_, index) => ({
        index,
        rerankScore: 0.0,
      }));
      const finalTopK = topK || this.topK;
      return finalTopK ? scored.slice(0, finalTopK) : scored;
    }
  }
}
