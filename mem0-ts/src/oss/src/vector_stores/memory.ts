import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface MemoryVector {
  id: string;
  vector: number[];
  payload: Record<string, any>;
}

export class MemoryVectorStore implements VectorStore {
  private vectors: Map<string, MemoryVector>;
  private dimension: number;

  constructor(config: VectorStoreConfig) {
    this.vectors = new Map();
    this.dimension = config.dimension || 1536; // Default OpenAI dimension
  }

  private cosineSimilarity(a: number[], b: number[]): number {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  private filterVector(vector: MemoryVector, filters?: SearchFilters): boolean {
    if (!filters) return true;
    return Object.entries(filters).every(
      ([key, value]) => vector.payload[key] === value,
    );
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    for (let i = 0; i < vectors.length; i++) {
      if (vectors[i].length !== this.dimension) {
        throw new Error(
          `Vector dimension mismatch. Expected ${this.dimension}, got ${vectors[i].length}`,
        );
      }
      this.vectors.set(ids[i], {
        id: ids[i],
        vector: vectors[i],
        payload: payloads[i],
      });
    }
  }

  async search(
    query: number[],
    limit: number = 10,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    if (query.length !== this.dimension) {
      throw new Error(
        `Query dimension mismatch. Expected ${this.dimension}, got ${query.length}`,
      );
    }

    const results: VectorStoreResult[] = [];
    for (const vector of this.vectors.values()) {
      if (this.filterVector(vector, filters)) {
        const score = this.cosineSimilarity(query, vector.vector);
        results.push({
          id: vector.id,
          payload: vector.payload,
          score,
        });
      }
    }

    results.sort((a, b) => (b.score || 0) - (a.score || 0));
    return results.slice(0, limit);
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const vector = this.vectors.get(vectorId);
    if (!vector) return null;
    return {
      id: vector.id,
      payload: vector.payload,
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    if (vector.length !== this.dimension) {
      throw new Error(
        `Vector dimension mismatch. Expected ${this.dimension}, got ${vector.length}`,
      );
    }
    const existing = this.vectors.get(vectorId);
    if (!existing) throw new Error(`Vector with ID ${vectorId} not found`);
    this.vectors.set(vectorId, {
      id: vectorId,
      vector,
      payload,
    });
  }

  async delete(vectorId: string): Promise<void> {
    this.vectors.delete(vectorId);
  }

  async deleteCol(): Promise<void> {
    this.vectors.clear();
  }

  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const results: VectorStoreResult[] = [];
    for (const vector of this.vectors.values()) {
      if (this.filterVector(vector, filters)) {
        results.push({
          id: vector.id,
          payload: vector.payload,
        });
      }
    }
    return [results.slice(0, limit), results.length];
  }
}
