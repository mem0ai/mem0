import type {
  BedrockRuntimeClient as BedrockRuntimeClientModule,
  BedrockRuntimeClient as BedrockRuntimeClientType,
  BedrockRuntimeClientConfig,
  InvokeModelCommand as InvokeModelCommandType,
} from "@aws-sdk/client-bedrock-runtime";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_MODEL = "amazon.titan-embed-text-v1";
const DEFAULT_REGION = "us-west-2";

type BedrockEmbeddingResponse = {
  embedding?: number[];
  embeddings?: number[][];
};

type BedrockRuntimeModule = {
  BedrockRuntimeClient: typeof BedrockRuntimeClientModule;
  InvokeModelCommand: typeof InvokeModelCommandType;
};

export class AWSBedrockEmbedder implements Embedder {
  private modulePromise?: Promise<BedrockRuntimeModule>;
  private clientPromise?: Promise<BedrockRuntimeClientType>;
  private model: string;
  private region: string;
  private embeddingDims?: number;
  private credentials?: {
    accessKeyId: string;
    secretAccessKey: string;
    sessionToken?: string;
  };

  constructor(config: EmbeddingConfig) {
    this.model = config.model || DEFAULT_MODEL;
    this.region = config.awsRegion || process.env.AWS_REGION || DEFAULT_REGION;
    this.embeddingDims = config.embeddingDims;

    const hasAccessKey = Boolean(config.awsAccessKeyId);
    const hasSecretKey = Boolean(config.awsSecretAccessKey);
    if (hasAccessKey !== hasSecretKey) {
      throw new Error(
        "AWS Bedrock requires both awsAccessKeyId and awsSecretAccessKey when explicit credentials are configured",
      );
    }

    if (config.awsAccessKeyId && config.awsSecretAccessKey) {
      this.credentials = {
        accessKeyId: config.awsAccessKeyId,
        secretAccessKey: config.awsSecretAccessKey,
        ...(config.awsSessionToken && {
          sessionToken: config.awsSessionToken,
        }),
      };
    }
  }

  private async loadModule(): Promise<BedrockRuntimeModule> {
    if (!this.modulePromise) {
      this.modulePromise = import("@aws-sdk/client-bedrock-runtime").catch(
        (error) => {
          const message =
            error instanceof Error ? error.message : String(error);
          throw new Error(
            "AWS Bedrock embeddings require @aws-sdk/client-bedrock-runtime. " +
              `Install it with \`pnpm add @aws-sdk/client-bedrock-runtime\`. ${message}`,
          );
        },
      );
    }
    return this.modulePromise;
  }

  private async getClient(): Promise<BedrockRuntimeClientType> {
    if (!this.clientPromise) {
      this.clientPromise = this.loadModule().then(
        ({ BedrockRuntimeClient }) => {
          const clientConfig: BedrockRuntimeClientConfig = {
            region: this.region,
            ...(this.credentials && { credentials: this.credentials }),
          };
          return new BedrockRuntimeClient(clientConfig);
        },
      );
    }
    return this.clientPromise;
  }

  private isCohereModel(): boolean {
    return this.model.startsWith("cohere.");
  }

  private buildRequestBody(texts: string[]): Record<string, unknown> {
    if (this.isCohereModel()) {
      return {
        texts,
        input_type: "search_document",
      };
    }

    const body: Record<string, unknown> = { inputText: texts[0] };
    if (
      this.embeddingDims !== undefined &&
      this.model.includes("titan-embed-text-v2")
    ) {
      body.dimensions = this.embeddingDims;
    }
    return body;
  }

  private async invoke(texts: string[]): Promise<number[][]> {
    const { InvokeModelCommand } = await this.loadModule();
    const client = await this.getClient();

    try {
      const response = await client.send(
        new InvokeModelCommand({
          modelId: this.model,
          contentType: "application/json",
          accept: "application/json",
          body: JSON.stringify(this.buildRequestBody(texts)),
        }),
      );
      const parsed = JSON.parse(
        new TextDecoder().decode(response.body),
      ) as BedrockEmbeddingResponse;
      const embeddings = this.isCohereModel()
        ? parsed.embeddings
        : parsed.embedding
          ? [parsed.embedding]
          : undefined;

      if (!embeddings || embeddings.length !== texts.length) {
        throw new Error(
          `AWS Bedrock model ${this.model} returned no embedding for one or more inputs`,
        );
      }
      return embeddings;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(
        `Error getting embedding from AWS Bedrock model ${this.model}: ${message}`,
      );
    }
  }

  async embed(text: string): Promise<number[]> {
    return (await this.invoke([text]))[0];
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) return [];
    if (this.isCohereModel()) return this.invoke(texts);
    return Promise.all(texts.map((text) => this.embed(text)));
  }
}
