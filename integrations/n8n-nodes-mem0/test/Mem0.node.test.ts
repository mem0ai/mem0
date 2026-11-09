// Offline unit tests: they stub IExecuteFunctions and mock the HTTP layer, so
// they run with no network. They cover the review-flagged paths: the entity-id
// guard, JSON-parse errors, the poll-timeout loop, plus source attribution and
// the Return All pagination.

// Make the poll loop instant (pollEvent sleeps between attempts).
jest.mock('n8n-workflow', () => {
	const actual = jest.requireActual('n8n-workflow');
	return { ...actual, sleep: jest.fn().mockResolvedValue(undefined) };
});

import { Mem0 } from '../nodes/Mem0/Mem0.node';

type HttpImpl = (options: any) => Promise<any>;

function makeCtx(
	operation: string,
	params: Record<string, any>,
	http: HttpImpl,
	opts: { continueOnFail?: boolean } = {},
): any {
	const requests: any[] = [];
	const node = { name: 'Mem0', type: '@mem0/n8n-nodes-mem0.mem0', typeVersion: 1 };
	const ctx: any = {
		getInputData: () => [{ json: {} }],
		getCredentials: async () => ({ apiKey: 'm0-test', baseUrl: 'https://api.mem0.ai' }),
		getNodeParameter: (name: string, _i: number, dflt?: any) =>
			name === 'operation' ? operation : name in params ? params[name] : dflt,
		getNode: () => node,
		continueOnFail: () => opts.continueOnFail ?? false,
		helpers: {
			httpRequestWithAuthentication: jest.fn(async function (_cred: string, options: any) {
				requests.push(options);
				return http(options);
			}),
		},
	};
	ctx.requests = requests;
	return ctx;
}

const run = (ctx: any) => Mem0.prototype.execute.call(ctx);

describe('Mem0 node (offline)', () => {
	it('reports a clear error when Add has no entity id', async () => {
		const ctx = makeCtx(
			'add',
			{ 'messages.message': [{ role: 'user', content: 'hi' }], addFields: {}, userId: '' },
			async () => ({}),
			{ continueOnFail: true },
		);
		const out: any = await run(ctx);
		expect(out[0][0].json.error).toMatch(/at least one of User ID/i);
	});

	it('forwards app id, includes and excludes on Add', async () => {
		const ctx = makeCtx(
			'add',
			{
				'messages.message': [{ role: 'user', content: 'hi' }],
				addFields: {
					app_id: 'p1',
					includes: 'only food preferences',
					excludes: 'nothing about vehicles',
				},
				userId: 'u1',
			},
			async () => ({}),
		);
		await run(ctx);
		expect(ctx.requests[0].body).toMatchObject({
			app_id: 'p1',
			includes: 'only food preferences',
			excludes: 'nothing about vehicles',
		});
	});

	it('accepts an app id alone as the entity scope on Add', async () => {
		const ctx = makeCtx(
			'add',
			{
				'messages.message': [{ role: 'user', content: 'hi' }],
				addFields: { app_id: 'p1' },
				userId: '',
			},
			async () => ({}),
			{ continueOnFail: true },
		);
		const out: any = await run(ctx);
		expect(out[0][0].json.error).toBeUndefined();
		expect(ctx.requests[0].body.app_id).toBe('p1');
	});

	it('reports a clear error on invalid JSON in Custom Categories', async () => {
		const ctx = makeCtx(
			'add',
			{
				'messages.message': [{ role: 'user', content: 'hi' }],
				addFields: { custom_categories: '{bad' },
				userId: 'u1',
			},
			async () => ({}),
			{ continueOnFail: true },
		);
		const out: any = await run(ctx);
		expect(out[0][0].json.error).toMatch(/Invalid JSON/i);
	});

	it('times out when the add event never resolves', async () => {
		const ctx = makeCtx(
			'add',
			{
				'messages.message': [{ role: 'user', content: 'hi' }],
				addFields: {},
				userId: 'u1',
				waitForCompletion: true,
			},
			async (options) => {
				if (options.url.includes('/v3/memories/add/')) return { event_id: 'e1', status: 'PENDING' };
				if (options.url.includes('/v1/event/')) return { status: 'PENDING' }; // never terminal
				return {};
			},
			{ continueOnFail: true },
		);
		const out: any = await run(ctx);
		expect(out[0][0].json.error).toMatch(/Timed out waiting for memory event/i);
	});

	it('tags every request with source=N8N for first-party attribution', async () => {
		const ctx = makeCtx('search', { query: 'x', userId: 'u1', limit: 5 }, async () => ({ results: [] }));
		await run(ctx);
		expect(ctx.requests[0].qs.source).toBe('N8N');
	});

	it('sends a single entity id as a flat filter', async () => {
		const ctx = makeCtx('search', { query: 'x', userId: 'u1' }, async () => ({ results: [] }));
		await run(ctx);
		expect(ctx.requests[0].body.filters).toEqual({ user_id: 'u1' });
	});

	it('combines entity ids with OR, never AND (entities are stored separately, so AND matches nothing)', async () => {
		const ctx = makeCtx(
			'search',
			{ query: 'x', userId: 'u1', agentId: 'a1', appId: 'p1', runId: 'r1' },
			async () => ({ results: [] }),
		);
		await run(ctx);
		expect(ctx.requests[0].body.filters).toEqual({
			OR: [{ user_id: 'u1' }, { agent_id: 'a1' }, { app_id: 'p1' }, { run_id: 'r1' }],
		});
	});

	it.each(['search', 'getAll'])('filters %s by app id alone', async (op) => {
		const ctx = makeCtx(op, { query: 'x', appId: 'p1' }, async () => ({ results: [] }));
		await run(ctx);
		expect(ctx.requests[0].body.filters).toEqual({ app_id: 'p1' });
	});

	it('filters Get Many by agent id alone', async () => {
		const ctx = makeCtx('getAll', { agentId: 'a1' }, async () => ({ results: [] }));
		await run(ctx);
		expect(ctx.requests[0].body.filters).toEqual({ agent_id: 'a1' });
	});

	it.each(['search', 'getAll'])('reports a clear error when %s has no entity id', async (op) => {
		const ctx = makeCtx(op, { query: 'x' }, async () => ({ results: [] }), {
			continueOnFail: true,
		});
		const out: any = await run(ctx);
		expect(out[0][0].json.error).toMatch(/at least one of User ID/i);
	});

	it.each([
		['get', 'GET'],
		['delete', 'DELETE'],
	])('escapes the memory id in the %s url', async (op, method) => {
		const ctx = makeCtx(op, { memoryId: '../v1/entities' }, async () => ({}));
		await run(ctx);
		expect(ctx.requests[0].method).toBe(method);
		expect(ctx.requests[0].url).toBe('https://api.mem0.ai/v1/memories/..%2Fv1%2Fentities/');
	});

	it('escapes the event id when polling', async () => {
		const ctx = makeCtx(
			'add',
			{
				'messages.message': [{ role: 'user', content: 'hi' }],
				addFields: {},
				userId: 'u1',
				waitForCompletion: true,
			},
			async (options) => {
				if (options.url.includes('/v3/memories/add/')) return { event_id: 'a b/c' };
				return { status: 'SUCCEEDED', results: [] };
			},
		);
		await run(ctx);
		expect(ctx.requests[1].url).toBe('https://api.mem0.ai/v1/event/a%20b%2Fc/');
	});

	it('Return All pages through until a short page', async () => {
		let call = 0;
		const ctx = makeCtx('getAll', { userId: 'u1', returnAll: true, pageSize: 2 }, async () => {
			call++;
			if (call === 1) return { results: [{ id: 'a' }, { id: 'b' }], next: 'page2' };
			return { results: [{ id: 'c' }], next: null }; // short page -> stop
		});
		const out: any = await run(ctx);
		expect(out[0].map((d: any) => d.json.id)).toEqual(['a', 'b', 'c']);
	});
});
