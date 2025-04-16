import { VectorStore as LangchainVectorStoreInterface } from "@langchain/core/vectorstores";
import { Document } from "@langchain/core/documents";
import { VectorStore } from "./base"; // mem0's VectorStore interface
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

// Config specifically for the Langchain wrapper
interface LangchainStoreConfig extends VectorStoreConfig {
  client: LangchainVectorStoreInterface;
  // dimension might still be useful for validation if not automatically inferred
}

export class LangchainVectorStore implements VectorStore {
  private lcStore: LangchainVectorStoreInterface;
  private dimension?: number;
  private storeUserId: string = "anonymous-langchain-user"; // Simple in-memory user ID

  constructor(config: LangchainStoreConfig) {
    if (!config.client || typeof config.client !== "object") {
      throw new Error(
        "Langchain vector store provider requires an initialized Langchain VectorStore instance passed via the 'client' field.",
      );
    }
    // Basic checks for core methods
    if (
      typeof config.client.addVectors !== "function" ||
      typeof config.client.similaritySearchVectorWithScore !== "function"
    ) {
      throw new Error(
        "Provided Langchain 'client' does not appear to be a valid Langchain VectorStore (missing addVectors or similaritySearchVectorWithScore method).",
      );
    }

    this.lcStore = config.client;
    this.dimension = config.dimension;

    // Attempt to get dimension from the underlying store if not provided
    if (
      !this.dimension &&
      (this.lcStore as any).embeddings?.embeddingDimension
    ) {
      this.dimension = (this.lcStore as any).embeddings.embeddingDimension;
    }
    if (
      !this.dimension &&
      (this.lcStore as any).embedding?.embeddingDimension
    ) {
      this.dimension = (this.lcStore as any).embedding.embeddingDimension;
    }
    // If still no dimension, we might need to throw or warn, as it's needed for validation
    if (!this.dimension) {
      console.warn(
        "LangchainVectorStore: Could not determine embedding dimension. Input validation might be skipped.",
      );
    }
  }

  // --- Method Mappings ---

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    if (!ids || ids.length !== vectors.length) {
      throw new Error(
        "IDs array must be provided and have the same length as vectors.",
      );
    }
    if (this.dimension) {
      vectors.forEach((v, i) => {
        if (v.length !== this.dimension) {
          throw new Error(
            `Vector dimension mismatch at index ${i}. Expected ${this.dimension}, got ${v.length}`,
          );
        }
      });
    }

    // Convert payloads to Langchain Document metadata format
    const documents = payloads.map((payload, i) => {
      // Provide empty pageContent, store mem0 id and other data in metadata
      return new Document({
        pageContent: "", // Add required empty pageContent
        metadata: { ...payload, _mem0_id: ids[i] },
      });
    });

    // Use addVectors. Note: Langchain stores often generate their own internal IDs.
    // We store the mem0 ID in the metadata (`_mem0_id`).
    try {
      await this.lcStore.addVectors(vectors, documents, { ids }); // Pass mem0 ids if the store supports it
    } catch (e) {
      // Fallback if the store doesn't support passing ids directly during addVectors
      console.warn(
        "Langchain store might not support custom IDs on insert. Trying without IDs.",
        e,
      );
      await this.lcStore.addVectors(vectors, documents);
    }
  }

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters, // filters parameter is received but will be ignored
  ): Promise<VectorStoreResult[]> {
    if (this.dimension && query.length !== this.dimension) {
      throw new Error(
        `Query vector dimension mismatch. Expected ${this.dimension}, got ${query.length}`,
      );
    }

    // --- Remove filter processing logic ---
    // Filters passed via mem0 interface are not reliably translatable to generic Langchain stores.
    // let lcFilter: any = undefined;
    // if (filters && ...) { ... }
    // console.warn("LangchainVectorStore: Passing filters directly..."); // Remove warning

    // Call similaritySearchVectorWithScore WITHOUT the filter argument
    const results = await this.lcStore.similaritySearchVectorWithScore(
      query,
      limit,
      // Do not pass lcFilter here
    );

    // Map Langchain results [Document, score] back to mem0 VectorStoreResult
    return results.map(([doc, score]) => ({
      id: doc.metadata._mem0_id || "unknown_id",
      payload: doc.metadata,
      score: score,
    }));
  }

  // --- Methods with No Direct Langchain Equivalent (Throwing Errors) ---

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    // Most Langchain stores lack a direct getById. Simulation is inefficient.
    console.error(
      `LangchainVectorStore: The 'get' method is not directly supported by most Langchain VectorStores.`,
    );
    throw new Error(
      "Method 'get' not reliably supported by LangchainVectorStore wrapper.",
    );
    // Potential (inefficient) simulation:
    // Perform a search with a filter like { _mem0_id: vectorId }, limit 1.
    // This requires the underlying store to support filtering on _mem0_id.
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    // Updates often require delete + add in Langchain.
    console.error(
      `LangchainVectorStore: The 'update' method is not directly supported. Use delete followed by insert.`,
    );
    throw new Error(
      "Method 'update' not supported by LangchainVectorStore wrapper.",
    );
    // Possible implementation: Check if store has delete, call delete({_mem0_id: vectorId}), then insert.
  }

  async delete(vectorId: string): Promise<void> {
    // Check if the underlying store supports deletion by ID
    if (typeof (this.lcStore as any).delete === "function") {
      try {
        // We need to delete based on our stored _mem0_id.
        // Langchain's delete often takes its own internal IDs or filter.
        // Attempting deletion via filter is the most likely approach.
        console.warn(
          "LangchainVectorStore: Attempting delete via filter on '_mem0_id'. Success depends on the specific Langchain VectorStore's delete implementation.",
        );
        await (this.lcStore as any).delete({ filter: { _mem0_id: vectorId } });
        // OR if it takes IDs directly (less common for *our* IDs):
        // await (this.lcStore as any).delete({ ids: [vectorId] });
      } catch (e) {
        console.error(
          `LangchainVectorStore: Delete failed. Underlying store's delete method might expect different arguments or filters. Error: ${e}`,
        );
        throw new Error(`Delete failed in underlying Langchain store: ${e}`);
      }
    } else {
      console.error(
        `LangchainVectorStore: The underlying Langchain store instance does not seem to support a 'delete' method.`,
      );
      throw new Error(
        "Method 'delete' not available on the provided Langchain VectorStore client.",
      );
    }
  }

  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    // No standard list method in Langchain core interface.
    console.error(
      `LangchainVectorStore: The 'list' method is not supported by the generic LangchainVectorStore wrapper.`,
    );
    throw new Error(
      "Method 'list' not supported by LangchainVectorStore wrapper.",
    );
    // Could potentially be implemented if the underlying store has a specific list/scroll/query capability.
  }

  async deleteCol(): Promise<void> {
    console.error(
      `LangchainVectorStore: The 'deleteCol' method is not supported by the generic LangchainVectorStore wrapper.`,
    );
    throw new Error(
      "Method 'deleteCol' not supported by LangchainVectorStore wrapper.",
    );
  }

  // --- Wrapper-Specific Methods (In-Memory User ID) ---

  async getUserId(): Promise<string> {
    return this.storeUserId;
  }

  async setUserId(userId: string): Promise<void> {
    this.storeUserId = userId;
  }

  async initialize(): Promise<void> {
    // No specific initialization needed for the wrapper itself,
    // assuming the passed Langchain client is already initialized.
    return Promise.resolve();
  }
}
