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

  // V3 optional methods — implementations that don't need them can omit these.
  saveMessages?(
    messages: Array<{ role: string; content: string; name?: string }>,
    sessionScope: string,
  ): Promise<void>;
  getLastMessages?(
    sessionScope: string,
    limit?: number,
  ): Promise<
    Array<{ role: string; content: string; name?: string; createdAt: string }>
  >;
  batchAddHistory?(
    records: Array<{
      memoryId: string;
      previousValue: string | null;
      newValue: string | null;
      action: string;
      createdAt?: string;
      updatedAt?: string;
      isDeleted?: number;
    }>,
  ): Promise<void>;
}
