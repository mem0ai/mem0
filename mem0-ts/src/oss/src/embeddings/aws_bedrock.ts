import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

/**
 * Try to import AWS SDK Bedrock Runtime client.
 * This is a peer dependency - users must install @aws-sdk/client-bedrock-runtime.
 */
let BedrockRuntimeClient: any;
let InvokeModelCommand: any;

try {
  const bedrockRuntime = require("@aws-sdk/client-bedrock-runtime");
  BedrockRuntimeClient = bedrockRuntime.BedrockRuntimeClient;
  InvokeModelCommand = bedrockRuntime.InvokeModelCommand;
} catch {
  // Will throw at runtime if AWSBedrockEmbedder is used without the SDK installed
}

/**
 * Supported Bedrock embedding providers.
 */
const EMBEDDING_PROVIDERS = ["amazon", "cohere"] as const;

type EmbeddingProvider = (typeof EMBEDDING_PROVIDERS)[number];

/**
 * Configuration for AWS Bedrock Embedder.
 */
export interface AWSBedrockEmbeddingConfig extends EmbeddingConfig {
  /** AWS region (e.g., "us-east-1", "us-west-2") */
  region?: string;
  /** AWS credentials (optional - falls back to environment/IAM) */
  credentials?: {
    accessKeyId: string;
    secretAccessKey: string;
    sessionToken?: string;
  };
  /** Whether to normalize embeddings to unit vectors */
  normalize?: boolean;
}

/**
 * Extract provider from model identifier.
 *
 * @param model - Model identifier (e.g., "amazon.titan-embed-text-v1")
 * @returns Provider name
 */
function extractProvider(model: string): EmbeddingProvider {
  const lowerModel = model.toLowerCase();

  if (lowerModel.startsWith("amazon") || lowerModel.includes("titan")) {
    return "amazon";
  }
  if (lowerModel.startsWith("cohere") || lowerModel.includes("embed")) {
    if (lowerModel.includes("cohere")) {
      return "cohere";
    }
  }

  // Default to amazon for unknown models
  return "amazon";
}

/**
 * AWS Bedrock Embedder implementation.
 *
 * Supports Amazon Titan and Cohere embedding models via AWS Bedrock.
 *
 * @example
 * ```typescript
 * const embedder = new AWSBedrockEmbedder({
 *   model: "amazon.titan-embed-text-v1",
 *   region: "us-east-1",
 * });
 *
 * const embedding = await embedder.embed("Hello, world!");
 * ```
 *
 * @example
 * ```typescript
 * // Using Cohere embeddings
 * const embedder = new AWSBedrockEmbedder({
 *   model: "cohere.embed-english-v3",
 *   region: "us-west-2",
 * });
 *
 * const embeddings = await embedder.embedBatch(["text1", "text2"]);
 * ```
 */
export class AWSBedrockEmbedder implements Embedder {
  private client: InstanceType<typeof BedrockRuntimeClient>;
  private model: string;
  private provider: EmbeddingProvider;
  private normalize: boolean;

  /**
   * Default embedding dimensions by model.
   */
  private static readonly MODEL_DIMENSIONS: Record<string, number> = {
    "amazon.titan-embed-text-v1": 1536,
    "amazon.titan-embed-text-v2:0": 1024,
    "amazon.titan-embed-image-v1": 1024,
    "cohere.embed-english-v3": 1024,
    "cohere.embed-multilingual-v3": 1024,
  };

  constructor(config: AWSBedrockEmbeddingConfig) {
    if (!BedrockRuntimeClient) {
      throw new Error(
        "The '@aws-sdk/client-bedrock-runtime' package is required. " +
          "Please install it using 'npm install @aws-sdk/client-bedrock-runtime'.",
      );
    }

    this.model = config.model || "amazon.titan-embed-text-v1";
    this.provider = extractProvider(this.model);
    this.normalize = config.normalize ?? false;

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
   * Normalize a vector to unit length.
   *
   * @param vector - Input vector
   * @returns Normalized vector
   */
  private normalizeVector(vector: number[]): number[] {
    const magnitude = Math.sqrt(
      vector.reduce((sum, val) => sum + val * val, 0),
    );

    if (magnitude === 0) {
      return vector;
    }

    return vector.map((val) => val / magnitude);
  }

  /**
   * Prepare input body for Amazon Titan models.
   *
   * @param text - Text to embed
   * @returns Request body
   */
  private prepareAmazonInput(text: string): Record<string, unknown> {
    return {
      inputText: text,
    };
  }

  /**
   * Prepare input body for Cohere models.
   *
   * @param texts - Texts to embed
   * @param inputType - Type of input (search_document, search_query, classification, clustering)
   * @returns Request body
   */
  private prepareCohereInput(
    texts: string[],
    inputType: string = "search_document",
  ): Record<string, unknown> {
    return {
      texts: texts,
      input_type: inputType,
    };
  }

  /**
   * Parse embedding response from Amazon Titan models.
   *
   * @param responseBody - Response body from Bedrock
   * @returns Embedding vector
   */
  private parseAmazonResponse(responseBody: Record<string, unknown>): number[] {
    const embedding = responseBody.embedding as number[] | undefined;

    if (!embedding) {
      throw new Error("No embedding found in Amazon Titan response");
    }

    return embedding;
  }

  /**
   * Parse embedding response from Cohere models.
   *
   * @param responseBody - Response body from Bedrock
   * @returns Embedding vectors
   */
  private parseCohereResponse(
    responseBody: Record<string, unknown>,
  ): number[][] {
    const embeddings = responseBody.embeddings as number[][] | undefined;

    if (!embeddings || embeddings.length === 0) {
      throw new Error("No embeddings found in Cohere response");
    }

    return embeddings;
  }

  /**
   * Invoke the Bedrock model.
   *
   * @param body - Request body
   * @returns Response body
   */
  private async invokeModel(
    body: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const command = new InvokeModelCommand({
      modelId: this.model,
      body: JSON.stringify(body),
      accept: "application/json",
      contentType: "application/json",
    });

    const response = await this.client.send(command);

    // Parse response body
    const responseBody = JSON.parse(
      new TextDecoder().decode(response.body),
    ) as Record<string, unknown>;

    return responseBody;
  }

  /**
   * Generate embedding for a single text.
   *
   * @param text - Text to embed
   * @returns Embedding vector
   */
  async embed(text: string): Promise<number[]> {
    let embedding: number[];

    if (this.provider === "cohere") {
      // Cohere always returns an array of embeddings
      const body = this.prepareCohereInput([text], "search_document");
      const responseBody = await this.invokeModel(body);
      const embeddings = this.parseCohereResponse(responseBody);
      embedding = embeddings[0];
    } else {
      // Amazon Titan
      const body = this.prepareAmazonInput(text);
      const responseBody = await this.invokeModel(body);
      embedding = this.parseAmazonResponse(responseBody);
    }

    if (this.normalize) {
      embedding = this.normalizeVector(embedding);
    }

    return embedding;
  }

  /**
   * Generate embeddings for multiple texts.
   *
   * @param texts - Array of texts to embed
   * @returns Array of embedding vectors
   */
  async embedBatch(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) {
      return [];
    }

    let embeddings: number[][];

    if (this.provider === "cohere") {
      // Cohere supports batch embedding natively
      const body = this.prepareCohereInput(texts, "search_document");
      const responseBody = await this.invokeModel(body);
      embeddings = this.parseCohereResponse(responseBody);
    } else {
      // Amazon Titan doesn't support batch - process sequentially
      embeddings = await Promise.all(texts.map((text) => this.embed(text)));
      return embeddings; // Already normalized if needed in embed()
    }

    if (this.normalize) {
      embeddings = embeddings.map((emb) => this.normalizeVector(emb));
    }

    return embeddings;
  }
}
