import { WasmSQLiteStorage } from '../src/worker-entry';

describe('worker build smoke test', () => {
  jest.setTimeout(20000);

  it('initializes WASM sqlite and performs CRUD', async () => {
    const s = new WasmSQLiteStorage();
    await s.initialize();
    await s.addMemory('test-1', 'hello world', { a: 1 });
    const row = await s.getMemory('test-1');
    expect(row).not.toBeNull();
    expect(row?.content).toBe('hello world');
    await s.close();
  });
});
