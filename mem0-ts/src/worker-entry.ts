/*
Worker entrypoint for mem0 OSS SDK.
This file re-exports only Worker/browser-safe components.
Consumers can import from 'mem0/worker' (after updating package exports) to load this bundle.
*/

import WasmSQLiteStorage from './storage/wasm-sqlite';
export { WasmSQLiteStorage };

// Minimal factory showing how to wire the storage into a memory manager.
// Keep this intentionally small so it is safe to ship in a worker bundle.

export type SimpleMemory = {
  id: string;
  content: string;
  metadata?: Record<string, unknown>;
};

export class SimpleMemoryManager {
  private storage: any;

  constructor(storage: any) {
    this.storage = storage;
  }

  async init() {
    if (typeof this.storage.initialize === 'function') await this.storage.initialize();
  }

  async add(mem: SimpleMemory) {
    return this.storage.addMemory(mem.id, mem.content, mem.metadata);
  }

  async get(id: string) {
    return this.storage.getMemory(id);
  }

  async list(limit?: number, offset?: number) {
    return this.storage.listMemories(limit, offset);
  }
}

export default { WasmSQLiteStorage: WasmSQLiteStorage, SimpleMemoryManager };
