import * as zapier from 'zapier-platform-core';
import App from '../src';

const appTester = zapier.createAppTester(App as any);

const authData = {
	apiKey: process.env.MEM0_API_KEY,
	baseUrl: process.env.MEM0_BASE_URL || 'https://api.mem0.ai',
};

const userId = `zapier-e2e-${Date.now()}`;

// Retry an async op until `done` is satisfied or attempts run out. Extraction is
// async, so the default Add returns before the memory is searchable.
const until = async <T>(
	fn: () => Promise<T>,
	done: (r: T) => boolean,
	{ attempts = 30, delayMs = 2000 } = {},
): Promise<T> => {
	let last: T = undefined as unknown as T;
	for (let i = 0; i < attempts; i++) {
		last = await fn();
		if (done(last)) return last;
		await new Promise((resolve) => setTimeout(resolve, delayMs));
	}
	return last;
};

// The E2E suite hits the live Mem0 API, so it only runs when MEM0_API_KEY is
// set (locally / with a secret). In CI without a key it is skipped, not failed.
const describeE2E = authData.apiKey ? describe : describe.skip;

describeE2E('Mem0 Zapier integration (E2E)', () => {
	it('authentication.test succeeds', async () => {
		const res: any = await appTester((App as any).authentication.test, { authData });
		expect(res.status).toBe(200);
	});

	it('adds, searches, lists, and deletes a memory', async () => {
		// Add via the default path: returns immediately with an event id.
		const added: any = await appTester((App as any).creates.add_memory.operation.perform, {
			authData,
			inputData: {
				content: 'I love hiking in the Alps and my favorite food is sushi',
				user_id: userId,
			},
		});
		expect(added.event_id).toBeDefined();

		// Extraction is async; retry search until the memory is indexed.
		// Budget generously — live extraction can occasionally exceed a minute.
		const found: any[] = await until(
			() =>
				appTester((App as any).searches.search_memories.operation.perform, {
					authData,
					inputData: { query: 'outdoor activities', user_id: userId, limit: 5 },
				}),
			(r: any[]) => Array.isArray(r) && r.length > 0,
			{ attempts: 60, delayMs: 2000 },
		);
		expect(Array.isArray(found)).toBe(true);
		expect(found.length).toBeGreaterThan(0);

		// Get all
		const all: any[] = await appTester((App as any).searches.get_memories.operation.perform, {
			authData,
			inputData: { user_id: userId },
		});
		expect(Array.isArray(all)).toBe(true);
		expect(all.length).toBeGreaterThan(0);

		// Cleanup: delete every memory we created
		for (const mem of all) {
			await appTester((App as any).creates.delete_memory.operation.perform, {
				authData,
				inputData: { memory_id: mem.id },
			});
		}

		const afterDelete: any[] = await appTester(
			(App as any).searches.get_memories.operation.perform,
			{ authData, inputData: { user_id: userId } },
		);
		expect(afterDelete.length).toBe(0);
	});

	it('surfaces API errors instead of returning an empty array (search needs a filter)', async () => {
		// filters is required by the API; omitting it must throw, not return [].
		await expect(
			appTester((App as any).searches.search_memories.operation.perform, {
				authData,
				inputData: { query: 'anything' },
			}),
		).rejects.toThrow();
	});
});
