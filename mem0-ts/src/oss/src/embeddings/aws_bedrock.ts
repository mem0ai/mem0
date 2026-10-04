import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

const DEFAULT_MODEL = "amazon.titan-embed-text-v1";
const DEFAULT_REGION = "us-west-2";

// Cohere's Bedrock embed API rejects an InvokeModel call carrying more than 96
// texts, so `embedBatch` chunks at that boundary.
const COHERE_MAX_BATCH = 96;

// Titan has no server-side batch endpoint -- one InvokeModel call per text --
// so without a cap a large embedBatch() would fan out one request per text.
// Bounds concurrency the same way COHERE_MAX_BATCH bounds the Cohere path.
const TITAN_MAX_CONCURRENCY = 4;

// Cohere wants to know whether a text is being embedded for storage or for a
// retrieval query; embedding a search query in document mode silently
// degrades retrieval. Titan ignores this and has no equivalent parameter.
const COHERE_INPUT_TYPES: Record<"add" | "update" | "search", string> = {
  add: "search_document",
  update: "search_document",
  search: "search_query",
};

type BedrockRuntimeModule = typeof import("@aws-sdk/client-bedrock-runtime");

interface BedrockCredentials {
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken?: string;
}

interface BedrockEmbeddingResponse {
  // Titan returns a single vector. Cohere v3 returns a flat array of vectors;
  // Cohere v4, when `embedding_types` is requested, nests it as `{ float }`.
  embedding?: number[];
  embeddings?: number[][] | { float?: number[][] };
}

/**
 * Runs `fn` over `items` with at most `limit` calls in flight at once,
 * returning results in input order regardless of completion order.
 */
async function mapWithConcurrencyLimit<T, R>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let next = 0;

  async function worker(): Promise<void> {
    while (next < items.length) {
      const index = next++;
      results[index] = await fn(items[index]);
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(limit, items.length) }, worker),
  );
  return results;
}

/**
 * AWS Bedrock embedder, mirroring `mem0/embeddings/aws_bedrock.py`.
 *
 * Supports the Amazon Titan and Cohere embedding model families. The
 * `@aws-sdk/client-bedrock-runtime` dependency is lazily imported so the
 * package stays optional: importing this module never forces the SDK to be
 * installed until a Bedrock embedder actually embeds something.
 */
export class AWSBedrockEmbedder implements Embedder {
  private readonly model: string;
  private readonly region: string;
  private readonly embeddingDims?: number;
  private readonly credentials?: BedrockCredentials;
  private clientPromise?: Promise<{
    sdk: BedrockRuntimeModule;
    client: { send: (command: any) => Promise<{ body?: Uint8Array }> };
  }>;

  constructor(config: EmbeddingConfig) {
    this.model = config.model || DEFAULT_MODEL;
    this.region = config.awsRegion || process.env.AWS_REGION || DEFAULT_REGION;
    this.embeddingDims = config.embeddingDims;

    const hasKeyPair = Boolean(
      config.awsAccessKeyId && config.awsSecretAccessKey,
    );
    const hasAnyCredential = Boolean(
      config.awsAccessKeyId ||
      config.awsSecretAccessKey ||
      config.awsSessionToken,
    );

    // Partially configured credentials would silently fall back to the default
    // chain, embedding under an identity the caller never chose.
    if (hasAnyCredential && !hasKeyPair) {
      throw new Error(
        "AWS Bedrock requires both awsAccessKeyId and awsSecretAccessKey when any explicit credential is configured. " +
          "Omit all credential fields to use the AWS default credential chain.",
      );
    }

    // Leaving `credentials` unset lets the AWS SDK resolve them from its
    // default chain: environment, shared config, SSO, or the instance role.
    if (hasKeyPair) {
      this.credentials = {
        accessKeyId: config.awsAccessKeyId!,
        secretAccessKey: config.awsSecretAccessKey!,
        ...(config.awsSessionToken && { sessionToken: config.awsSessionToken }),
      };
    }
  }

  private async loadSdk(): Promise<BedrockRuntimeModule> {
    try {
      return await import("@aws-sdk/client-bedrock-runtime");
    } catch (error) {
      // Only a genuine module-resolution failure gets the friendly install
      // hint. Node's native ESM loader raises ERR_MODULE_NOT_FOUND; Jest's
      // and bundlers' CJS-style resolvers raise MODULE_NOT_FOUND. Anything
      // else (e.g. the package is installed but throws while loading, such
      // as on a Node version older than the SDK's own engines requirement)
      // rethrows unchanged instead of being misreported as "not installed".
      const code = (error as { code?: string } | undefined)?.code;
      if (code === "ERR_MODULE_NOT_FOUND" || code === "MODULE_NOT_FOUND") {
        throw Object.assign(
          new Error(
            "The '@aws-sdk/client-bedrock-runtime' package is required to use the AWS Bedrock embedder. " +
              "Install it with: npm install @aws-sdk/client-bedrock-runtime",
          ),
          { cause: error },
        );
      }
      throw error;
    }
  }

  private async createClient(): Promise<{
    sdk: BedrockRuntimeModule;
    client: { send: (command: any) => Promise<{ body?: Uint8Array }> };
  }> {
    const sdk = await this.loadSdk();
    return {
      sdk,
      client: new sdk.BedrockRuntimeClient({
        region: this.region,
        ...(this.credentials && { credentials: this.credentials }),
      }),
    };
  }

  private getClient() {
    // Memoized so concurrent embed() calls share one client instead of each
    // racing to build their own. Cleared on rejection so a transient failure
    // (e.g. a network blip while resolving credentials) doesn't permanently
    // disable Bedrock for the rest of this embedder's lifetime.
    if (!this.clientPromise) {
      this.clientPromise = this.createClient().catch((err) => {
        this.clientPromise = undefined;
        throw err;
      });
    }
    return this.clientPromise;
  }

  private isCohereModel(): boolean {
    return this.model.startsWith("cohere.");
  }

  private isCohereV4Model(): boolean {
    return this.model.includes("embed-v4");
  }

  private buildRequestBody(
    texts: string[],
    memoryAction?: "add" | "update" | "search",
  ): Record<string, unknown> {
    if (this.isCohereModel()) {
      const body: Record<string, unknown> = {
        texts,
        input_type: memoryAction
          ? COHERE_INPUT_TYPES[memoryAction]
          : "search_document",
      };

      // Only Embed v4 understands embedding_types / output_dimension; v3
      // rejects unknown fields, so they're guarded to the v4 model family.
      if (this.isCohereV4Model()) {
        body.embedding_types = ["float"];
        if (this.embeddingDims !== undefined) {
          body.output_dimension = this.embeddingDims;
        }
      }
      return body;
    }

    // Titan accepts one text per call. Only Titan Text Embeddings V2 supports
    // a caller-chosen output size (256/512/1024), so the field is guarded the
    // same way the Python provider guards it.
    return {
      inputText: texts[0],
      ...(this.embeddingDims !== undefined &&
        this.model.includes("titan-embed-text-v2") && {
          dimensions: this.embeddingDims,
        }),
    };
  }

  private async invoke(
    texts: string[],
    memoryAction?: "add" | "update" | "search",
  ): Promise<number[][]> {
    const { sdk, client } = await this.getClient();

    let payload: BedrockEmbeddingResponse;
    try {
      const response = await client.send(
        new sdk.InvokeModelCommand({
          modelId: this.model,
          contentType: "application/json",
          accept: "application/json",
          body: new TextEncoder().encode(
            JSON.stringify(this.buildRequestBody(texts, memoryAction)),
          ),
        }),
      );
      payload = JSON.parse(new TextDecoder().decode(response.body));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(
        `Error getting embedding from AWS Bedrock model ${this.model}: ${message}`,
      );
    }

    // Validated outside the try so this message is not re-wrapped by the catch.
    // Cohere v3 replies with a flat `embeddings` array; v4 (when
    // embedding_types is requested) nests it under `.float`.
    const embeddings = this.isCohereModel()
      ? Array.isArray(payload.embeddings)
        ? payload.embeddings
        : payload.embeddings?.float
      : payload.embedding && [payload.embedding];

    // `[]` is truthy, so a lone zero-length vector must be checked for
    // explicitly -- otherwise it passes the length check and hands the
    // caller an empty embedding instead of an error.
    if (
      !embeddings ||
      embeddings.length !== texts.length ||
      embeddings.some((embedding) => embedding.length === 0)
    ) {
      throw new Error(
        `AWS Bedrock model ${this.model} returned no embedding for one or more inputs`,
      );
    }
    return embeddings;
  }

  async embed(
    text: string,
    memoryAction?: "add" | "update" | "search",
  ): Promise<number[]> {
    return (await this.invoke([text], memoryAction))[0];
  }

  async embedBatch(
    texts: string[],
    memoryAction?: "add" | "update" | "search",
  ): Promise<number[][]> {
    if (texts.length === 0) return [];

    if (!this.isCohereModel()) {
      return mapWithConcurrencyLimit(texts, TITAN_MAX_CONCURRENCY, (text) =>
        this.embed(text, memoryAction),
      );
    }

    const embeddings: number[][] = [];
    for (let i = 0; i < texts.length; i += COHERE_MAX_BATCH) {
      embeddings.push(
        ...(await this.invoke(
          texts.slice(i, i + COHERE_MAX_BATCH),
          memoryAction,
        )),
      );
    }
    return embeddings;
  }
}
