// Offline unit tests: they mock `z.request`, so they run unconditionally in CI
// (unlike the live E2E suite in mem0.test.ts, gated on MEM0_API_KEY). They cover
// what `zapier validate` can't: boolean coercion, URL join, metadata, array shapes.

import addMemory from '../src/creates/add_memory';
import deleteMemory from '../src/creates/delete_memory';
import searchMemories from '../src/searches/search_memories';
import getMemories from '../src/searches/get_memories';
import { includeApiKey } from '../src/middleware';

// Minimal `z` stub: hands back queued responses and records every request.
const makeZ = (responses: any[] = []): any => {
	const queue = [...responses];
	const requests: any[] = [];
	return {
		requests,
		request: async (opts: any) => {
			requests.push(opts);
			const next = queue.shift();
			return next !== undefined ? next : { data: {} };
		},
		errors: {
			Error: class Mem0Error extends Error {
				name: string;
				status?: number;
				constructor(message: string, name?: string, status?: number) {
					super(message);
					this.name = name || 'Error';
					this.status = status;
				}
			},
		},
	};
};

describe('add_memory (offline)', () => {
	it('coerces infer="false" to a boolean and does not poll by default', async () => {
		const z = makeZ([{ data: { event_id: 'e1', status: 'PENDING' } }]);
		const res = await addMemory.operation.perform(z, {
			inputData: { content: 'hi', user_id: 'u1', infer: 'false' },
		} as any);
		// waitForCompletion defaults off -> a single request (the add), no poll.
		expect(z.requests).toHaveLength(1);
		expect(z.requests[0].body.infer).toBe(false);
		expect((res as any).status).toBe('PENDING');
	});

	it('polls the event only when waitForCompletion="true"', async () => {
		const z = makeZ([
			{ data: { event_id: 'e1', status: 'PENDING' } },
			{ data: { status: 'SUCCEEDED', results: [{ id: 'm1' }] } },
		]);
		const res = await addMemory.operation.perform(z, {
			inputData: { content: 'hi', user_id: 'u1', waitForCompletion: 'true' },
		} as any);
		expect(z.requests).toHaveLength(2);
		expect(z.requests[1].url).toBe('/v1/event/e1/');
		expect((res as any).status).toBe('SUCCEEDED');
	});

	it('keeps polling past the old 12-attempt budget when the API is slow', async () => {
		jest.useFakeTimers();
		const pendingPolls = Array.from({ length: 20 }, () => ({ data: { status: 'PENDING' } }));
		const z = makeZ([
			{ data: { event_id: 'e1', status: 'PENDING' } },
			...pendingPolls,
			{ data: { status: 'SUCCEEDED', results: [{ id: 'm1' }] } },
		]);
		const resultPromise = addMemory.operation.perform(z, {
			inputData: { content: 'hi', user_id: 'u1', waitForCompletion: 'true' },
		} as any);
		for (let i = 0; i < pendingPolls.length; i++) {
			await jest.advanceTimersByTimeAsync(1500);
		}
		const res = await resultPromise;
		expect((res as any).status).toBe('SUCCEEDED');
		jest.useRealTimers();
	});

	it('throws a clear error on invalid JSON metadata', async () => {
		const z = makeZ();
		await expect(
			addMemory.operation.perform(z, {
				inputData: { content: 'hi', user_id: 'u1', metadata: '{not json' },
			} as any),
		).rejects.toThrow('Metadata must be valid JSON.');
	});

	it('forwards custom_instructions and parses custom_categories JSON', async () => {
		const z = makeZ([{ data: { event_id: 'e1', status: 'PENDING' } }]);
		await addMemory.operation.perform(z, {
			inputData: {
				content: 'hi',
				user_id: 'u1',
				custom_instructions: 'keep durable facts',
				custom_categories: '[{"work":"job related"}]',
			},
		} as any);
		expect(z.requests[0].body.custom_instructions).toBe('keep durable facts');
		expect(z.requests[0].body.custom_categories).toEqual([{ work: 'job related' }]);
	});

	it('throws a clear error on invalid Custom Categories JSON', async () => {
		const z = makeZ();
		await expect(
			addMemory.operation.perform(z, {
				inputData: { content: 'hi', user_id: 'u1', custom_categories: '{bad' },
			} as any),
		).rejects.toThrow('Custom Categories must be valid JSON.');
	});

	it('forwards includes and excludes when provided', async () => {
		const z = makeZ([{ data: { event_id: 'e1', status: 'PENDING' } }]);
		await addMemory.operation.perform(z, {
			inputData: { content: 'hi', user_id: 'u1', includes: 'work facts', excludes: 'small talk' },
		} as any);
		expect(z.requests[0].body.includes).toBe('work facts');
		expect(z.requests[0].body.excludes).toBe('small talk');
	});
});

describe('search / get array-shape enforcement (offline)', () => {
	it('search unwraps an object {results:[...]} into an array', async () => {
		const z = makeZ([{ data: { results: [{ id: 'm1' }] } }]);
		const res = await searchMemories.operation.perform(z, {
			inputData: { query: 'x', user_id: 'u1' },
		} as any);
		expect(Array.isArray(res)).toBe(true);
		expect(res).toHaveLength(1);
	});

	it('get_memories returns [] when the API returns neither array nor results', async () => {
		const z = makeZ([{ data: {} }]);
		const res = await getMemories.operation.perform(z, { inputData: { user_id: 'u1' } } as any);
		expect(Array.isArray(res)).toBe(true);
		expect(res).toHaveLength(0);
	});

	it('get_memories forwards page and page_size as numbers', async () => {
		const z = makeZ([{ data: { results: [] } }]);
		await getMemories.operation.perform(z, {
			inputData: { user_id: 'u1', page: '2', limit: '10' },
		} as any);
		expect(z.requests[0].params).toEqual({ page: 2, page_size: 10 });
	});

	it('search and get_memories return [] on a null/empty body (no crash)', async () => {
		const zSearch = makeZ([{ data: null }]);
		const found = await searchMemories.operation.perform(zSearch, {
			inputData: { query: 'x', user_id: 'u1' },
		} as any);
		expect(found).toEqual([]);

		const zGet = makeZ([{ data: null }]);
		const all = await getMemories.operation.perform(zGet, { inputData: { user_id: 'u1' } } as any);
		expect(all).toEqual([]);
	});
});

describe('delete_memory (offline)', () => {
	it('encodes the memory id in the URL path', async () => {
		const z = makeZ([{ data: {} }]);
		await deleteMemory.operation.perform(z, { inputData: { memory_id: 'a/b c' } } as any);
		expect(z.requests[0].url).toBe('/v1/memories/a%2Fb%20c/');
	});
});

describe('includeApiKey middleware (offline)', () => {
	it('prepends the base URL and injects the auth header', () => {
		const req = includeApiKey({ url: '/v3/memories/' }, null as any, {
			authData: { apiKey: 'k', baseUrl: 'https://api.mem0.ai/' },
		} as any);
		expect(req.url).toBe('https://api.mem0.ai/v3/memories/');
		expect(req.headers!.Authorization).toBe('Token k');
	});

	it('leaves absolute URLs untouched', () => {
		const req = includeApiKey({ url: 'https://other.example/x' }, null as any, {
			authData: { apiKey: 'k' },
		} as any);
		expect(req.url).toBe('https://other.example/x');
	});
});
