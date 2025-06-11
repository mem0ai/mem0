export interface HistoryManager {
  addHistory(
    memoryId: string,
    previousValue: string | null,
    newValue: string | null,
    action: string,
    createdAt?: string,
    updatedAt?: string,
    isDeleted?: number,
  ): Promise<void>;
  getHistory(memoryId: string): Promise<any[]>;
  reset(): Promise<void>;
  close(): void;
}
