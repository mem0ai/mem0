import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface TurbopufferConfig extends VectorStoreConfig {
  apiKey?: string;
  region?: string;
  collectionName: string;
  distanceMetric?: string;
  batchSize?: number;
}

export class TurbopufferDB implements VectorStore {
  private clientInstance?: any;
  private clientPromise?: Promise<any>;
  private readonly apiKey: string;
  private readonly region: string;
  private readonly collectionName: string;
  private readonly distanceMetric: string;
  private readonly batchSize: number;

  constructor(config: TurbopufferConfig) {
    const apiKey = config.apiKey ?? process.env.TURBOPUFFER_API_KEY;
    if (!apiKey) {
      throw new Error(
        "Turbopuffer API key is required. Provide it via config.apiKey or the TURBOPUFFER_API_KEY environment variable.",
      );
    }

    this.apiKey = apiKey;
    this.region = config.region ?? "gcp-us-central1";
    this.collectionName = config.collectionName;
    this.distanceMetric = config.distanceMetric ?? "cosine_distance";
    this.batchSize = config.batchSize ?? 100;
  }

  /**
   * Lazily construct (or reuse) the Turbopuffer client, importing the optional
   * `@turbopuffer/turbopuffer` peer only when the store is first used so
   * consumers that never touch Turbopuffer don't need it installed.
   */
  private async getClient(): Promise<any> {
    if (this.clientInstance) return this.clientInstance;
    if (!this.clientPromise) {
      this.clientPromise = this.createClient();
    }
    this.clientInstance = await this.clientPromise;
    return this.clientInstance;
  }

  private async createClient(): Promise<any> {
    let sdk: any;
    try {
      sdk = await import("@turbopuffer/turbopuffer");
    } catch {
      throw new Error(
        "The '@turbopuffer/turbopuffer' package is required to use the Turbopuffer vector store. Install it with: npm install @turbopuffer/turbopuffer",
      );
    }

    // @turbopuffer/turbopuffer ships `Turbopuffer` as both the default export
    // and a named export pointing at the same class. Use `.default` since
    // that's what a plain `import Turbopuffer from "..."` resolves to (and
    // what test doubles for this module mock).
    return new sdk.default({
      apiKey: this.apiKey,
      region: this.region,
    });
  }

  private async getNs(): Promise<any> {
    const client = await this.getClient();
    return client.namespace(this.collectionName);
  }

  private async getMigrationsNs(): Promise<any> {
    const client = await this.getClient();
    return client.namespace(this.collectionName + "_migrations");
  }

  async initialize(): Promise<void> {
    // no-op: Turbopuffer creates namespaces on first write
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const ns = await this.getNs();
    for (let i = 0; i < vectors.length; i += this.batchSize) {
      const batchVectors = vectors.slice(i, i + this.batchSize);
      const batchIds = ids.slice(i, i + this.batchSize);
      const batchPayloads = payloads.slice(i, i + this.batchSize);

      const upsert_rows = batchVectors.map((vector, j) => ({
        ...batchPayloads[j],
        id: batchIds[j],
        vector,
      }));

      await ns.write({
        upsert_rows,
        distance_metric: this.distanceMetric as any,
      });
    }
  }

  async search(
    query: number[],
    topK?: number,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const queryParams: any = {
      rank_by: ["vector", "ANN", query],
      top_k: topK ?? 5,
      include_attributes: true,
    };

    const tpufFilters = this.convertFilters(filters);
    if (tpufFilters !== null) queryParams.filters = tpufFilters;

    const ns = await this.getNs();
    try {
      const result = await ns.query(queryParams);
      return this.parseRows(result.rows ?? []);
    } catch (err) {
      console.error("Turbopuffer search error:", err);
      return [];
    }
  }

  async keywordSearch(): Promise<null> {
    return null;
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const ns = await this.getNs();
    try {
      const result = await ns.query({
        rank_by: ["id", "asc"] as any,
        top_k: 1,
        include_attributes: true,
        filters: ["id", "Eq", vectorId] as any,
      });
      const rows = result.rows ?? [];
      return rows.length ? this.parseRows(rows)[0] : null;
    } catch (err) {
      console.error("Turbopuffer get error:", err);
      return null;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const ns = await this.getNs();
    if (vector && vector.length > 0) {
      await ns.write({
        upsert_rows: [{ ...payload, id: vectorId, vector }],
        distance_metric: this.distanceMetric as any,
      });
    } else {
      await ns.write({
        patch_rows: [{ ...payload, id: vectorId }],
      });
    }
  }

  async delete(vectorId: string): Promise<void> {
    const ns = await this.getNs();
    await ns.write({ deletes: [vectorId] });
  }

  async deleteCol(): Promise<void> {
    const ns = await this.getNs();
    await ns.deleteAll();
  }

  async list(
    filters?: SearchFilters,
    topK?: number,
  ): Promise<[VectorStoreResult[], number]> {
    const queryParams: any = {
      rank_by: ["id", "asc"],
      top_k: topK ?? 100,
      include_attributes: true,
    };

    const tpufFilters = this.convertFilters(filters);
    if (tpufFilters !== null) queryParams.filters = tpufFilters;

    const ns = await this.getNs();
    try {
      const result = await ns.query(queryParams);
      const rows = this.parseRows(result.rows ?? []);
      return [rows, rows.length];
    } catch (err) {
      console.error("Turbopuffer list error:", err);
      return [[], 0];
    }
  }

  async getUserId(): Promise<string> {
    try {
      const migrationsNs = await this.getMigrationsNs();
      let rows: any[] = [];
      try {
        const result = await migrationsNs.query({
          rank_by: ["id", "asc"] as any,
          top_k: 1,
          include_attributes: true,
        });
        rows = result.rows ?? [];
      } catch (err: any) {
        // The migrations namespace is created lazily on first write, so the
        // very first read 404s. Treat that as "no id yet" and fall through to
        // create one; surface any other error (auth, rate limit, network).
        if (err?.status !== 404) throw err;
      }
      if (rows.length > 0 && rows[0].user_id) {
        return String(rows[0].user_id);
      }
      const randomId =
        Math.random().toString(36).slice(2, 15) +
        Math.random().toString(36).slice(2, 15);
      await migrationsNs.write({
        upsert_rows: [{ id: "1", vector: [0.0], user_id: randomId }],
        distance_metric: "cosine_distance" as any,
      });
      return randomId;
    } catch (err) {
      console.error("Error getting user ID:", err);
      throw err;
    }
  }

  async setUserId(userId: string): Promise<void> {
    try {
      const migrationsNs = await this.getMigrationsNs();
      await migrationsNs.write({
        upsert_rows: [{ id: "1", vector: [0.0], user_id: userId }],
        distance_metric: "cosine_distance" as any,
      });
    } catch (err) {
      console.error("Error setting user ID:", err);
      throw err;
    }
  }

  private convertFilters(filters?: SearchFilters): any {
    if (!filters || Object.keys(filters).length === 0) return null;

    const conditions: any[] = [];
    for (const [key, value] of Object.entries(filters)) {
      if (
        typeof value === "object" &&
        value !== null &&
        !Array.isArray(value)
      ) {
        if ("gte" in value) conditions.push([key, "Gte", value.gte]);
        if ("lte" in value) conditions.push([key, "Lte", value.lte]);
        if ("gt" in value) conditions.push([key, "Gt", value.gt]);
        if ("lt" in value) conditions.push([key, "Lt", value.lt]);
      } else {
        conditions.push([key, "Eq", value]);
      }
    }

    if (conditions.length === 0) return null;
    if (conditions.length === 1) return conditions[0];
    return ["And", conditions];
  }

  private parseRows(rows: any[]): VectorStoreResult[] {
    return rows.map((row) => {
      const { id, $dist, vector, ...rest } = row;
      const score = $dist != null ? 1 - $dist : undefined;
      return { id: String(id), payload: rest, score };
    });
  }
}
