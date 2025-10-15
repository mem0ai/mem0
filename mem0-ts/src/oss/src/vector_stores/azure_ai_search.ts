import {
  SearchClient,
  SearchIndexClient,
  AzureKeyCredential,
  SearchIndex,
  SearchField,
  SearchFieldDataType,
  SimpleField,
  VectorSearch,
  VectorSearchProfile,
  HnswAlgorithmConfiguration,
  ScalarQuantizationCompression,
  BinaryQuantizationCompression,
  VectorizedQuery,
} from "@azure/search-documents";
import { DefaultAzureCredential } from "@azure/identity";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

/**
 * Configuration interface for Azure AI Search vector store
 */
interface AzureAISearchConfig extends VectorStoreConfig {
  /**
   * Azure AI Search service name (e.g., "my-search-service")
   */
  serviceName: string;

  /**
   * Index/collection name to use
   */
  collectionName: string;

  /**
   * API key for authentication (if not provided, uses DefaultAzureCredential)
   */
  apiKey?: string;

  /**
   * Vector embedding dimensions
   */
  embeddingModelDims: number;

  /**
   * Compression type: 'none', 'scalar', or 'binary'
   * @default 'none'
   */
  compressionType?: "none" | "scalar" | "binary";

  /**
   * Use half precision (float16) instead of full precision (float32)
   * @default false
   */
  useFloat16?: boolean;

  /**
   * Enable hybrid search (combines vector + text search)
   * @default false
   */
  hybridSearch?: boolean;

  /**
   * Vector filter mode: 'preFilter' or 'postFilter'
   * @default 'preFilter'
   */
  vectorFilterMode?: string;
}

/**
 * Azure AI Search vector store implementation
 * Supports vector search with hybrid search, compression, and filtering
 */
export class AzureAISearch implements VectorStore {
  private searchClient: SearchClient<any>;
  private indexClient: SearchIndexClient;
  private readonly serviceName: string;
  private readonly indexName: string;
  private readonly embeddingModelDims: number;
  private readonly compressionType: "none" | "scalar" | "binary";
  private readonly useFloat16: boolean;
  private readonly hybridSearch: boolean;
  private readonly vectorFilterMode: string;
  private readonly apiKey: string | undefined;

  constructor(config: AzureAISearchConfig) {
    this.serviceName = config.serviceName;
    this.indexName = config.collectionName;
    this.embeddingModelDims = config.embeddingModelDims;
    this.compressionType = config.compressionType || "none";
    this.useFloat16 = config.useFloat16 || false;
    this.hybridSearch = config.hybridSearch || false;
    this.vectorFilterMode = config.vectorFilterMode || "preFilter";
    this.apiKey = config.apiKey;

    const serviceEndpoint = `https://${this.serviceName}.search.windows.net`;

    // Determine authentication: API key or DefaultAzureCredential
    const credential =
      this.apiKey && this.apiKey !== "" && this.apiKey !== "your-api-key"
        ? new AzureKeyCredential(this.apiKey)
        : new DefaultAzureCredential();

    // Initialize clients
    this.searchClient = new SearchClient(
      serviceEndpoint,
      this.indexName,
      credential,
    );

    this.indexClient = new SearchIndexClient(serviceEndpoint, credential);

    // Initialize the index
    this.initialize().catch(console.error);
  }

  /**
   * Initialize the Azure AI Search index if it doesn't exist
   */
  async initialize(): Promise<void> {
    try {
      const collections = await this.listCols();
      if (!collections.includes(this.indexName)) {
        await this.createCol();
      }
    } catch (error) {
      console.error("Error initializing Azure AI Search:", error);
      throw error;
    }
  }

  /**
   * Create a new index in Azure AI Search
   */
  private async createCol(): Promise<void> {
    // Determine vector type based on use_float16 setting
    const vectorType = this.useFloat16
      ? "Collection(Edm.Half)"
      : "Collection(Edm.Single)";

    // Configure compression settings
    const compressionConfigurations: Array<
      ScalarQuantizationCompression | BinaryQuantizationCompression
    > = [];
    let compressionName: string | undefined = undefined;

    if (this.compressionType === "scalar") {
      compressionName = "myCompression";
      compressionConfigurations.push({
        kind: "scalarQuantization",
        compressionName: compressionName,
      } as ScalarQuantizationCompression);
    } else if (this.compressionType === "binary") {
      compressionName = "myCompression";
      compressionConfigurations.push({
        kind: "binaryQuantization",
        compressionName: compressionName,
      } as BinaryQuantizationCompression);
    }

    // Define index fields
    const fields: SearchField[] = [
      {
        name: "id",
        type: "Edm.String",
        key: true,
      } as SimpleField,
      {
        name: "user_id",
        type: "Edm.String",
        filterable: true,
      } as SimpleField,
      {
        name: "run_id",
        type: "Edm.String",
        filterable: true,
      } as SimpleField,
      {
        name: "agent_id",
        type: "Edm.String",
        filterable: true,
      } as SimpleField,
      {
        name: "vector",
        type: vectorType as SearchFieldDataType,
        searchable: true,
        vectorSearchDimensions: this.embeddingModelDims,
        vectorSearchProfileName: "my-vector-config",
      } as SearchField,
      {
        name: "payload",
        type: "Edm.String",
        searchable: true,
      } as SearchField,
    ];

    // Configure vector search
    const vectorSearch: VectorSearch = {
      profiles: [
        {
          name: "my-vector-config",
          algorithmConfigurationName: "my-algorithms-config",
          compressionName:
            this.compressionType !== "none" ? compressionName : undefined,
        } as VectorSearchProfile,
      ],
      algorithms: [
        {
          kind: "hnsw",
          name: "my-algorithms-config",
        } as HnswAlgorithmConfiguration,
      ],
      compressions: compressionConfigurations,
    };

    // Create index
    const index: SearchIndex = {
      name: this.indexName,
      fields,
      vectorSearch,
    };

    await this.indexClient.createOrUpdateIndex(index);
  }

  /**
   * Generate a document for insertion
   */
  private generateDocument(
    vector: number[],
    payload: Record<string, any>,
    id: string,
  ): Record<string, any> {
    const document: Record<string, any> = {
      id,
      vector,
      payload: JSON.stringify(payload),
    };

    // Extract additional fields if they exist
    for (const field of ["user_id", "run_id", "agent_id"]) {
      if (field in payload) {
        document[field] = payload[field];
      }
    }

    return document;
  }

  /**
   * Insert vectors into the index
   */
  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    console.log(
      `Inserting ${vectors.length} vectors into index ${this.indexName}`,
    );

    const documents = vectors.map((vector, idx) =>
      this.generateDocument(vector, payloads[idx] || {}, ids[idx]),
    );

    const response = await this.searchClient.uploadDocuments(documents);

    // Check for errors
    for (const result of response.results) {
      if (!result.succeeded) {
        throw new Error(
          `Insert failed for document ${result.key}: ${result.errorMessage}`,
        );
      }
    }
  }

  /**
   * Sanitize filter keys to remove non-alphanumeric characters
   */
  private sanitizeKey(key: string): string {
    return key.replace(/[^\w]/g, "");
  }

  /**
   * Build OData filter expression from SearchFilters
   */
  private buildFilterExpression(filters: SearchFilters): string {
    const filterConditions: string[] = [];

    for (const [key, value] of Object.entries(filters)) {
      const safeKey = this.sanitizeKey(key);

      if (typeof value === "string") {
        // Escape single quotes in string values
        const safeValue = value.replace(/'/g, "''");
        filterConditions.push(`${safeKey} eq '${safeValue}'`);
      } else {
        filterConditions.push(`${safeKey} eq ${value}`);
      }
    }

    return filterConditions.join(" and ");
  }

  /**
   * Extract JSON from payload string
   * Handles cases where payload might have extra text
   */
  private extractJson(payload: string): string {
    try {
      // Try to parse as-is first
      JSON.parse(payload);
      return payload;
    } catch {
      // If that fails, try to extract JSON object
      const match = payload.match(/\{.*\}/s);
      return match ? match[0] : payload;
    }
  }

  /**
   * Search for similar vectors
   */
  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const filterExpression = filters
      ? this.buildFilterExpression(filters)
      : undefined;

    const vectorQuery: VectorizedQuery<any> = {
      kind: "vector",
      vector: query,
      kNearestNeighborsCount: limit,
      fields: ["vector"],
    };

    let searchResults;

    if (this.hybridSearch) {
      // Hybrid search: combines vector + text search
      searchResults = await this.searchClient.search("*", {
        vectorSearchOptions: {
          queries: [vectorQuery],
          filterMode: this.vectorFilterMode as any,
        },
        filter: filterExpression,
        top: limit,
        searchFields: ["payload"],
      });
    } else {
      // Pure vector search
      searchResults = await this.searchClient.search("*", {
        vectorSearchOptions: {
          queries: [vectorQuery],
          filterMode: this.vectorFilterMode as any,
        },
        filter: filterExpression,
        top: limit,
      });
    }

    const results: VectorStoreResult[] = [];

    for await (const result of searchResults.results) {
      const payloadStr = result.document.payload as string;
      const payload = JSON.parse(this.extractJson(payloadStr));

      results.push({
        id: result.document.id as string,
        score: result.score,
        payload,
      });
    }

    return results;
  }

  /**
   * Delete a vector by ID
   */
  async delete(vectorId: string): Promise<void> {
    const response = await this.searchClient.deleteDocuments([
      { id: vectorId },
    ]);

    for (const result of response.results) {
      if (!result.succeeded) {
        throw new Error(
          `Delete failed for document ${vectorId}: ${result.errorMessage}`,
        );
      }
    }

    console.log(
      `Deleted document with ID '${vectorId}' from index '${this.indexName}'.`,
    );
  }

  /**
   * Update a vector and its payload
   */
  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const document: Record<string, any> = { id: vectorId };

    if (vector) {
      document.vector = vector;
    }

    if (payload) {
      document.payload = JSON.stringify(payload);

      // Extract additional fields
      for (const field of ["user_id", "run_id", "agent_id"]) {
        if (field in payload) {
          document[field] = payload[field];
        }
      }
    }

    const response = await this.searchClient.mergeOrUploadDocuments([document]);

    for (const result of response.results) {
      if (!result.succeeded) {
        throw new Error(
          `Update failed for document ${vectorId}: ${result.errorMessage}`,
        );
      }
    }
  }

  /**
   * Retrieve a vector by ID
   */
  async get(vectorId: string): Promise<VectorStoreResult | null> {
    try {
      const result = await this.searchClient.getDocument(vectorId);
      const payloadStr = result.payload as string;
      const payload = JSON.parse(this.extractJson(payloadStr));

      return {
        id: result.id as string,
        payload,
      };
    } catch (error: any) {
      // Return null if document not found
      if (error?.statusCode === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * List all collections (indexes)
   */
  private async listCols(): Promise<string[]> {
    const names: string[] = [];

    for await (const index of this.indexClient.listIndexes()) {
      names.push(index.name);
    }

    return names;
  }

  /**
   * Delete the index
   */
  async deleteCol(): Promise<void> {
    await this.indexClient.deleteIndex(this.indexName);
  }

  /**
   * Get information about the index
   */
  private async colInfo(): Promise<{ name: string; fields: SearchField[] }> {
    const index = await this.indexClient.getIndex(this.indexName);
    return {
      name: index.name,
      fields: index.fields,
    };
  }

  /**
   * List all vectors in the index
   */
  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const filterExpression = filters
      ? this.buildFilterExpression(filters)
      : undefined;

    const searchResults = await this.searchClient.search("*", {
      filter: filterExpression,
      top: limit,
    });

    const results: VectorStoreResult[] = [];

    for await (const result of searchResults.results) {
      const payloadStr = result.document.payload as string;
      const payload = JSON.parse(this.extractJson(payloadStr));

      results.push({
        id: result.document.id as string,
        score: result.score,
        payload,
      });
    }

    return [results, results.length];
  }

  /**
   * Generate a random user ID
   */
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

  /**
   * Get user ID from memory_migrations collection
   * Required by VectorStore interface
   */
  async getUserId(): Promise<string> {
    try {
      // Check if memory_migrations index exists
      const collections = await this.listCols();
      const migrationIndexExists = collections.includes("memory_migrations");

      if (!migrationIndexExists) {
        // Create memory_migrations index
        const migrationIndex: SearchIndex = {
          name: "memory_migrations",
          fields: [
            {
              name: "id",
              type: "Edm.String",
              key: true,
            } as SimpleField,
            {
              name: "user_id",
              type: "Edm.String",
              searchable: false,
              filterable: true,
            } as SimpleField,
          ],
        };
        await this.indexClient.createOrUpdateIndex(migrationIndex);
      }

      // Try to get existing user_id
      const searchResults = await this.searchClient.search("*", {
        top: 1,
      });

      for await (const result of searchResults.results) {
        const userId = result.document.user_id as string;
        if (userId) {
          return userId;
        }
      }

      // Generate a random user_id if none exists
      const randomUserId =
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15);

      await this.searchClient.uploadDocuments([
        {
          id: this.generateUUID(),
          user_id: randomUserId,
        },
      ]);

      return randomUserId;
    } catch (error) {
      console.error("Error getting user ID:", error);
      throw error;
    }
  }

  /**
   * Set user ID in memory_migrations collection
   * Required by VectorStore interface
   */
  async setUserId(userId: string): Promise<void> {
    try {
      // Get existing point ID or generate new one
      const searchResults = await this.searchClient.search("*", {
        top: 1,
      });

      let pointId = this.generateUUID();

      for await (const result of searchResults.results) {
        pointId = result.document.id as string;
        break;
      }

      await this.searchClient.mergeOrUploadDocuments([
        {
          id: pointId,
          user_id: userId,
        },
      ]);
    } catch (error) {
      console.error("Error setting user ID:", error);
      throw error;
    }
  }

  /**
   * Reset the index by deleting and recreating it
   */
  async reset(): Promise<void> {
    console.log(`Resetting index ${this.indexName}...`);

    try {
      // Delete the index
      await this.deleteCol();

      // Recreate the index
      await this.createCol();
    } catch (error) {
      console.error(`Error resetting index ${this.indexName}:`, error);
      throw error;
    }
  }
}
