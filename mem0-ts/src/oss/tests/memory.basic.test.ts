import { Memory } from '../src';
import dotenv from 'dotenv';
import { describe, it, expect, beforeAll, jest } from '@jest/globals';
dotenv.config();

const OPENAI_API_KEY = process.env.OPENAI_API_KEY || '';

jest.setTimeout(30000);

describe('Memory Basic Integration', () => {
  const userId = 'test_user';
  let memory: Memory;
  let memoryId: string;

  beforeAll(() => {
    if (!OPENAI_API_KEY) {
      // Skip tests if no API key
      // @ts-ignore
      return pending('OPENAI_API_KEY not set');
    }
    memory = new Memory({
      embedder: { provider: 'openai', config: { apiKey: OPENAI_API_KEY } },
      llm: { provider: 'openai', config: { apiKey: OPENAI_API_KEY } },
    });
  });

  it('should add a memory', async () => {
    try {
      const result = await memory.add('The sky is blue.', { userId });
      expect(result.results.length).toBeGreaterThan(0);
      memoryId = result.results[0].id;
      expect(result.results[0].memory).toContain('sky');
    } catch (err) {
      console.error('Add memory error:', err);
      throw err;
    }
  });

  it('should get a memory by ID', async () => {
    const mem = await memory.get(memoryId);
    expect(mem).not.toBeNull();
    expect(mem?.memory).toContain('sky');
  });

  it('should update a memory', async () => {
    const res = await memory.update(memoryId, 'The sky is green.');
    expect(res.message).toMatch(/updated/i);
    const mem = await memory.get(memoryId);
    expect(mem?.memory).toContain('green');
  });

  it('should get all memories for the user', async () => {
    const all = await memory.getAll({ userId });
    expect(all.results.length).toBeGreaterThan(0);
  });

  it('should search for a memory', async () => {
    const search = await memory.search('What color is the sky?', { userId });
    expect(search.results.length).toBeGreaterThan(0);
    expect(search.results[0].memory).toBeDefined();
  });

  it('should delete a memory', async () => {
    const res = await memory.delete(memoryId);
    expect(res.message).toMatch(/deleted/i);
    const mem = await memory.get(memoryId);
    expect(mem).toBeNull();
  });

  it('should reset all memories', async () => {
    await memory.add('Another memory.', { userId });
    await memory.reset();
    const all = await memory.getAll({ userId });
    expect(all.results.length).toBe(0);
  });
}); 