import { createClient } from "redis";
import type {
  RedisClientType,
  RedisDefaultModules,
  RedisFunctions,
  RedisModules,
  RedisScripts,
} from "redis";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface RedisConfig extends VectorStoreConfig {
  redisUrl: string;
  collectionName: string;
  embeddingModelDims: number;
  username?: string;
  password?: string;
}

interface RedisField {
  name: string;
  type: string;
  attrs?: {
    distance_metric: string;
    algorithm: string;
    datatype: string;
    dims?: number;
  };
}

interface RedisSchema {
  index: {
    name: string;
    prefix: string;
  };
  fields: RedisField[];
}

interface RedisEntry {
  memory_id: string;
  hash: string;
  memory: string;
  created_at: number;
  updated_at?: number;
  embedding: Buffer;
  agent_id?: string;
  run_id?: string;
  user_id?: string;
  metadata?: string;
  [key: string]: any;
}

interface RedisDocument {
  id: string;
  value: {
    memory_id: string;
    hash: string;
    memory: string;
    created_at: string;
    updated_at?: string;
    agent_id?: string;
    run_id?: string;
    user_id?: string;
    metadata?: string;
    __vector_score?: number;
  };
}

interface RedisSearchResult {
  total: number;
  documents: RedisDocument[];
}

interface RedisModule {
  name: string;
  ver: number;
}

const DEFAULT_FIELDS: RedisField[] = [
  { name: "memory_id", type: "tag" },
  { name: "hash", type: "tag" },
  { name: "agent_id", type: "tag" },
  { name: "run_id", type: "tag" },
  { name: "user_id", type: "tag" },
  { name: "memory", type: "text" },
  { name: "metadata", type: "text" },
  { name: "created_at", type: "numeric" },
  { name: "updated_at", type: "numeric" },
  {
    name: "embedding",
    type: "vector",
    attrs: {
      algorithm: "flat",
      distance_metric: "cosine",
      datatype: "float32",
      dims: 0, // Will be set in constructor
    },
  },
];

const EXCLUDED_KEYS = new Set([
  "user_id",
  "agent_id",
  "run_id",
  "hash",
  "data",
  "created_at",
  "updated_at",
]);

// Utility function to convert object keys to snake_case
function toSnakeCase(obj: Record<string, any>): Record<string, any> {
  if (typeof obj !== "object" || obj === null) return obj;

  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) => [
      key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`),
      value,
    ]),
  );
}

// Utility function to convert object keys to camelCase
function toCamelCase(obj: Record<string, any>): Record<string, any> {
  if (typeof obj !== "object" || obj === null) return obj;

  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) => [
      key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()),
      value,
    ]),
  );
}

export class RedisDB implements VectorStore {
  private client: RedisClientType<
    RedisDefaultModules & RedisModules & RedisFunctions & RedisScripts
  >;
  private readonly indexName: string;
  private readonly indexPrefix: string;
  private readonly schema: RedisSchema;

  constructor(config: RedisConfig) {
    this.indexName = config.collectionName;
    this.indexPrefix = `mem0:${config.collectionName}`;

    this.schema = {
      index: {
        name: this.indexName,
        prefix: this.indexPrefix,
      },
      fields: DEFAULT_FIELDS.map((field) => {
        if (field.name === "embedding" && field.attrs) {
          return {
            ...field,
            attrs: {
              ...field.attrs,
              dims: config.embeddingModelDims,
            },
          };
        }
        return field;
      }),
    };

    this.client = createClient({
      url: config.redisUrl,
      username: config.username,
      password: config.password,
      socket: {
        reconnectStrategy: (retries) => {
          if (retries > 10) {
            console.error("Max reconnection attempts reached");
            return new Error("Max reconnection attempts reached");
          }
          return Math.min(retries * 100, 3000);
        },
      },
    });

    this.client.on("error", (err) => console.error("Redis Client Error:", err));
    this.client.on("connect", () => console.log("Redis Client Connected"));

    this.initialize().catch((err) => {
      console.error("Failed to initialize Redis:", err);
      throw err;
    });
  }

  private async createIndex(): Promise<void> {
    try {
      // Drop existing index if it exists
      try {
        await this.client.ft.dropIndex(this.indexName);
      } catch (error) {
        // Ignore error if index doesn't exist
      }

      // Create new index with proper vector configuration
      const schema: Record<string, any> = {};

      for (const field of this.schema.fields) {
        if (field.type === "vector") {
          schema[field.name] = {
            type: "VECTOR",
            ALGORITHM: "FLAT",
            TYPE: "FLOAT32",
            DIM: field.attrs!.dims,
            DISTANCE_METRIC: "COSINE",
            INITIAL_CAP: 1000,
          };
        } else if (field.type === "numeric") {
          schema[field.name] = {
            type: "NUMERIC",
            SORTABLE: true,
          };
        } else if (field.type === "tag") {
          schema[field.name] = {
            type: "TAG",
            SEPARATOR: "|",
          };
        } else if (field.type === "text") {
          schema[field.name] = {
            type: "TEXT",
            WEIGHT: 1,
          };
        }
      }

      // Create the index
      await this.client.ft.create(this.indexName, schema, {
        ON: "HASH",
        PREFIX: this.indexPrefix + ":",
        STOPWORDS: [],
      });
    } catch (error) {
      console.error("Error creating Redis index:", error);
      throw error;
    }
  }

  async initialize(): Promise<void> {
    try {
      await this.client.connect();
      console.log("Connected to Redis");

      // Check if Redis Stack modules are loaded
      const modulesResponse =
        (await this.client.moduleList()) as unknown as any[];

      // Parse module list to find search module
      const hasSearch = modulesResponse.some((module: any[]) => {
        const moduleMap = new Map();
        for (let i = 0; i < module.length; i += 2) {
          moduleMap.set(module[i], module[i + 1]);
        }
        return moduleMap.get("name")?.toLowerCase() === "search";
      });

      if (!hasSearch) {
        throw new Error(
          "RediSearch module is not loaded. Please ensure Redis Stack is properly installed and running.",
        );
      }

      // Create index with retries
      let retries = 0;
      const maxRetries = 3;
      while (retries < maxRetries) {
        try {
          await this.createIndex();
          console.log("Redis index created successfully");
          break;
        } catch (error) {
          console.error(
            `Error creating index (attempt ${retries + 1}/${maxRetries}):`,
            error,
          );
          retries++;
          if (retries === maxRetries) {
            throw error;
          }
          // Wait before retrying
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
    } catch (error) {
      if (error instanceof Error) {
        console.error("Error initializing Redis:", error.message);
      } else {
        console.error("Error initializing Redis:", error);
      }
      throw error;
    }
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const data = vectors.map((vector, idx) => {
      const payload = toSnakeCase(payloads[idx]);
      const id = ids[idx];

      // Create entry with required fields
      const entry: Record<string, any> = {
        memory_id: id,
        hash: payload.hash,
        memory: payload.data,
        created_at: new Date(payload.created_at).getTime(),
        embedding: new Float32Array(vector).buffer,
      };

      // Add optional fields
      ["agent_id", "run_id", "user_id"].forEach((field) => {
        if (field in payload) {
          entry[field] = payload[field];
        }
      });

      // Add metadata excluding specific keys
      entry.metadata = JSON.stringify(
        Object.fromEntries(
          Object.entries(payload).filter(([key]) => !EXCLUDED_KEYS.has(key)),
        ),
      );

      return entry;
    });

    try {
      // Insert all entries
      await Promise.all(
        data.map((entry) =>
          this.client.hSet(`${this.indexPrefix}:${entry.memory_id}`, {
            ...entry,
            embedding: Buffer.from(entry.embedding),
          }),
        ),
      );
    } catch (error) {
      console.error("Error during vector insert:", error);
      throw error;
    }
  }

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const snakeFilters = filters ? toSnakeCase(filters) : undefined;
    const filterExpr = snakeFilters
      ? Object.entries(snakeFilters)
          .filter(([_, value]) => value !== null)
          .map(([key, value]) => `@${key}:{${value}}`)
          .join(" ")
      : "*";

    const queryVector = new Float32Array(query).buffer;

    const searchOptions = {
      PARAMS: {
        vec: Buffer.from(queryVector),
      },
      RETURN: [
        "memory_id",
        "hash",
        "agent_id",
        "run_id",
        "user_id",
        "memory",
        "metadata",
        "created_at",
        "__vector_score",
      ],
      SORTBY: "__vector_score",
      DIALECT: 2,
      LIMIT: {
        from: 0,
        size: limit,
      },
    };

    try {
      const results = (await this.client.ft.search(
        this.indexName,
        `${filterExpr} =>[KNN ${limit} @embedding $vec AS __vector_score]`,
        searchOptions,
      )) as unknown as RedisSearchResult;

      return results.documents.map((doc) => {
        const resultPayload = {
          hash: doc.value.hash,
          data: doc.value.memory,
          created_at: new Date(parseInt(doc.value.created_at)).toISOString(),
          ...(doc.value.updated_at && {
            updated_at: new Date(parseInt(doc.value.updated_at)).toISOString(),
          }),
          ...(doc.value.agent_id && { agent_id: doc.value.agent_id }),
          ...(doc.value.run_id && { run_id: doc.value.run_id }),
          ...(doc.value.user_id && { user_id: doc.value.user_id }),
          ...JSON.parse(doc.value.metadata || "{}"),
        };

        return {
          id: doc.value.memory_id,
          payload: toCamelCase(resultPayload),
          score: Number(doc.value.__vector_score) ?? 0,
        };
      });
    } catch (error) {
      console.error("Error during vector search:", error);
      throw error;
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    try {
      // Check if the memory exists first
      const exists = await this.client.exists(
        `${this.indexPrefix}:${vectorId}`,
      );
      if (!exists) {
        console.warn(`Memory with ID ${vectorId} does not exist`);
        return null;
      }

      const result = await this.client.hGetAll(
        `${this.indexPrefix}:${vectorId}`,
      );
      if (!Object.keys(result).length) return null;

      const doc = {
        memory_id: result.memory_id,
        hash: result.hash,
        memory: result.memory,
        created_at: result.created_at,
        updated_at: result.updated_at,
        agent_id: result.agent_id,
        run_id: result.run_id,
        user_id: result.user_id,
        metadata: result.metadata,
      };

      // Validate and convert timestamps
      let created_at: Date;
      try {
        if (!result.created_at) {
          created_at = new Date();
        } else {
          const timestamp = Number(result.created_at);
          // Check if timestamp is in milliseconds (13 digits) or seconds (10 digits)
          if (timestamp.toString().length === 10) {
            created_at = new Date(timestamp * 1000);
          } else {
            created_at = new Date(timestamp);
          }
          // Validate the date is valid
          if (isNaN(created_at.getTime())) {
            console.warn(
              `Invalid created_at timestamp: ${result.created_at}, using current date`,
            );
            created_at = new Date();
          }
        }
      } catch (error) {
        console.warn(
          `Error parsing created_at timestamp: ${result.created_at}, using current date`,
        );
        created_at = new Date();
      }

      let updated_at: Date | undefined;
      try {
        if (result.updated_at) {
          const timestamp = Number(result.updated_at);
          // Check if timestamp is in milliseconds (13 digits) or seconds (10 digits)
          if (timestamp.toString().length === 10) {
            updated_at = new Date(timestamp * 1000);
          } else {
            updated_at = new Date(timestamp);
          }
          // Validate the date is valid
          if (isNaN(updated_at.getTime())) {
            console.warn(
              `Invalid updated_at timestamp: ${result.updated_at}, setting to undefined`,
            );
            updated_at = undefined;
          }
        }
      } catch (error) {
        console.warn(
          `Error parsing updated_at timestamp: ${result.updated_at}, setting to undefined`,
        );
        updated_at = undefined;
      }

      const payload = {
        hash: doc.hash,
        data: doc.memory,
        created_at: created_at.toISOString(),
        ...(updated_at && { updated_at: updated_at.toISOString() }),
        ...(doc.agent_id && { agent_id: doc.agent_id }),
        ...(doc.run_id && { run_id: doc.run_id }),
        ...(doc.user_id && { user_id: doc.user_id }),
        ...JSON.parse(doc.metadata || "{}"),
      };

      return {
        id: vectorId,
        payload,
      };
    } catch (error) {
      console.error("Error getting vector:", error);
      throw error;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const snakePayload = toSnakeCase(payload);
    const entry: Record<string, any> = {
      memory_id: vectorId,
      hash: snakePayload.hash,
      memory: snakePayload.data,
      created_at: new Date(snakePayload.created_at).getTime(),
      updated_at: new Date(snakePayload.updated_at).getTime(),
      embedding: Buffer.from(new Float32Array(vector).buffer),
    };

    // Add optional fields
    ["agent_id", "run_id", "user_id"].forEach((field) => {
      if (field in snakePayload) {
        entry[field] = snakePayload[field];
      }
    });

    // Add metadata excluding specific keys
    entry.metadata = JSON.stringify(
      Object.fromEntries(
        Object.entries(snakePayload).filter(([key]) => !EXCLUDED_KEYS.has(key)),
      ),
    );

    try {
      await this.client.hSet(`${this.indexPrefix}:${vectorId}`, entry);
    } catch (error) {
      console.error("Error during vector update:", error);
      throw error;
    }
  }

  async delete(vectorId: string): Promise<void> {
    try {
      // Check if memory exists first
      const key = `${this.indexPrefix}:${vectorId}`;
      const exists = await this.client.exists(key);

      if (!exists) {
        console.warn(`Memory with ID ${vectorId} does not exist`);
        return;
      }

      // Delete the memory
      const result = await this.client.del(key);

      if (!result) {
        throw new Error(`Failed to delete memory with ID ${vectorId}`);
      }

      console.log(`Successfully deleted memory with ID ${vectorId}`);
    } catch (error) {
      console.error("Error deleting memory:", error);
      throw error;
    }
  }

  async deleteCol(): Promise<void> {
    await this.client.ft.dropIndex(this.indexName);
  }

  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const snakeFilters = filters ? toSnakeCase(filters) : undefined;
    const filterExpr = snakeFilters
      ? Object.entries(snakeFilters)
          .filter(([_, value]) => value !== null)
          .map(([key, value]) => `@${key}:{${value}}`)
          .join(" ")
      : "*";

    const searchOptions = {
      SORTBY: "created_at",
      SORTDIR: "DESC",
      LIMIT: {
        from: 0,
        size: limit,
      },
    };

    const results = (await this.client.ft.search(
      this.indexName,
      filterExpr,
      searchOptions,
    )) as unknown as RedisSearchResult;

    const items = results.documents.map((doc) => ({
      id: doc.value.memory_id,
      payload: toCamelCase({
        hash: doc.value.hash,
        data: doc.value.memory,
        created_at: new Date(parseInt(doc.value.created_at)).toISOString(),
        ...(doc.value.updated_at && {
          updated_at: new Date(parseInt(doc.value.updated_at)).toISOString(),
        }),
        ...(doc.value.agent_id && { agent_id: doc.value.agent_id }),
        ...(doc.value.run_id && { run_id: doc.value.run_id }),
        ...(doc.value.user_id && { user_id: doc.value.user_id }),
        ...JSON.parse(doc.value.metadata || "{}"),
      }),
    }));

    return [items, results.total];
  }

  async close(): Promise<void> {
    await this.client.quit();
  }

  async getUserId(): Promise<string> {
    try {
      // Check if the user ID exists in Redis
      const userId = await this.client.get("memory_migrations:1");
      if (userId) {
        return userId;
      }

      // Generate a random user_id if none exists
      const randomUserId =
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15);

      // Store the user ID
      await this.client.set("memory_migrations:1", randomUserId);
      return randomUserId;
    } catch (error) {
      console.error("Error getting user ID:", error);
      throw error;
    }
  }

  async setUserId(userId: string): Promise<void> {
    try {
      await this.client.set("memory_migrations:1", userId);
    } catch (error) {
      console.error("Error setting user ID:", error);
      throw error;
    }
  }
}
