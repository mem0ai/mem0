import Cloudflare from "cloudflare";
import type { Vectorize, VectorizeVector } from "@cloudflare/workers-types";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface VectorizeConfig extends VectorStoreConfig {
  apiKey?: string;
  indexName: string;
  accountId: string;
  // binding?: Vectorize; // TODO - Optional binding for Cloudflare Workers
}

interface CloudflareVector {
  id: string;
  values: number[];
  metadata?: Record<string, any>;
}

export class VectorizeDB implements VectorStore {
  private client: Cloudflare | null = null;
  private dimensions: number;
  private indexName: string;
  private accountId: string;
  private binding?: Vectorize; // TODO - Optional binding for Cloudflare Workers

  constructor(config: VectorizeConfig) {
    this.client = new Cloudflare({ apiToken: config.apiKey });
    this.dimensions = config.dimension || 1536;
    this.indexName = config.indexName;
    this.accountId = config.accountId;
    this.binding = config.binding; // TODO - Optional binding for Cloudflare Workers
    this.initialize().catch(console.error);
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[]
  ): Promise<void> {
    try {
      const vectorObjects: CloudflareVector[] = vectors.map(
        (vector, index) => ({
          id: ids[index],
          values: vector,
          metadata: payloads[index] || {},
        })
      );

      const ndjsonPayload = vectorObjects
        .map((v) => JSON.stringify(v))
        .join("\n");

      // TODO - Optional binding for Cloudflare Workers
      /*
      if (this.binding) {
        //this.binding.insert();
      }
      */

      const response = await fetch(
        `https://api.cloudflare.com/client/v4/accounts/${this.accountId}/vectorize/v2/indexes/${this.indexName}/insert`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/x-ndjson",
            Authorization: `Bearer ${this.client?.apiToken}`,
          },
          body: ndjsonPayload,
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Failed to insert vectors: ${response.status} ${errorText}`
        );
      }
    } catch (error) {
      console.error("Error inserting vectors:", error);
      throw new Error(
        `Failed to insert vectors: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters
  ): Promise<VectorStoreResult[]> {
    try {
      const result = await this.client?.vectorize.indexes.query(
        this.indexName,
        {
          account_id: this.accountId,
          vector: query,
          filter: filters,
          returnMetadata: "all",
          topK: limit,
        }
      );

      return (
        (result?.matches?.map((match) => ({
          id: match.id,
          payload: match.metadata,
          score: match.score,
        })) as VectorStoreResult[]) || []
      ); // Return empty array if result or matches is null/undefined
    } catch (error) {
      console.error("Error searching vectors:", error);
      throw new Error(
        `Failed to search vectors: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    try {
      const result = (await this.client?.vectorize.indexes.getByIds(
        this.indexName,
        {
          account_id: this.accountId,
          ids: [vectorId],
        }
      )) as any;

      if (!result?.length) return null;

      return {
        id: vectorId,
        payload: result[0].metadata,
      };
    } catch (error) {
      console.error("Error getting vector:", error);
      throw new Error(
        `Failed to get vector: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>
  ): Promise<void> {
    try {
      const data: VectorizeVector = {
        id: vectorId,
        values: vector,
        metadata: payload,
      };

      const response = await fetch(
        `https://api.cloudflare.com/client/v4/accounts/${this.accountId}/vectorize/v2/indexes/${this.indexName}/upsert`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/x-ndjson",
            Authorization: `Bearer ${this.client?.apiToken}`,
          },
          body: JSON.stringify(data) + "\n", // ndjson format
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Failed to update vector: ${response.status} ${errorText}`
        );
      }
    } catch (error) {
      console.error("Error updating vector:", error);
      throw new Error(
        `Failed to update vector: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  async delete(vectorId: string): Promise<void> {
    try {
      await this.client?.vectorize.indexes.deleteByIds(this.indexName, {
        account_id: this.accountId,
        ids: [vectorId],
      });
    } catch (error) {
      console.error("Error deleting vector:", error);
      throw new Error(
        `Failed to delete vector: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  async deleteCol(): Promise<void> {
    try {
      await this.client?.vectorize.indexes.delete(this.indexName, {
        account_id: this.accountId,
      });
    } catch (error) {
      console.error("Error deleting collection:", error);
      throw new Error(
        `Failed to delete collection: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  async list(
    filters?: SearchFilters,
    limit: number = 20
  ): Promise<[VectorStoreResult[], number]> {
    try {
      const result = await this.client?.vectorize.indexes.query(
        this.indexName,
        {
          account_id: this.accountId,
          vector: Array(this.dimensions).fill(0), // Dummy vector for listing
          filter: filters,
          topK: limit,
          returnMetadata: "all",
        }
      );

      const matches =
        (result?.matches?.map((match) => ({
          id: match.id,
          payload: match.metadata,
          score: match.score,
        })) as VectorStoreResult[]) || [];

      return [matches, matches.length];
    } catch (error) {
      console.error("Error listing vectors:", error);
      throw new Error(
        `Failed to list vectors: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  async getUserId(): Promise<string> {
    throw new Error("getUserId Not yet implemented");
  }

  async setUserId(userId: string): Promise<void> {
    throw new Error("setUserId Not yet implemented");
  }

  async initialize(): Promise<void> {
    try {
      const existing = new Set<string>();
      for await (const idx of this.client!.vectorize.indexes.list({
        account_id: this.accountId,
      })) {
        existing.add(idx.name!);
      }

      if (!existing.has(this.indexName)) {
        try {
          await this.client?.vectorize.indexes.create({
            account_id: this.accountId,
            name: this.indexName,
            config: {
              dimensions: this.dimensions,
              metric: "cosine",
            },
          });

          const properties = ["userId", "agentId", "runId"];

          for (const propertyName of properties) {
            await this.client?.vectorize.indexes.metadataIndex.create(
              this.indexName,
              {
                account_id: this.accountId,
                indexType: "string",
                propertyName,
              }
            );
          }
        } catch (err: any) {
          throw new Error(err);
        }
      }

      // check for metadata index
      const metadataIndexes =
        await this.client?.vectorize.indexes.metadataIndex.list(
          this.indexName,
          {
            account_id: this.accountId,
          }
        );
      const existingMetadataIndexes = new Set<string>();
      for (const metadataIndex of metadataIndexes?.metadataIndexes || []) {
        existingMetadataIndexes.add(metadataIndex.propertyName!);
      }
      const properties = ["userId", "agentId", "runId"];
      for (const propertyName of properties) {
        if (!existingMetadataIndexes.has(propertyName)) {
          await this.client?.vectorize.indexes.metadataIndex.create(
            this.indexName,
            {
              account_id: this.accountId,
              indexType: "string",
              propertyName,
            }
          );
        }
      }
    } catch (err: any) {
      throw new Error(err);
    }
  }
}
