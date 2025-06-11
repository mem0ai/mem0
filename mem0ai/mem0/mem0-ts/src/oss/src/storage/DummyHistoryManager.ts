export class DummyHistoryManager {
  constructor() {}

  async addHistory(
    memoryId: string,
    previousValue: string | null,
    newValue: string | null,
    action: string,
    createdAt?: string,
    updatedAt?: string,
    isDeleted: number = 0,
  ): Promise<void> {
    return;
  }

  async getHistory(memoryId: string): Promise<any[]> {
    return [];
  }

  async reset(): Promise<void> {
    return;
  }

  close(): void {
    return;
  }
}
