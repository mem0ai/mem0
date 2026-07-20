import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_MODEL = "amazon.titan-embed-text-v1";
const DEFAULT_REGION = "us-west-2";
const BEDROCK_RUNTIME_PACKAGE = "@aws-sdk/client-bedrock-runtime";
const NON_COHERE_BATCH_CONCURRENCY = 4;
const COHERE_BATCH_SIZE = 96;

type BedrockEmbeddingResponse = {
  embedding?: number[];
  embeddings?: number[][] | { float?: number[][] };
};

type BedrockRuntimeClientConfig = {
  region: string;
  credentials?: {
    accessKeyId: string;
    secretAccessKey: string;
    sessionToken?: string;
  };
};

type BedrockRuntimeClient = {
  send(command: unknown): Promise<{ body?: Uint8Array }>;
};

type BedrockRuntimeModule = {
  BedrockRuntimeClient: new (
    config: BedrockRuntimeClientConfig,
  ) => BedrockRuntimeClient;
  InvokeModelCommand: new (input: Record<string, unknown>) => unknown;
};

export class AWSBedrockEmbedder implements Embedder {
  private modulePromise?: Promise<BedrockRuntimeModule>;
  private clientPromise?: Promise<BedrockRuntimeClient>;
  private model: string;
  private region: string;
  private embeddingDims?: number;
  private credentials?: BedrockRuntimeClientConfig["credentials"];

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
      this.modulePromise = import(BEDROCK_RUNTIME_PACKAGE)
        .then((runtime) => runtime as BedrockRuntimeModule)
        .catch((error) => {
          const message =
            error instanceof Error ? error.message : String(error);
          throw new Error(
            "AWS Bedrock embeddings require @aws-sdk/client-bedrock-runtime. " +
              `Install it with \`pnpm add @aws-sdk/client-bedrock-runtime\`. ${message}`,
          );
        });
    }
    return this.modulePromise;
  }

  private async getClient(): Promise<BedrockRuntimeClient> {
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

  private isCohereV4Model(): boolean {
    return this.model.includes("embed-v4");
  }

  private buildRequestBody(texts: string[]): Record<string, unknown> {
    if (this.isCohereModel()) {
      return {
        texts,
        input_type: "search_document",
        ...(this.isCohereV4Model() && { embedding_types: ["float"] }),
        ...(this.isCohereV4Model() &&
          this.embeddingDims !== undefined && {
            output_dimension: this.embeddingDims,
          }),
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
      const embeddings = this.extractEmbeddings(parsed);

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

  private extractEmbeddings(
    parsed: BedrockEmbeddingResponse,
  ): number[][] | undefined {
    if (!this.isCohereModel()) {
      return parsed.embedding ? [parsed.embedding] : undefined;
    }

    if (Array.isArray(parsed.embeddings)) {
      return parsed.embeddings;
    }

    return parsed.embeddings?.float;
  }

  async embed(text: string): Promise<number[]> {
    return (await this.invoke([text]))[0];
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    if (texts.length === 0) return [];
    if (this.isCohereModel()) {
      const results: number[][] = [];
      for (let i = 0; i < texts.length; i += COHERE_BATCH_SIZE) {
        results.push(
          ...(await this.invoke(texts.slice(i, i + COHERE_BATCH_SIZE))),
        );
      }
      return results;
    }

    const results: number[][] = new Array(texts.length);
    let nextIndex = 0;

    const worker = async (): Promise<void> => {
      while (nextIndex < texts.length) {
        const index = nextIndex++;
        results[index] = await this.embed(texts[index]);
      }
    };

    const workerCount = Math.min(NON_COHERE_BATCH_CONCURRENCY, texts.length);
    await Promise.all(Array.from({ length: workerCount }, () => worker()));
    return results;
  }
}
