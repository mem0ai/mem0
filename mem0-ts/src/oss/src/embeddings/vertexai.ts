import type { PredictionServiceClient } from "@google-cloud/aiplatform";
import { Embedder } from "./base";
import { VertexAIConfig } from "../types";

interface EmbeddingResponse {
  embeddings: {
    values: number[];
  };
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
  private helpers: any;
  private clientOptions: any;
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

    this.projectId =
      config.googleProjectId ||
      process.env.GCP_PROJECT_ID ||
      process.env.GOOGLE_CLOUD_PROJECT ||
      process.env.GCLOUD_PROJECT ||
      "";

    if (!this.projectId) {
      throw new Error(
        "Vertex AI requires a Google Cloud project ID. Set googleProjectId in config or the GOOGLE_CLOUD_PROJECT/GCLOUD_PROJECT env var.",
      );
    }

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
    if (this.client) {
      return;
    }
    try {
      const aiplatform = await import("@google-cloud/aiplatform");
      this.client = new aiplatform.PredictionServiceClient(this.clientOptions);
      this.helpers = aiplatform.helpers;
    } catch (err) {
      throw new Error(
        "Failed to import '@google-cloud/aiplatform'. Please install it to use the Vertex AI embedding provider: " +
          (err as Error).message,
      );
    }
  }

  private formatInstance(text: string) {
    return {
      content: text,
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

    const endpointName = `projects/${this.projectId}/locations/${this.location}/publishers/google/models/${this.model}`;
    const instance = this.formatInstance(text);
    const parameters = {
      taskType: embeddingType,
      outputDimensionality: this.embeddingDims,
    };

    const [response] = await this.client.predict({
      endpoint: endpointName,
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

    let embeddingType = "SEMANTIC_SIMILARITY";
    if (memoryAction !== undefined) {
      if (!(memoryAction in this.embeddingTypes)) {
        throw new Error(`Invalid memory action: ${memoryAction}`);
      }
      embeddingType = this.embeddingTypes[memoryAction];
    }

    const endpointName = `projects/${this.projectId}/locations/${this.location}/publishers/google/models/${this.model}`;
    const allEmbeddings: number[][] = [];
    const batchSize = 250;

    for (let i = 0; i < texts.length; i += batchSize) {
      const chunk = texts.slice(i, i + batchSize);
      const instances = chunk.map(
        (text) => this.helpers.toValue(this.formatInstance(text)) as any,
      );
      const parameters = {
        taskType: embeddingType,
        outputDimensionality: this.embeddingDims,
      };

      const [response] = await this.client.predict({
        endpoint: endpointName,
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
        `Vertex AI embedBatch() returned ${allEmbeddings.length} embeddings for ${texts.length} texts`,
      );
    }

    return allEmbeddings;
  }
}
