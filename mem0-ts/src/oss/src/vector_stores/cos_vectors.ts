import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import * as crypto from "crypto";

/**
 * Configuration interface for COS Vectors vector store
 */
interface CosVectorsConfig extends VectorStoreConfig {
  /** Vector bucket name */
  bucketName: string;
  /** Vector index name, default "mem0" */
  indexName?: string;
  /** Tencent Cloud region */
  region: string;
  /** Vector dimension, default 1536 */
  embeddingModelDims?: number;
  /** Tencent Cloud SecretId */
  secretId: string;
  /** Tencent Cloud SecretKey */
  secretKey: string;
  /** Temporary token (optional) */
  token?: string;
  /** Distance metric, default "cosine" */
  distanceMetric?: string;
  /** Use internal access, default false */
  internalAccess?: boolean;
}

/**
 * COS HMAC-SHA1 signer for generating request authentication signatures
 */
class CosAuth {
  private secretId: string;
  private secretKey: string;
  private token?: string;

  constructor(secretId: string, secretKey: string, token?: string) {
    this.secretId = secretId;
    this.secretKey = secretKey;
    this.token = token;
  }

  /**
   * Generate Authorization header for COS requests
   * using HMAC-SHA1 signing algorithm
   */
  sign(method: string, path: string, headers: Record<string, string>): string {
    const now = Math.floor(Date.now() / 1000);
    const expireTime = now + 600; // 签名有效期 10 分钟
    const keyTime = `${now};${expireTime}`;

    // 1. Generate SignKey
    const signKey = crypto
      .createHmac("sha1", this.secretKey)
      .update(keyTime)
      .digest("hex");

    // 2. Generate hash of HttpString
    const httpString = `${method.toLowerCase()}\n${path}\n\n\n`;
    const sha1edHttpString = crypto
      .createHash("sha1")
      .update(httpString)
      .digest("hex");

    // 3. Generate StringToSign
    const stringToSign = `sha1\n${keyTime}\n${sha1edHttpString}\n`;

    // 4. Generate signature
    const signature = crypto
      .createHmac("sha1", signKey)
      .update(stringToSign)
      .digest("hex");

    return (
      `q-sign-algorithm=sha1` +
      `&q-ak=${this.secretId}` +
      `&q-sign-time=${keyTime}` +
      `&q-key-time=${keyTime}` +
      `&q-header-list=` +
      `&q-url-param-list=` +
      `&q-signature=${signature}`
    );
  }

  getToken(): string | undefined {
    return this.token;
  }
}

/**
 * COS Vectors TypeScript vector store implementation
 *
 * Based on Tencent Cloud COS Vectors REST API, supports vector CRUD operations and similarity search.
 */
export class CosVectorsDB implements VectorStore {
  private readonly bucketName: string;
  private readonly indexName: string;
  private readonly region: string;
  private readonly embeddingModelDims: number;
  private readonly distanceMetric: string;
  private readonly internalAccess: boolean;
  private readonly auth: CosAuth;
  private readonly endpoint: string;
  private initialized: boolean = false;

  constructor(config: CosVectorsConfig) {
    // Parameter validation: ensure required config fields exist
    const requiredFields: { key: keyof CosVectorsConfig; label: string }[] = [
      { key: "bucketName", label: "bucketName（向量存储桶名称）" },
      { key: "region", label: "region（腾讯云地域）" },
      { key: "secretId", label: "secretId（腾讯云 SecretId）" },
      { key: "secretKey", label: "secretKey（腾讯云 SecretKey）" },
    ];
    for (const { key, label } of requiredFields) {
      if (!config[key]) {
        throw new Error(
          `CosVectorsDB 初始化失败：缺少必需的配置项 ${label}，请检查 vectorStore.config 配置`,
        );
      }
    }

    this.bucketName = config.bucketName;
    this.indexName = config.indexName || "mem0";
    this.region = config.region;
    this.embeddingModelDims = config.embeddingModelDims || 1536;
    this.distanceMetric = config.distanceMetric || "cosine";
    this.internalAccess = config.internalAccess || false;
    this.auth = new CosAuth(config.secretId, config.secretKey, config.token);
    this.endpoint = this.getEndpoint();

    this.initialize().catch(console.error);
  }

  /**
   * Get the COS Vectors access endpoint
   */
  private getEndpoint(): string {
    if (this.internalAccess) {
      return `http://vectors.${this.region}.internal.tencentcos.com`;
    }
    return `http://vectors.${this.region}.coslake.com`;
  }

  /**
   * Send HTTP request to COS Vectors API
   */
  private async request(
    action: string,
    body: Record<string, any>,
  ): Promise<any> {
    const path = `/${action}`;
    const url = `${this.endpoint}${path}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Authorization: this.auth.sign("post", path, {}),
    };

    const token = this.auth.getToken();
    if (token) {
      headers["x-cos-security-token"] = token;
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorData: any;
      try {
        errorData = JSON.parse(errorText);
      } catch {
        errorData = { message: errorText };
      }
      const errorCode = errorData?.code || errorData?.Code || "UnknownError";
      const errorMessage =
        errorData?.message || errorData?.Message || errorText;

      // Parse field-level error details from fieldList
      const fieldErrors: string[] = [];
      if (Array.isArray(errorData?.fieldList)) {
        for (const field of errorData.fieldList) {
          fieldErrors.push(`    - ${field.path}: ${field.message}`);
        }
      }

      // Output detailed response info for debugging
      console.error(
        `[COS Vectors] 请求失败:\n` +
          `  Action: ${action}\n` +
          `  URL: ${url}\n` +
          `  Status: ${response.status} ${response.statusText}\n` +
          `  ErrorCode: ${errorCode}\n` +
          `  ErrorMessage: ${errorMessage}\n` +
          (fieldErrors.length
            ? `  FieldErrors:\n${fieldErrors.join("\n")}\n`
            : "") +
          `  Response: ${errorText}`,
      );
      const error: any = new Error(
        `COS Vectors API error: ${action} - ${response.status} ${response.statusText} - ${errorCode}: ${errorMessage}` +
          (fieldErrors.length
            ? ` | Fields: ${errorData.fieldList.map((f: any) => `${f.path}(${f.message})`).join(", ")}`
            : ""),
      );
      error.statusCode = response.status;
      error.errorCode = errorCode;
      error.errorMessage = errorMessage;
      error.fieldList = errorData?.fieldList;
      throw error;
    }

    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return response.json();
    }
    return {};
  }

  /**
   * Check if error is "not found" type
   */
  private isNotFoundError(error: any): boolean {
    return (
      error?.errorCode === "NotFoundException" || error?.statusCode === 404
    );
  }

  /**
   * Ensure vector bucket exists, create if not
   */
  private async ensureBucketExists(): Promise<void> {
    try {
      await this.request("GetVectorBucket", {
        vectorBucketName: this.bucketName,
      });
      console.log(`Vector bucket '${this.bucketName}' already exists.`);
    } catch (error: any) {
      if (this.isNotFoundError(error)) {
        console.log(
          `Vector bucket '${this.bucketName}' not found. Creating it.`,
        );
        await this.request("CreateVectorBucket", {
          vectorBucketName: this.bucketName,
        });
        console.log(`Vector bucket '${this.bucketName}' created.`);
      } else {
        throw error;
      }
    }
  }

  /**
   * Ensure vector index exists, create if not
   */
  private async ensureIndexExists(
    indexName: string,
    dimension: number,
    distanceMetric: string,
  ): Promise<void> {
    try {
      await this.request("GetIndex", {
        vectorBucketName: this.bucketName,
        indexName: indexName,
      });
      console.log(
        `Index '${indexName}' already exists in bucket '${this.bucketName}'.`,
      );
    } catch (error: any) {
      if (this.isNotFoundError(error)) {
        console.log(
          `Index '${indexName}' not found in bucket '${this.bucketName}'. Creating it.`,
        );
        await this.request("CreateIndex", {
          vectorBucketName: this.bucketName,
          indexName: indexName,
          dataType: "float32",
          dimension: dimension,
          distanceMetric: distanceMetric,
        });
        console.log(`Index '${indexName}' created.`);
      } else {
        throw error;
      }
    }
  }

  /**
   * Parse COS Vectors returned data to unified format
   */
  private parseOutput(vectors: any[]): VectorStoreResult[] {
    return vectors.map((v: any) => {
      let payload = v.metadata || {};
      // metadata may be a JSON string
      if (typeof payload === "string") {
        try {
          payload = JSON.parse(payload);
        } catch {
          console.warn(`Failed to parse metadata for key ${v.key}`);
          payload = {};
        }
      }
      return {
        id: v.key,
        payload,
        score: v.distance,
      };
    });
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const vectorsToInsert = vectors.map((vec, i) => ({
      key: ids[i],
      data: { float32: vec },
      metadata: payloads[i] || {},
    }));

    await this.request("PutVectors", {
      vectorBucketName: this.bucketName,
      indexName: this.indexName,
      vectors: vectorsToInsert,
    });
  }

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const body: Record<string, any> = {
      vectorBucketName: this.bucketName,
      indexName: this.indexName,
      queryVector: { float32: query },
      topK: limit,
      returnMetaData: true,
      returnDistance: true,
    };

    if (filters) {
      console.log(
        "[CosVectorsDB] search filters:",
        JSON.stringify(filters, null, 2),
      );
      // Convert filters to Tencent Cloud vector database $and format
      const filterKeys = Object.keys(filters);
      if (filterKeys.length > 1) {
        // Use $and for multiple conditions
        body.filter = {
          $and: filterKeys.map((key) => ({ [key]: filters[key] })),
        };
      } else {
        // Use single condition directly
        body.filter = filters;
      }
    }

    const data = await this.request("QueryVectors", body);
    return this.parseOutput(data?.vectors || []);
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const data = await this.request("GetVectors", {
      vectorBucketName: this.bucketName,
      indexName: this.indexName,
      keys: [vectorId],
      returnData: false,
      returnMetaData: true,
    });

    const vectors = data?.vectors || [];
    if (!vectors.length) {
      return null;
    }
    return this.parseOutput(vectors)[0];
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    // COS Vectors uses PutVectors for overwrite update
    await this.insert([vector], [vectorId], [payload]);
  }

  async delete(vectorId: string): Promise<void> {
    await this.request("DeleteVectors", {
      vectorBucketName: this.bucketName,
      indexName: this.indexName,
      keys: [vectorId],
    });
  }

  async deleteCol(): Promise<void> {
    await this.request("DeleteIndex", {
      vectorBucketName: this.bucketName,
      indexName: this.indexName,
    });
  }

  async list(
    filters?: SearchFilters,
    limit?: number,
  ): Promise<[VectorStoreResult[], number]> {
    if (filters) {
      console.warn(
        "COS Vectors `list` does not support metadata filtering. Ignoring filters.",
      );
    }

    let allVectors: any[] = [];
    let nextToken: string | undefined = undefined;
    let finished = false;

    while (!finished) {
      // Calculate batch size: if limit exists, use min of remaining and 1000, otherwise use API max 1000
      let batchSize: number;
      if (limit !== undefined) {
        const remaining = limit - allVectors.length;
        batchSize = Math.min(remaining, 1000);
      } else {
        batchSize = 1000;
      }

      const body: Record<string, any> = {
        vectorBucketName: this.bucketName,
        indexName: this.indexName,
        returnData: false,
        returnMetaData: true,
        maxResults: batchSize,
      };

      if (nextToken) {
        body.nextToken = nextToken;
      }

      const data = await this.request("ListVectors", body);
      allVectors = allVectors.concat(data?.vectors || []);

      // Truncate and stop pagination when limit is reached
      if (limit !== undefined && allVectors.length >= limit) {
        allVectors = allVectors.slice(0, limit);
        finished = true;
      } else if (data?.nextToken) {
        nextToken = data.nextToken;
      } else {
        finished = true;
      }
    }

    const results = this.parseOutput(allVectors);
    return [results, results.length];
  }

  /**
   * List all indexes under the bucket
   */
  async listIndexes(): Promise<string[]> {
    const data = await this.request("ListIndexes", {
      vectorBucketName: this.bucketName,
    });
    return (data?.indexes || []).map((idx: any) => idx.indexName);
  }

  /**
   * Get current index information
   */
  async getIndexInfo(): Promise<any> {
    const data = await this.request("GetIndex", {
      vectorBucketName: this.bucketName,
      indexName: this.indexName,
    });
    return data?.index || {};
  }

  async getUserId(): Promise<string> {
    try {
      // Try to get user_id from vector store
      const data = await this.request("GetVectors", {
        vectorBucketName: this.bucketName,
        indexName: this.indexName,
        keys: ["__mem0_user_id__"],
        returnData: false,
        returnMetaData: true,
      });

      const vectors = data?.vectors || [];
      if (vectors.length > 0) {
        const metadata = vectors[0].metadata || {};
        if (typeof metadata === "string") {
          try {
            const parsed = JSON.parse(metadata);
            if (parsed.user_id) return parsed.user_id;
          } catch {
            // ignore
          }
        } else if (metadata.user_id) {
          return metadata.user_id;
        }
      }
    } catch {
      // Vector does not exist, generate new user_id
    }

    // Generate a random user_id
    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

    // Store user_id (using zero vector)
    const zeroVector = new Array(this.embeddingModelDims).fill(0);
    await this.insert(
      [zeroVector],
      ["__mem0_user_id__"],
      [{ user_id: randomUserId }],
    );

    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    const zeroVector = new Array(this.embeddingModelDims).fill(0);
    await this.insert(
      [zeroVector],
      ["__mem0_user_id__"],
      [{ user_id: userId }],
    );
  }

  async initialize(): Promise<void> {
    if (this.initialized) return;
    await this.ensureBucketExists();
    await this.ensureIndexExists(
      this.indexName,
      this.embeddingModelDims,
      this.distanceMetric,
    );
    this.initialized = true;
  }
}
