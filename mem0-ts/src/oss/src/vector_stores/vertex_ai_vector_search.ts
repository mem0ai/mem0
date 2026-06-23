import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

export interface GoogleMatchingEngineConfig extends VectorStoreConfig {
  projectId: string;
  projectNumber: string;
  region: string;
  endpointId: string;
  indexId: string;
  deploymentIndexId: string;
  collectionName?: string;
  credentialsPath?: string;
  serviceAccountJson?: Record<string, any>;
  vectorSearchApiEndpoint?: string;
}

export class VertexAIVectorSearch implements VectorStore {
  private config: GoogleMatchingEngineConfig;
  private matchClient: any;
  private indexClient: any;
  private _initPromise?: Promise<void>;

  constructor(config: GoogleMatchingEngineConfig) {
    this.config = { ...config };
    if (!this.config.collectionName) {
      this.config.collectionName =
        this.config.indexId || this.config.deploymentIndexId;
    }
    this.initialize().catch(console.error);
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    try {
      const aiplatform = await import("@google-cloud/aiplatform");
      const { MatchServiceClient, IndexServiceClient } = aiplatform.v1;

      const clientOptions: any = {
        projectId: this.config.projectId,
        apiEndpoint:
          this.config.vectorSearchApiEndpoint ||
          `${this.config.region}-aiplatform.googleapis.com`,
      };

      if (this.config.credentialsPath) {
        clientOptions.keyFilename = this.config.credentialsPath;
      } else if (this.config.serviceAccountJson) {
        clientOptions.credentials = {
          client_email: this.config.serviceAccountJson.client_email,
          private_key: this.config.serviceAccountJson.private_key,
        };
      }

      this.matchClient = new MatchServiceClient(clientOptions);
      this.indexClient = new IndexServiceClient(clientOptions);
    } catch (error) {
      console.error(
        "Failed to initialize Vertex AI client. Make sure @google-cloud/aiplatform is installed.",
        error,
      );
      throw error;
    }
  }

  private _createRestriction(key: string, value: any): any {
    return {
      namespace: key,
      allowList: [String(value)],
    };
  }

  private _createDatapoint(
    vectorId: string,
    vector: number[],
    payload: Record<string, any> = {},
  ): any {
    const restricts = Object.entries(payload).map(([key, value]) =>
      this._createRestriction(key, value),
    );
    return {
      datapointId: vectorId,
      featureVector: vector,
      restricts: restricts.length > 0 ? restricts : undefined,
    };
  }

  private get indexPath(): string {
    return `projects/${this.config.projectNumber}/locations/${this.config.region}/indexes/${this.config.indexId}`;
  }

  private get indexEndpointPath(): string {
    return `projects/${this.config.projectNumber}/locations/${this.config.region}/indexEndpoints/${this.config.endpointId}`;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    const datapoints = vectors.map((vector, i) =>
      this._createDatapoint(ids[i], vector, payloads[i] || {}),
    );

    await this.indexClient.upsertDatapoints({
      index: this.indexPath,
      datapoints,
    });
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();

    const restricts: any[] = [];
    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        if (typeof value === "object" && value !== null) {
          const includes = value.include || [];
          const excludes = value.exclude || [];
          restricts.push({
            namespace: key,
            allowList: includes.map(String),
            denyList: excludes.map(String),
          });
        } else {
          restricts.push({
            namespace: key,
            allowList: [String(value)],
          });
        }
      }
    }

    const request = {
      indexEndpoint: this.indexEndpointPath,
      deployedIndexId: this.config.deploymentIndexId,
      queries: [
        {
          datapoint: {
            featureVector: query,
            restricts: restricts.length > 0 ? restricts : undefined,
          },
          neighborCount: topK,
        },
      ],
      returnFullDatapoint: true,
    };

    const [response] = await this.matchClient.findNeighbors(request);

    if (
      !response ||
      !response.nearestNeighbors ||
      response.nearestNeighbors.length === 0
    ) {
      return [];
    }

    const neighbors = response.nearestNeighbors[0].neighbors || [];
    return neighbors.map((neighbor: any) => {
      const payload: Record<string, any> = {};
      if (neighbor.datapoint?.restricts) {
        for (const restrict of neighbor.datapoint.restricts) {
          if (restrict.allowList && restrict.allowList.length > 0) {
            payload[restrict.namespace] = restrict.allowList[0];
          }
        }
      }

      const score =
        neighbor.distance !== undefined
          ? Math.max(0.0, 1.0 - neighbor.distance)
          : undefined;
      return {
        id: neighbor.datapoint.datapointId,
        payload,
        score,
      };
    });
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();

    const request = {
      indexEndpoint: this.indexEndpointPath,
      deployedIndexId: this.config.deploymentIndexId,
      queries: [
        {
          datapoint: {
            datapointId: vectorId,
          },
          neighborCount: 1,
        },
      ],
      returnFullDatapoint: true,
    };

    const [response] = await this.matchClient.findNeighbors(request);

    if (
      !response ||
      !response.nearestNeighbors ||
      response.nearestNeighbors.length === 0
    ) {
      return null;
    }

    const neighbors = response.nearestNeighbors[0].neighbors || [];
    if (neighbors.length === 0) {
      return null;
    }

    const neighbor = neighbors[0];
    const payload: Record<string, any> = {};
    if (neighbor.datapoint?.restricts) {
      for (const restrict of neighbor.datapoint.restricts) {
        if (restrict.allowList && restrict.allowList.length > 0) {
          payload[restrict.namespace] = restrict.allowList[0];
        }
      }
    }

    const score =
      neighbor.distance !== undefined
        ? Math.max(0.0, 1.0 - neighbor.distance)
        : undefined;
    return {
      id: neighbor.datapoint.datapointId,
      payload,
      score,
    };
  }

  async keywordSearch(
    query: string,
    topK?: number,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    return null;
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();

    // Verify existence first
    const existing = await this.get(vectorId);
    if (!existing) {
      return;
    }

    const datapoint = this._createDatapoint(vectorId, vector, payload);
    await this.indexClient.upsertDatapoints({
      index: this.indexPath,
      datapoints: [datapoint],
    });
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    try {
      await this.indexClient.removeDatapoints({
        index: this.indexPath,
        datapointIds: [vectorId],
      });
    } catch (error: any) {
      // Ignore if not found
      if (error.code !== 5) {
        // 5 is NOT_FOUND in gRPC
        throw error;
      }
    }
  }

  async deleteCol(): Promise<void> {
    console.warn(
      "Delete collection operation is not supported for Google Matching Engine",
    );
  }

  async list(
    filters?: SearchFilters,
    topK: number = 10000,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    // We do not have dimension natively, usually 768 or 1536.
    // Vertex AI returns error if vector size is wrong, but some setups might allow empty vector.
    // In Python SDK, it uses a zero vector of size 768.
    const dimension = this.config.dimension || 768;
    const zeroVector = Array(dimension).fill(0.0);

    const results = await this.search(zeroVector, topK, filters);
    return [results, results.length];
  }

  private generateUUID(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      function (c) {
        const r = (Math.random() * 16) | 0;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      },
    );
  }

  async getUserId(): Promise<string> {
    // Vertex AI doesn't easily let us create arbitrary new indexes dynamically.
    // So we use a special datapoint in the same index, with a specific ID.
    const userIdDatapointId = "mem0-user-id-record";
    const existing = await this.get(userIdDatapointId);
    if (existing && existing.payload?.user_id) {
      return existing.payload.user_id;
    }

    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

    await this.setUserId(randomUserId);
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    const userIdDatapointId = "mem0-user-id-record";
    const dimension = this.config.dimension || 768;
    const zeroVector = Array(dimension).fill(0.0);

    const datapoint = this._createDatapoint(userIdDatapointId, zeroVector, {
      user_id: userId,
    });
    await this.indexClient.upsertDatapoints({
      index: this.indexPath,
      datapoints: [datapoint],
    });
  }
}
