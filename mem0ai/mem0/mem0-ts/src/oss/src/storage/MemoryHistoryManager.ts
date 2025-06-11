import { v4 as uuidv4 } from "uuid";
import { HistoryManager } from "./base";
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

export class MemoryHistoryManager implements HistoryManager {
  private memoryStore: Map<string, HistoryEntry> = new Map();

  async addHistory(
    memoryId: string,
    previousValue: string | null,
    newValue: string | null,
    action: string,
    createdAt?: string,
    updatedAt?: string,
    isDeleted: number = 0,
  ): Promise<void> {
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

    this.memoryStore.set(historyEntry.id, historyEntry);
  }

  async getHistory(memoryId: string): Promise<any[]> {
    return Array.from(this.memoryStore.values())
      .filter((entry) => entry.memory_id === memoryId)
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      )
      .slice(0, 100);
  }

  async reset(): Promise<void> {
    this.memoryStore.clear();
  }

  close(): void {
    // No need to close anything for in-memory storage
    return;
  }
}
