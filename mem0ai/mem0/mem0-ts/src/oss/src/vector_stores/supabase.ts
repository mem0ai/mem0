import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

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
  private client: SupabaseClient;
  private readonly tableName: string;
  private readonly embeddingColumnName: string;
  private readonly metadataColumnName: string;

  constructor(config: SupabaseConfig) {
    this.client = createClient(config.supabaseUrl, config.supabaseKey);
    this.tableName = config.tableName;
    this.embeddingColumnName = config.embeddingColumnName || "embedding";
    this.metadataColumnName = config.metadataColumnName || "metadata";

    this.initialize().catch((err) => {
      console.error("Failed to initialize Supabase:", err);
      throw err;
    });
  }

  async initialize(): Promise<void> {
    try {
      // Verify table exists and vector operations work by attempting a test insert
      const testVector = Array(1536).fill(0);

      // First try to delete any existing test vector
      try {
        await this.client.from(this.tableName).delete().eq("id", "test_vector");
      } catch {
        // Ignore delete errors - table might not exist yet
      }

      // Try to insert the test vector
      const { error: insertError } = await this.client
        .from(this.tableName)
        .insert({
          id: "test_vector",
          [this.embeddingColumnName]: testVector,
          [this.metadataColumnName]: {},
        })
        .select();

      // If we get a duplicate key error, that's actually fine - it means the table exists
      if (insertError && insertError.code !== "23505") {
        console.error("Test insert error:", insertError);
        throw new Error(
          `Vector operations failed. Please ensure:
1. The vector extension is enabled
2. The table "${this.tableName}" exists with correct schema
3. The match_vectors function is created

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

      // Clean up test vector - ignore errors here too
      try {
        await this.client.from(this.tableName).delete().eq("id", "test_vector");
      } catch {
        // Ignore delete errors
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

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    try {
      const rpcQuery: VectorQueryParams = {
        query_embedding: query,
        match_count: limit,
      };

      if (filters) {
        rpcQuery.filter = filters;
      }

      const { data, error } = await this.client.rpc("match_vectors", rpcQuery);

      if (error) throw error;
      if (!data) return [];

      const results = data as VectorSearchResult[];
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
    try {
      const { data, error } = await this.client
        .from(this.tableName)
        .select("*")
        .eq("id", vectorId)
        .single();

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
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    try {
      let query = this.client
        .from(this.tableName)
        .select("*", { count: "exact" })
        .limit(limit);

      if (filters) {
        Object.entries(filters).forEach(([key, value]) => {
          query = query.eq(`${this.metadataColumnName}->>${key}`, value);
        });
      }

      const { data, error, count } = await query;

      if (error) throw error;

      const results = data.map((item: VectorData) => ({
        id: item.id,
        payload: item[this.metadataColumnName],
      }));

      return [results, count || 0];
    } catch (error) {
      console.error("Error listing vectors:", error);
      throw error;
    }
  }

  async getUserId(): Promise<string> {
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
