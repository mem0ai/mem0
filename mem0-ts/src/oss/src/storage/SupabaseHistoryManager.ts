import type { SupabaseClient } from "@supabase/supabase-js";
import { v4 as uuidv4 } from "uuid";
import { HistoryManager } from "./base";
import { loadPeer } from "../utils/load_peer";

interface HistoryEntry {
  id: string;
  memory_id: string;
  previous_value: string | null;
  new_value: string | null;
  action: string;
  created_at: string;
  updated_at: string | null;
  is_deleted: number;
}

interface SupabaseHistoryConfig {
  supabaseUrl: string;
  supabaseKey: string;
  tableName?: string;
}

export class SupabaseHistoryManager implements HistoryManager {
  // ponytail: benign double-construct race — two concurrent first-calls may each
  // build a client; createClient opens no connection, so last-write-wins is fine.
  private supabase!: SupabaseClient;
  private readonly supabaseUrl: string;
  private readonly supabaseKey: string;
  private readonly tableName: string;

  constructor(config: SupabaseHistoryConfig) {
    this.tableName = config.tableName || "memory_history";
    this.supabaseUrl = config.supabaseUrl;
    this.supabaseKey = config.supabaseKey;
    this.initializeSupabase().catch(console.error);
  }

  private async ensureClient(): Promise<void> {
    if (this.supabase) return;
    const sdk = await loadPeer(
      "@supabase/supabase-js",
      "Supabase history manager",
      () => import("@supabase/supabase-js"),
    );
    this.supabase = sdk.createClient(this.supabaseUrl, this.supabaseKey);
  }

  private async initializeSupabase(): Promise<void> {
    await this.ensureClient();
    // Check if table exists
    const { error } = await this.supabase
      .from(this.tableName)
      .select("id")
      .limit(1);

    if (error) {
      console.error(
        "Error: Table does not exist. Please run this SQL in your Supabase SQL Editor:",
      );
      console.error(`
create table ${this.tableName} (
  id text primary key,
  memory_id text not null,
  previous_value text,
  new_value text,
  action text not null,
  created_at timestamp with time zone default timezone('utc', now()),
  updated_at timestamp with time zone,
  is_deleted integer default 0
);
      `);
      throw error;
    }
  }

  async addHistory(
    memoryId: string,
    previousValue: string | null,
    newValue: string | null,
    action: string,
    createdAt?: string,
    updatedAt?: string,
    isDeleted: number = 0,
  ): Promise<void> {
    await this.ensureClient();
    const historyEntry: HistoryEntry = {
      id: uuidv4(),
      memory_id: memoryId,
      previous_value: previousValue,
      new_value: newValue,
      action: action,
      created_at: createdAt || new Date().toISOString(),
      updated_at: updatedAt || null,
      is_deleted: isDeleted,
    };

    const { error } = await this.supabase
      .from(this.tableName)
      .insert(historyEntry);

    if (error) {
      console.error("Error adding history to Supabase:", error);
      throw error;
    }
  }

  async getHistory(memoryId: string): Promise<any[]> {
    await this.ensureClient();
    const { data, error } = await this.supabase
      .from(this.tableName)
      .select("*")
      .eq("memory_id", memoryId)
      .order("created_at", { ascending: false })
      .limit(100);

    if (error) {
      console.error("Error getting history from Supabase:", error);
      throw error;
    }

    return data || [];
  }

  async reset(): Promise<void> {
    await this.ensureClient();
    const { error } = await this.supabase
      .from(this.tableName)
      .delete()
      .neq("id", "");

    if (error) {
      console.error("Error resetting Supabase history:", error);
      throw error;
    }
  }

  close(): void {
    // No need to close anything as connections are handled by the client
    return;
  }
}
