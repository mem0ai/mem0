import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
// @ts-ignore - @google-cloud/aiplatform is a peer dependency
import aiplatform from "@google-cloud/aiplatform";
// @ts-ignore - @google-cloud/aiplatform is a peer dependency
import { GoogleAuth } from "google-auth-library";

interface VertexAIVectorSearchConfig extends VectorStoreConfig {
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
  private projectId: string;
  private projectNumber: string;
  private region: string;
  private endpointId: string;
  private indexId: string;
  private deploymentIndexId: string;
  private collectionName: string;
  private vectorSearchApiEndpoint?: string;
  private index: any;
  private indexEndpoint: any;
  private _initPromise?: Promise<void>;
  private userId: string = "";

  constructor(config: VertexAIVectorSearchConfig) {
    // Handle collection_name/deployment_index_id mapping
    if (config.collectionName && !config.deploymentIndexId) {
      config.deploymentIndexId = config.collectionName;
    } else if (config.deploymentIndexId && !config.collectionName) {
      config.collectionName = config.deploymentIndexId;
    }

    this.projectId = config.projectId;
    this.projectNumber = config.projectNumber;
    this.region = config.region;
    this.endpointId = config.endpointId;
    this.indexId = config.indexId;
    this.deploymentIndexId = config.deploymentIndexId;
    this.collectionName = config.collectionName || config.indexId;
    this.vectorSearchApiEndpoint = config.vectorSearchApiEndpoint;

    // Initialize Vertex AI with credentials if provided
    const initArgs: any = {
      project: this.projectId,
      location: this.region,
    };

    if (config.credentialsPath) {
      const auth = new GoogleAuth({
        keyFilename: config.credentialsPath,
      });
      initArgs.credentials = auth;
    } else if (config.serviceAccountJson) {
      const auth = new GoogleAuth({
        credentials: config.serviceAccountJson,
      });
      initArgs.credentials = auth;
    }

    try {
      aiplatform.init(initArgs);

      // Initialize index
      const indexPath = `projects/${this.projectNumber}/locations/${this.region}/indexes/${this.indexId}`;
      this.index = new aiplatform.MatchingEngineIndex({ indexName: indexPath });

      // Initialize endpoint
      this.indexEndpoint = new aiplatform.MatchingEngineIndexEndpoint({
        indexEndpointName: this.endpointId,
      });
    } catch (error) {
      throw new Error(`Failed to initialize Vertex AI Vector Search: ${error}`);
    }

    this.initialize().catch(console.error);
  }

  private createRestriction(key: string, value: any): any {
    const strValue = value !== null && value !== undefined ? String(value) : "";
    return new aiplatform.v1.IndexDatapoint.Restriction({
      namespace: key,
      allowList: [strValue],
    });
  }

  private createDatapoint(
    vectorId: string,
    vector: number[],
    payload?: Record<string, any>
  ): any {
    const restrictions: any[] = [];

    if (payload) {
      for (const [key, value] of Object.entries(payload)) {
        restrictions.push(this.createRestriction(key, value));
      }
    }

    return new aiplatform.v1.IndexDatapoint({
      datapointId: vectorId,
      featureVector: vector,
      restricts: restrictions,
    });
  }

  private generateUUID(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[]
  ): Promise<void> {
    if (!vectors || vectors.length === 0) {
      throw new Error("No vectors provided for insertion");
    }

    if (payloads && payloads.length !== vectors.length) {
      throw new Error(
        `Number of payloads (${payloads.length}) does not match number of vectors (${vectors.length})`
      );
    }

    if (ids && ids.length !== vectors.length) {
      throw new Error(
        `Number of ids (${ids.length}) does not match number of vectors (${vectors.length})`
      );
    }

    const datapoints = vectors.map((vector, idx) =>
      this.createDatapoint(
        ids[idx] || this.generateUUID(),
        vector,
        payloads && idx < payloads.length ? payloads[idx] : undefined
      )
    );

    await this.index.upsertDatapoints({ datapoints });
  }

  async keywordSearch(): Promise<null> {
    // Vertex AI hybrid search requires sparse embeddings configuration
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters
  ): Promise<VectorStoreResult[]> {
    const filterNamespaces: any[] = [];
    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
          filterNamespaces.push(
            new aiplatform.matching_engine.matching_engine_index_endpoint.Namespace({
              name: key,
              allowTokens: [String(value)],
              denyTokens: [],
            })
          );
        } else if (typeof value === "object" && value !== null && !Array.isArray(value)) {
          const includes = (value as any).include || [];
          const excludes = (value as any).exclude || [];
          filterNamespaces.push(
            new aiplatform.matching_engine.matching_engine_index_endpoint.Namespace({
              name: key,
              allowTokens: includes.map(String),
              denyTokens: excludes.map(String),
            })
          );
        }
      }
    }

    const response = await this.indexEndpoint.findNeighbors({
      deployedIndexId: this.deploymentIndexId,
      queries: [query],
      numNeighbors: topK,
      filter: filterNamespaces.length > 0 ? filterNamespaces : undefined,
      returnFullDatapoint: true,
    });

    if (!response || response.length === 0 || response[0].length === 0) {
      return [];
    }

    const results: VectorStoreResult[] = [];
    for (const neighbor of response[0]) {
      const payload: Record<string, any> = {};
      if (neighbor.restricts) {
        for (const restrict of neighbor.restricts) {
          if (restrict.name && restrict.allowTokens && restrict.allowTokens.length > 0) {
            payload[restrict.name] = restrict.allowTokens[0];
          }
        }
      }

      const score = neighbor.distance !== null && neighbor.distance !== undefined
        ? Math.max(0.0, 1.0 - neighbor.distance)
        : undefined;

      results.push({
        id: neighbor.id,
        score,
        payload,
      });
    }

    return results;
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    if (!this.vectorSearchApiEndpoint) {
      throw new Error("vectorSearchApiEndpoint is required for get operation");
    }

    const vectorSearchClient = new aiplatform.v1.MatchServiceClient({
      apiEndpoint: this.vectorSearchApiEndpoint,
    });

    const datapoint = new aiplatform.v1.IndexDatapoint({ datapointId: vectorId });
    const query = new aiplatform.v1.FindNeighborsRequest.Query({
      datapoint,
      neighborCount: 1,
    });

    const request = new aiplatform.v1.FindNeighborsRequest({
      indexEndpoint: `projects/${this.projectNumber}/locations/${this.region}/indexEndpoints/${this.endpointId}`,
      deployedIndexId: this.deploymentIndexId,
      queries: [query],
      returnFullDatapoint: true,
    });

    try {
      const response = await vectorSearchClient.findNeighbors(request);

      if (response.nearestNeighbors && response.nearestNeighbors.length > 0) {
        const nearest = response.nearestNeighbors[0];
        if (nearest.neighbors && nearest.neighbors.length > 0) {
          const neighbor = nearest.neighbors[0];

          const payload: Record<string, any> = {};
          if (neighbor.datapoint.restricts) {
            for (const restrict of neighbor.datapoint.restricts) {
              if (restrict.allowList && restrict.allowList.length > 0) {
                payload[restrict.namespace] = restrict.allowList[0];
              }
            }
          }

          const score = neighbor.distance !== null && neighbor.distance !== undefined
            ? Math.max(0.0, 1.0 - neighbor.distance)
            : undefined;

          return {
            id: neighbor.datapoint.datapointId,
            score,
            payload,
          };
        }
      }

      return null;
    } catch (error: any) {
      if (error.code === 5 || error.code === 404) {
        // NOT_FOUND
        return null;
      }
      if (error.code === 7 || error.code === 403) {
        // PERMISSION_DENIED
        return null;
      }
      throw error;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>
  ): Promise<void> {
    // Check if vector exists first
    const existing = await this.get(vectorId);
    if (!existing) {
      throw new Error(`Vector ID not found: ${vectorId}`);
    }

    const datapoint = this.createDatapoint(vectorId, vector, payload);
    await this.index.upsertDatapoints({ datapoints: [datapoint] });
  }

  async delete(vectorId: string): Promise<void> {
    try {
      await this.index.removeDatapoints({ datapointIds: [vectorId] });
    } catch (error: any) {
      if (error.code === 5 || error.code === 404) {
        // NOT_FOUND - already deleted, consider it a success
        return;
      }
      if (error.code === 7 || error.code === 403) {
        // PERMISSION_DENIED
        throw new Error(`Permission denied: ${error.message}`);
      }
      throw error;
    }
  }

  async deleteCol(): Promise<void> {
    // Delete collection operation is not supported through the API
    // Indexes are managed through Google Cloud Console
    console.warn("Delete collection operation is not supported for Vertex AI Vector Search");
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100
  ): Promise<[VectorStoreResult[], number]> {
    // Use a zero vector for the search as a workaround
    const dimension = 768; // This should be configurable based on the model
    const zeroVector = new Array(dimension).fill(0.0);

    const results = await this.search(zeroVector, topK, filters);
    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    // For Vertex AI, we'll use a simple in-memory approach
    // In a real implementation, you might want to store this in the index metadata
    if (!this.userId) {
      this.userId = Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15);
    }
    return this.userId;
  }

  async setUserId(userId: string): Promise<void> {
    this.userId = userId;
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    // Vertex AI indexes are pre-created through Google Cloud Console
    // No initialization needed beyond what's done in constructor
    return;
  }
}
