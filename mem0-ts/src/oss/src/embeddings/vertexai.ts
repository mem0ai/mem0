import type { PredictionServiceClient } from "@google-cloud/aiplatform";
import { Embedder } from "./base";
import { VertexAIConfig } from "../types";

type AIPlatform = typeof import("@google-cloud/aiplatform");
type ClientOptions = NonNullable<
  ConstructorParameters<AIPlatform["PredictionServiceClient"]>[0]
>;

interface EmbeddingResponse {
  embeddings: {
    values: number[];
  };
}

/**
 * Vertex AI caps how many input texts one `predict()` call may carry, and the
 * cap depends on the model family. `gemini-embedding-*` accepts exactly one
 * text per request; the older `text-embedding-*` / `text-multilingual-*`
 * models accept up to 250.
 * https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings
 */
function maxInstancesPerRequest(model: string): number {
  return model.startsWith("gemini-embedding") ? 1 : 250;
}

function isValidEmbedding(value: unknown): value is EmbeddingResponse {
  if (typeof value !== "object" || value === null) return false;
  const obj = value as Record<string, unknown>;
  if (typeof obj.embeddings !== "object" || obj.embeddings === null)
    return false;
  const embeddings = obj.embeddings as Record<string, unknown>;
  const values = embeddings.values;
  return (
    Array.isArray(values) &&
    values.every((v) => typeof v === "number" && Number.isFinite(v))
  );
}

export class VertexAIEmbedder implements Embedder {
  private client: PredictionServiceClient | undefined;
  private helpers: AIPlatform["helpers"] | undefined;
  private initPromise: Promise<void> | undefined;
  private clientOptions: ClientOptions;
  private model: string;
  private embeddingDims: number;
  private location: string;
  private projectId: string;
  private embeddingTypes: {
    add: string;
    update: string;
    search: string;
  };

  constructor(config: VertexAIConfig) {
    this.model = config.model || "gemini-embedding-001";
    this.embeddingDims = config.embeddingDims || 256;
    this.location =
      config.location || process.env.GCP_LOCATION || "us-central1";

    // Left empty when unset: initClient() resolves it from Application Default
    // Credentials or the service account key file, the way the Python SDK does.
    this.projectId =
      config.googleProjectId ||
      process.env.GCP_PROJECT_ID ||
      process.env.GOOGLE_CLOUD_PROJECT ||
      process.env.GCLOUD_PROJECT ||
      "";

    this.embeddingTypes = {
      add: config.memoryAddEmbeddingType || "RETRIEVAL_DOCUMENT",
      update: config.memoryUpdateEmbeddingType || "RETRIEVAL_DOCUMENT",
      search: config.memorySearchEmbeddingType || "RETRIEVAL_QUERY",
    };

    const endpoint = `${this.location}-aiplatform.googleapis.com`;
    this.clientOptions = { apiEndpoint: endpoint };

    if (config.vertexCredentialsJson) {
      this.clientOptions.keyFilename = config.vertexCredentialsJson;
    } else if (config.googleServiceAccountJson) {
      try {
        this.clientOptions.credentials =
          typeof config.googleServiceAccountJson === "string"
            ? JSON.parse(config.googleServiceAccountJson)
            : config.googleServiceAccountJson;
      } catch (err) {
        throw new Error(
          "Failed to parse googleServiceAccountJson: " + (err as Error).message,
        );
      }
    }
  }

  private async initClient(): Promise<void> {
    // Memoized so concurrent embed() calls share one client instead of each
    // racing to build (and leak) their own gRPC channel.
    if (!this.initPromise) {
      this.initPromise = this.createClient().catch((err) => {
        this.initPromise = undefined;
        throw err;
      });
    }
    await this.initPromise;
  }

  private async createClient(): Promise<void> {
    let aiplatform: AIPlatform;
    try {
      aiplatform = await import("@google-cloud/aiplatform");
    } catch (err) {
      throw new Error(
        "Failed to import '@google-cloud/aiplatform'. Please install it to use the Vertex AI embedding provider: " +
          (err as Error).message,
      );
    }

    const client = new aiplatform.PredictionServiceClient(this.clientOptions);

    if (!this.projectId) {
      try {
        this.projectId = await client.getProjectId();
      } catch (err) {
        throw new Error(
          "Vertex AI could not determine a Google Cloud project ID. Set googleProjectId in config, " +
            "one of the GCP_PROJECT_ID / GOOGLE_CLOUD_PROJECT / GCLOUD_PROJECT env vars, or configure " +
            "Application Default Credentials: " +
            (err as Error).message,
        );
      }
    }

    this.client = client;
    this.helpers = aiplatform.helpers;
  }

  private endpoint(): string {
    return `projects/${this.projectId}/locations/${this.location}/publishers/google/models/${this.model}`;
  }

  private formatInstance(text: string, taskType: string) {
    // task_type must live on the instance (snake_case), not in `parameters`.
    // Vertex silently ignores an unknown `parameters.taskType`, which would
    // fall back to the model's default task type. This mirrors the Python SDK's
    // TextEmbeddingInput(text=..., task_type=...).
    return {
      content: text,
      task_type: taskType,
    };
  }

  async embed(
    text: string,
    memoryAction?: "add" | "update" | "search",
  ): Promise<number[]> {
    await this.initClient();
    if (!this.client || !this.helpers) {
      throw new Error("Client not initialized");
    }

    let embeddingType = "SEMANTIC_SIMILARITY";
    if (memoryAction !== undefined) {
      if (!(memoryAction in this.embeddingTypes)) {
        throw new Error(`Invalid memory action: ${memoryAction}`);
      }
      embeddingType = this.embeddingTypes[memoryAction];
    }

    const instance = this.formatInstance(text, embeddingType);
    const parameters = {
      outputDimensionality: this.embeddingDims,
    };

    const [response] = await this.client.predict({
      endpoint: this.endpoint(),
      instances: [this.helpers.toValue(instance) as any],
      parameters: this.helpers.toValue(parameters) as any,
    });

    if (!response.predictions || response.predictions.length === 0) {
      throw new Error("No predictions returned from Vertex AI");
    }

    const decoded = this.helpers.fromValue(response.predictions[0] as any);
    if (!isValidEmbedding(decoded)) {
      throw new Error("Failed to extract embedding values from response");
    }

    return decoded.embeddings.values;
  }

  async embedBatch(
    texts: string[],
    memoryAction: "add" | "update" | "search" = "add",
  ): Promise<number[][]> {
    if (!texts || texts.length === 0) {
      return [];
    }

    await this.initClient();
    if (!this.client || !this.helpers) {
      throw new Error("Client not initialized");
    }

    if (!(memoryAction in this.embeddingTypes)) {
      throw new Error(`Invalid memory action: ${memoryAction}`);
    }
    const embeddingType = this.embeddingTypes[memoryAction];

    const allEmbeddings: number[][] = [];
    const batchSize = maxInstancesPerRequest(this.model);

    for (let i = 0; i < texts.length; i += batchSize) {
      const chunk = texts.slice(i, i + batchSize);
      const instances = chunk.map(
        (text) =>
          this.helpers!.toValue(
            this.formatInstance(text, embeddingType),
          ) as any,
      );
      const parameters = {
        outputDimensionality: this.embeddingDims,
      };

      const [response] = await this.client.predict({
        endpoint: this.endpoint(),
        instances,
        parameters: this.helpers.toValue(parameters) as any,
      });

      if (!response.predictions || response.predictions.length === 0) {
        throw new Error("No predictions returned from Vertex AI batch request");
      }

      for (const prediction of response.predictions) {
        const decoded = this.helpers.fromValue(prediction as any);
        if (!isValidEmbedding(decoded)) {
          throw new Error(
            "Failed to extract embedding values from batch response",
          );
        }
        allEmbeddings.push(decoded.embeddings.values);
      }
    }

    if (allEmbeddings.length !== texts.length) {
      throw new Error(
        `Vertex AI embedBatch() returned ${allEmbeddings.length} embeddings for ${texts.length} texts using model '${this.model}'`,
      );
    }

    return allEmbeddings;
  }
}
