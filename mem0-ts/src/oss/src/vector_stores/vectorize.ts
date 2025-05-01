import Cloudflare from "cloudflare";
import type { Vectorize, VectorizeVector } from "@cloudflare/workers-types";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface VectorizeConfig extends VectorStoreConfig {
  dimension?: number;
  apiKey?: string;
  indexName: string;
  accountId: string;
  binding?: Vectorize; // TODO - Optional binding for Cloudflare Workers
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
    const vectorObjects: CloudflareVector[] = vectors.map((vector, index) => ({
      id: ids[index],
      values: vector,
      metadata: payloads[index] || {},
    }));

    const ndjsonBody = vectorObjects.map((v) => JSON.stringify(v)).join("\n");

    // TODO - Optional binding for Cloudflare Workers
    if (this.binding) {
      //this.binding.insert();
    }

    // Error in Cloudflare ts package when inserting vectors
    /*
      const response = await this.client?.vectorize.indexes.insert(
        this.indexName,
        {
          account_id: this.accountId,
          body: JSON.stringify(test_data),
          "unparsable-behavior": "error",
        }
      );
      */

    const response = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${this.accountId}/vectorize/v2/indexes/${this.indexName}/insert`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/x-ndjson",
          Authorization: `Bearer ${this.client?.apiToken}`,
        },
        body: ndjsonBody,
      }
    );
  }

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters
  ): Promise<VectorStoreResult[]> {
    const result = await this.client?.vectorize.indexes.query(this.indexName, {
      account_id: this.accountId,
      vector: query,
      filter: filters,
      returnMetadata: "all",
      topK: limit,
    });

    return result?.matches?.map((match) => ({
      id: match.id,
      payload: match.metadata,
      score: match.score,
    })) as VectorStoreResult[];
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
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
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>
  ): Promise<void> {
    const data: VectorizeVector = {
      id: vectorId,
      values: vector,
      metadata: payload,
    };

    await fetch(
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
  }

  async delete(vectorId: string): Promise<void> {
    await this.client?.vectorize.indexes.deleteByIds(this.indexName, {
      account_id: this.accountId,
      ids: [vectorId],
    });
  }

  async deleteCol(): Promise<void> {
    await this.client?.vectorize.indexes.delete(this.indexName, {
      account_id: this.accountId,
    });
  }

  async list(
    filters?: SearchFilters,
    limit: number = 20
  ): Promise<[VectorStoreResult[], number]> {
    const result = await this.client?.vectorize.indexes.query(this.indexName, {
      account_id: this.accountId,
      vector: Array(this.dimensions).fill(0), // Dummy vector for listing
      filter: filters,
      topK: limit,
      returnMetadata: "all",
    });

    return [
      result?.matches?.map((match) => ({
        id: match.id,
        payload: match.metadata,
        score: match.score,
      })) as VectorStoreResult[],
      result?.matches?.length || 0,
    ];
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
