import type { SupabaseClient } from "@supabase/supabase-js";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import { loadPeer } from "../utils/load_peer";

interface VectorData {
  id: string;
  embedding: number[];
  metadata: Record<string, any>;
  [key: string]: any;
}

interface VectorQueryParams {
  query_embedding: number[];
  match_count: number;
  filter?: SearchFilters;
}

interface VectorSearchResult {
  id: string;
  similarity: number;
  metadata: Record<string, any>;
  [key: string]: any;
}

interface SupabaseConfig extends VectorStoreConfig {
  supabaseUrl: string;
  supabaseKey: string;
  tableName: string;
  embeddingColumnName?: string;
  metadataColumnName?: string;
}

const POSTGREST_MAX_ROWS = 1000;

/*
SQL Migration to run in Supabase SQL Editor:

-- Enable the vector extension
create extension if not exists vector;

-- Create the memories table
create table if not exists memories (
  id text primary key,
  embedding vector(1536),
  metadata jsonb,
  created_at timestamp with time zone default timezone('utc', now()),
  updated_at timestamp with time zone default timezone('utc', now())
);

-- Create the memory migrations table
create table if not exists memory_migrations (
  user_id text primary key,
  created_at timestamp with time zone default timezone('utc', now())
);

-- Create the vector similarity search function
create or replace function match_vectors(
  query_embedding vector(1536),
  match_count int,
  filter jsonb default '{}'::jsonb
)
returns table (
  id text,
  similarity float,
  metadata jsonb
)
language plpgsql
as $$
begin
  return query
  select
    t.id::text,
    1 - (t.embedding <=> query_embedding) as similarity,
    t.metadata
  from memories t
  where case
    when filter::text = '{}'::text then true
    else t.metadata @> filter
  end
  order by t.embedding <=> query_embedding
  limit match_count;
end;
$$;
*/

export class SupabaseDB implements VectorStore {
  private client!: SupabaseClient;
  private readonly supabaseUrl: string;
  private readonly supabaseKey: string;
  private readonly tableName: string;
  private readonly embeddingColumnName: string;
  private readonly metadataColumnName: string;
  private _initPromise?: Promise<void>;

  constructor(config: SupabaseConfig) {
    this.supabaseUrl = config.supabaseUrl;
    this.supabaseKey = config.supabaseKey;
    this.tableName = config.tableName;
    this.embeddingColumnName = config.embeddingColumnName || "embedding";
    this.metadataColumnName = config.metadataColumnName || "metadata";

    this.initialize().catch((err) => {
      console.error("Failed to initialize Supabase:", err);
    });
  }

  private async ensureClient(): Promise<void> {
    if (this.client) return;
    const sdk = await loadPeer(
      "@supabase/supabase-js",
      "Supabase vector store",
      () => import("@supabase/supabase-js"),
    );
    this.client = sdk.createClient(this.supabaseUrl, this.supabaseKey);
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    await this.ensureClient();
    try {
      const { error: probeError } = await this.client
        .from(this.tableName)
        .select(this.embeddingColumnName)
        .limit(1);

      if (probeError) {
        console.error("Table probe error:", probeError);
        throw new Error(
          `Vector operations failed. Please ensure:
1. The vector extension is enabled
2. The table "${this.tableName}" exists with correct schema
3. The match_vectors function is created
4. Row Level Security policies allow the configured Supabase key to read the table

RUN THE FOLLOWING SQL IN YOUR SUPABASE SQL EDITOR:

-- Enable the vector extension
create extension if not exists vector;

-- Create the memories table
create table if not exists memories (
  id text primary key,
  embedding vector(1536),
  metadata jsonb,
  created_at timestamp with time zone default timezone('utc', now()),
  updated_at timestamp with time zone default timezone('utc', now())
);

-- Create the memory migrations table
create table if not exists memory_migrations (
  user_id text primary key,
  created_at timestamp with time zone default timezone('utc', now())
);

-- Create the vector similarity search function
create or replace function match_vectors(
  query_embedding vector(1536),
  match_count int,
  filter jsonb default '{}'::jsonb
)
returns table (
  id text,
  similarity float,
  metadata jsonb
)
language plpgsql
as $$
begin
  return query
  select
    t.id::text,
    1 - (t.embedding <=> query_embedding) as similarity,
    t.metadata
  from memories t
  where case
    when filter::text = '{}'::text then true
    else t.metadata @> filter
  end
  order by t.embedding <=> query_embedding
  limit match_count;
end;
$$;

See the SQL migration instructions in the code comments.`,
        );
      }

      console.log("Connected to Supabase successfully");
    } catch (error) {
      console.error("Error during Supabase initialization:", error);
      throw error;
    }
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    try {
      const data = vectors.map((vector, idx) => ({
        id: ids[idx],
        [this.embeddingColumnName]: vector,
        [this.metadataColumnName]: {
          ...payloads[idx],
          created_at: new Date().toISOString(),
        },
      }));

      const { error } = await this.client.from(this.tableName).insert(data);

      if (error) throw error;
    } catch (error) {
      console.error("Error during vector insert:", error);
      throw error;
    }
  }

  async keywordSearch(): Promise<null> {
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    try {
      const rpcQuery: VectorQueryParams = {
        query_embedding: query,
        match_count: topK,
      };

      if (filters) {
        rpcQuery.filter = filters;
      }

      const { data, error } = await this.client.rpc("match_vectors", rpcQuery);

      if (error) throw error;
      if (!data) return [];

      const results = data as VectorSearchResult[];

      if (topK > POSTGREST_MAX_ROWS && results.length === POSTGREST_MAX_ROWS) {
        console.warn(
          `Supabase search requested topK=${topK} but match_vectors returned exactly the PostgREST row cap of ${POSTGREST_MAX_ROWS}; results were likely truncated.`,
        );
      }

      return results.map((result) => ({
        id: result.id,
        payload: result.metadata,
        score: result.similarity,
      }));
    } catch (error) {
      console.error("Error during vector search:", error);
      throw error;
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    try {
      const { data, error } = await this.client
        .from(this.tableName)
        .select("*")
        .eq("id", vectorId)
        .maybeSingle();

      if (error) throw error;
      if (!data) return null;

      return {
        id: data.id,
        payload: data[this.metadataColumnName],
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
    await this.initialize();
    try {
      const { error } = await this.client
        .from(this.tableName)
        .update({
          [this.embeddingColumnName]: vector,
          [this.metadataColumnName]: {
            ...payload,
            updated_at: new Date().toISOString(),
          },
        })
        .eq("id", vectorId);

      if (error) throw error;
    } catch (error) {
      console.error("Error during vector update:", error);
      throw error;
    }
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    try {
      const { error } = await this.client
        .from(this.tableName)
        .delete()
        .eq("id", vectorId);

      if (error) throw error;
    } catch (error) {
      console.error("Error deleting vector:", error);
      throw error;
    }
  }

  async deleteCol(): Promise<void> {
    await this.initialize();
    try {
      const { error } = await this.client
        .from(this.tableName)
        .delete()
        .neq("id", ""); // Delete all rows

      if (error) throw error;
    } catch (error) {
      console.error("Error deleting collection:", error);
      throw error;
    }
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();
    try {
      const results: VectorStoreResult[] = [];
      let totalCount = 0;
      let offset = 0;

      while (results.length < topK) {
        const to = Math.min(offset + POSTGREST_MAX_ROWS, topK) - 1;

        let query = this.client
          .from(this.tableName)
          .select("*", { count: "exact" })
          .order("id", { ascending: true });

        if (filters) {
          Object.entries(filters).forEach(([key, value]) => {
            query = query.eq(`${this.metadataColumnName}->>${key}`, value);
          });
        }

        const { data, error, count } = await query.range(offset, to);

        if (error) throw error;

        totalCount = count ?? totalCount;

        const page = (data ?? []).map((item: VectorData) => ({
          id: item.id,
          payload: item[this.metadataColumnName],
        }));
        results.push(...page);

        const requestedPageSize = to - offset + 1;
        if (page.length < requestedPageSize) break;

        offset += page.length;

        if (results.length >= totalCount) break;
      }

      return [results, totalCount];
    } catch (error) {
      console.error("Error listing vectors:", error);
      throw error;
    }
  }

  async getUserId(): Promise<string> {
    await this.initialize();
    try {
      // First check if the table exists
      const { data: tableExists } = await this.client
        .from("memory_migrations")
        .select("user_id")
        .limit(1);

      if (!tableExists || tableExists.length === 0) {
        // Generate a random user_id
        const randomUserId =
          Math.random().toString(36).substring(2, 15) +
          Math.random().toString(36).substring(2, 15);

        // Insert the new user_id
        const { error: insertError } = await this.client
          .from("memory_migrations")
          .insert({ user_id: randomUserId });

        if (insertError) throw insertError;
        return randomUserId;
      }

      // Get the first user_id
      const { data, error } = await this.client
        .from("memory_migrations")
        .select("user_id")
        .limit(1);

      if (error) throw error;
      if (!data || data.length === 0) {
        // Generate a random user_id if no data found
        const randomUserId =
          Math.random().toString(36).substring(2, 15) +
          Math.random().toString(36).substring(2, 15);

        const { error: insertError } = await this.client
          .from("memory_migrations")
          .insert({ user_id: randomUserId });

        if (insertError) throw insertError;
        return randomUserId;
      }

      return data[0].user_id;
    } catch (error) {
      console.error("Error getting user ID:", error);
      return "anonymous-supabase";
    }
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    try {
      const { error: deleteError } = await this.client
        .from("memory_migrations")
        .delete()
        .neq("user_id", "");

      if (deleteError) throw deleteError;

      const { error: insertError } = await this.client
        .from("memory_migrations")
        .insert({ user_id: userId });

      if (insertError) throw insertError;
    } catch (error) {
      console.error("Error setting user ID:", error);
    }
  }
}
