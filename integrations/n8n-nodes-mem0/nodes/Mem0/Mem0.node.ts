import {
	IExecuteFunctions,
	IDataObject,
	IHttpRequestMethods,
	IHttpRequestOptions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	JsonObject,
	NodeApiError,
	NodeConnectionTypes,
	NodeOperationError,
	sleep,
} from 'n8n-workflow';

// Poll settings for asynchronous (infer=true) memory addition.
const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 40; // ~60s ceiling

export class Mem0 implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'Mem0',
		name: 'mem0',
		icon: { light: 'file:mem0.svg', dark: 'file:mem0.svg' },
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
		description: 'Add, search, and manage long-term memories with Mem0',
		defaults: {
			name: 'Mem0',
		},
		// Makes the node available to the AI Agent (Tools Agent) node.
		usableAsTool: true,
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [
			{
				name: 'mem0Api',
				required: true,
			},
		],
		properties: [
			{
				displayName: 'Resource',
				name: 'resource',
				type: 'options',
				noDataExpression: true,
				options: [{ name: 'Memory', value: 'memory' }],
				default: 'memory',
			},
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				displayOptions: { show: { resource: ['memory'] } },
				options: [
					{
						name: 'Add',
						value: 'add',
						action: 'Add a memory',
						description: 'Extract and store memories from messages',
					},
					{
						name: 'Delete',
						value: 'delete',
						action: 'Delete a memory',
						description: 'Delete a single memory by ID',
					},
					{
						name: 'Get',
						value: 'get',
						action: 'Get a memory',
						description: 'Retrieve a single memory by ID',
					},
					{
						name: 'Get Many',
						value: 'getAll',
						action: 'Get many memories',
						description: 'List stored memories for an entity',
					},
					{
						name: 'Search',
						value: 'search',
						action: 'Search memories',
						description: 'Semantic search over stored memories',
					},
					{
						name: 'Update',
						value: 'update',
						action: 'Update a memory',
						description: 'Update the text or metadata of a memory',
					},
				],
				default: 'add',
			},

			// ---- Add ---------------------------------------------------------
			{
				displayName: 'Messages',
				name: 'messages',
				placeholder: 'Add Message',
				type: 'fixedCollection',
				typeOptions: { multipleValues: true },
				displayOptions: { show: { resource: ['memory'], operation: ['add'] } },
				default: {},
				description: 'The conversation messages to extract memories from',
				options: [
					{
						name: 'message',
						displayName: 'Message',
						values: [
							{
								displayName: 'Role',
								name: 'role',
								type: 'options',
								options: [
									{ name: 'User', value: 'user' },
									{ name: 'Assistant', value: 'assistant' },
									{ name: 'System', value: 'system' },
								],
								default: 'user',
							},
							{
								displayName: 'Content',
								name: 'content',
								type: 'string',
								typeOptions: { rows: 2 },
								default: '',
							},
						],
					},
				],
			},
			{
				displayName: 'User ID',
				name: 'userId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['add'] } },
				description: 'Associate the memories with this user',
			},
			{
				displayName: 'Wait for Completion',
				name: 'waitForCompletion',
				type: 'boolean',
				default: true,
				displayOptions: { show: { resource: ['memory'], operation: ['add'] } },
				description:
					'Whether to poll until memory extraction finishes and return the resulting memories. Turn off to return immediately with the event ID.',
			},
			{
				displayName: 'Additional Fields',
				name: 'addFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				displayOptions: { show: { resource: ['memory'], operation: ['add'] } },
				options: [
					{
						displayName: 'Agent ID',
						name: 'agent_id',
						type: 'string',
						default: '',
					},
					{
						displayName: 'App ID',
						name: 'app_id',
						type: 'string',
						default: '',
					},
					{
						displayName: 'Custom Categories',
						name: 'custom_categories',
						type: 'json',
						default: '',
						description:
							'Optional taxonomy for categorising extracted memories, as a JSON array of {category: description} objects',
					},
					{
						displayName: 'Custom Instructions',
						name: 'custom_instructions',
						type: 'string',
						typeOptions: { rows: 3 },
						default: '',
						description:
							'Optional instructions that steer what the extractor keeps or ignores',
					},
					{
						displayName: 'Excludes',
						name: 'excludes',
						type: 'string',
						default: '',
						description: 'Optional: skip memories matching this description',
					},
					{
						displayName: 'Includes',
						name: 'includes',
						type: 'string',
						default: '',
						description: 'Optional: only extract memories matching this description',
					},
					{
						displayName: 'Infer',
						name: 'infer',
						type: 'boolean',
						default: true,
						description:
							'Whether to run LLM extraction over the messages. Turn off to store them verbatim. ' +
							'This controls extraction only — use "Wait for Completion" to control whether the node waits.',
					},
					{
						displayName: 'Metadata (JSON)',
						name: 'metadata',
						type: 'json',
						default: '',
					},
					{
						displayName: 'Run ID',
						name: 'run_id',
						type: 'string',
						default: '',
					},
				],
			},

			// ---- Search ------------------------------------------------------
			{
				displayName: 'Query',
				name: 'query',
				type: 'string',
				default: '',
				required: true,
				displayOptions: { show: { resource: ['memory'], operation: ['search'] } },
				description: 'What to recall from memory',
			},
			{
				displayName: 'User ID',
				name: 'userId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['search'] } },
				description:
					'Restrict the search to this user. Supply at least one of User ID, Agent ID, App ID, or Run ID.',
			},
			{
				displayName: 'Agent ID',
				name: 'agentId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['search'] } },
				description: 'Restrict the search to memories scoped to this agent',
			},
			{
				displayName: 'App ID',
				name: 'appId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['search'] } },
				description: 'Restrict the search to memories scoped to this app or project',
			},
			{
				displayName: 'Run ID',
				name: 'runId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['search'] } },
				description: 'Restrict the search to memories scoped to this session or run',
			},
			{
				displayName: 'Limit',
				name: 'limit',
				type: 'number',
				typeOptions: { minValue: 1 },
				default: 50,
				displayOptions: { show: { resource: ['memory'], operation: ['search'] } },
				description: 'Max number of results to return',
			},

			// ---- Get Many ----------------------------------------------------
			{
				displayName: 'User ID',
				name: 'userId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['getAll'] } },
				description:
					'Restrict the listing to this user. Supply at least one of User ID, Agent ID, App ID, or Run ID.',
			},
			{
				displayName: 'Agent ID',
				name: 'agentId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['getAll'] } },
				description: 'Restrict the listing to memories scoped to this agent',
			},
			{
				displayName: 'App ID',
				name: 'appId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['getAll'] } },
				description: 'Restrict the listing to memories scoped to this app or project',
			},
			{
				displayName: 'Run ID',
				name: 'runId',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['getAll'] } },
				description: 'Restrict the listing to memories scoped to this session or run',
			},
			{
				displayName: 'Return All',
				name: 'returnAll',
				type: 'boolean',
				default: false,
				displayOptions: { show: { resource: ['memory'], operation: ['getAll'] } },
				description: 'Whether to return all results or only up to a given limit',
			},
			{
				displayName: 'Page',
				name: 'page',
				type: 'number',
				typeOptions: { minValue: 1 },
				default: 1,
				displayOptions: {
					show: { resource: ['memory'], operation: ['getAll'], returnAll: [false] },
				},
			},
			{
				displayName: 'Page Size',
				name: 'pageSize',
				type: 'number',
				typeOptions: { minValue: 1 },
				default: 50,
				displayOptions: { show: { resource: ['memory'], operation: ['getAll'] } },
			},

			// ---- Get / Update / Delete (by ID) -------------------------------
			{
				displayName: 'Memory ID',
				name: 'memoryId',
				type: 'string',
				default: '',
				required: true,
				displayOptions: {
					show: { resource: ['memory'], operation: ['get', 'update', 'delete'] },
				},
			},
			{
				displayName: 'Text',
				name: 'text',
				type: 'string',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['update'] } },
				description: 'The new memory text',
			},
			{
				displayName: 'Metadata (JSON)',
				name: 'metadata',
				type: 'json',
				default: '',
				displayOptions: { show: { resource: ['memory'], operation: ['update'] } },
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];
		const credentials = await this.getCredentials('mem0Api');
		const baseUrl = (credentials.baseUrl as string) || 'https://api.mem0.ai';

		const request = async (
			method: IHttpRequestMethods,
			url: string,
			body?: IDataObject,
			qs?: IDataObject,
		): Promise<IDataObject> => {
			const options: IHttpRequestOptions = {
				method,
				url: `${baseUrl}${url}`,
				json: true,
				...(body ? { body } : {}),
				// First-party usage attribution: the backend reads `source` (same as OpenClaw).
				qs: { source: 'N8N', ...(qs ?? {}) },
			};
			return (await this.helpers.httpRequestWithAuthentication.call(
				this,
				'mem0Api',
				options,
			)) as IDataObject;
		};

		for (let i = 0; i < items.length; i++) {
			try {
				const operation = this.getNodeParameter('operation', i) as string;
				let responseData: IDataObject | IDataObject[] = {};

				if (operation === 'add') {
					const messagesUi = this.getNodeParameter('messages.message', i, []) as IDataObject[];
					if (!messagesUi.length) {
						throw new NodeOperationError(this.getNode(), 'At least one message is required', {
							itemIndex: i,
						});
					}
					const addFields = this.getNodeParameter('addFields', i, {}) as IDataObject;
					const body: IDataObject = {
						messages: messagesUi.map((m) => ({ role: m.role, content: m.content })),
						infer: addFields.infer !== undefined ? addFields.infer : true,
					};
					const userId = this.getNodeParameter('userId', i, '') as string;
					if (userId) body.user_id = userId;
					if (addFields.agent_id) body.agent_id = addFields.agent_id;
					if (addFields.app_id) body.app_id = addFields.app_id;
					if (addFields.run_id) body.run_id = addFields.run_id;
					if (addFields.metadata) {
						try {
							body.metadata =
								typeof addFields.metadata === 'string'
									? JSON.parse(addFields.metadata as string)
									: addFields.metadata;
						} catch {
							throw new NodeOperationError(this.getNode(), 'Invalid JSON in "Metadata" field', {
								itemIndex: i,
							});
						}
					}

					// Custom extraction controls (optional): steer what the API extracts.
					if (addFields.custom_instructions) {
						body.custom_instructions = addFields.custom_instructions;
					}
					if (addFields.custom_categories) {
						try {
							body.custom_categories =
								typeof addFields.custom_categories === 'string'
									? JSON.parse(addFields.custom_categories as string)
									: addFields.custom_categories;
						} catch {
							throw new NodeOperationError(
								this.getNode(),
								'Invalid JSON in "Custom Categories" field',
								{ itemIndex: i },
							);
						}
					}

					if (addFields.includes) body.includes = addFields.includes;
					if (addFields.excludes) body.excludes = addFields.excludes;

					// API requires at least one entity id — fail clearly instead of a raw 4xx.
					if (!body.user_id && !body.agent_id && !body.run_id && !body.app_id) {
						throw new NodeOperationError(
							this.getNode(),
							'Add requires at least one of User ID, Agent ID, Run ID, or App ID',
							{ itemIndex: i },
						);
					}

					const addResp = await request('POST', '/v3/memories/add/', body);
					const waitForCompletion = this.getNodeParameter('waitForCompletion', i, true) as boolean;
					const addStatus = addResp.status as string | undefined;
					const isTerminal = addStatus === 'SUCCEEDED' || addStatus === 'FAILED';

					// Add returns {event_id, status:PENDING|RUNNING}; poll until terminal when asked to wait.
					if (waitForCompletion && addResp.event_id && !isTerminal) {
						responseData = await pollEvent(request, addResp.event_id as string, this, i);
					} else if (addStatus === 'FAILED') {
						throw new NodeOperationError(
							this.getNode(),
							`Mem0 memory add failed: ${(addResp.message as string) || 'unknown error'}`,
							{ itemIndex: i },
						);
					} else {
						// If the response is already terminal, unwrap results; otherwise return as-is.
						responseData = Array.isArray(addResp.results)
							? (addResp.results as IDataObject[])
							: addResp;
					}
				} else if (operation === 'search') {
					const body: IDataObject = {
						query: this.getNodeParameter('query', i) as string,
						output_format: 'v1.1',
						top_k: this.getNodeParameter('limit', i, 50) as number,
					};
					body.filters = buildEntityFilters(
						{
							user_id: this.getNodeParameter('userId', i, '') as string,
							agent_id: this.getNodeParameter('agentId', i, '') as string,
							app_id: this.getNodeParameter('appId', i, '') as string,
							run_id: this.getNodeParameter('runId', i, '') as string,
						},
						this,
						i,
					);
					const resp = await request('POST', '/v3/memories/search/', body);
					responseData = Array.isArray(resp.results) ? (resp.results as IDataObject[]) : [];
				} else if (operation === 'getAll') {
					const returnAll = this.getNodeParameter('returnAll', i, false) as boolean;
					const pageSize = this.getNodeParameter('pageSize', i, 50) as number;
					const body: IDataObject = {
						filters: buildEntityFilters(
							{
								user_id: this.getNodeParameter('userId', i, '') as string,
								agent_id: this.getNodeParameter('agentId', i, '') as string,
								app_id: this.getNodeParameter('appId', i, '') as string,
								run_id: this.getNodeParameter('runId', i, '') as string,
							},
							this,
							i,
						),
					};
					if (returnAll) {
						// Page through until a short/empty page or no `next` (hard-capped for safety).
						const all: IDataObject[] = [];
						for (let page = 1; page <= 10000; page++) {
							const resp = await request('POST', '/v3/memories/', body, { page, page_size: pageSize });
							const results = Array.isArray(resp.results) ? (resp.results as IDataObject[]) : [];
							all.push(...results);
							if (results.length < pageSize || !resp.next) break;
						}
						responseData = all;
					} else {
						const page = this.getNodeParameter('page', i, 1) as number;
						const resp = await request('POST', '/v3/memories/', body, { page, page_size: pageSize });
						responseData = Array.isArray(resp.results) ? (resp.results as IDataObject[]) : [];
					}
				} else if (operation === 'get') {
					const memoryId = this.getNodeParameter('memoryId', i) as string;
					responseData = await request('GET', `/v1/memories/${encodeURIComponent(memoryId)}/`);
				} else if (operation === 'update') {
					const memoryId = this.getNodeParameter('memoryId', i) as string;
					const body: IDataObject = {};
					const text = this.getNodeParameter('text', i, '') as string;
					const metadata = this.getNodeParameter('metadata', i, '') as string;
					if (text) body.text = text;
					if (metadata) {
						try {
							body.metadata = typeof metadata === 'string' ? JSON.parse(metadata) : metadata;
						} catch {
							throw new NodeOperationError(this.getNode(), 'Invalid JSON in "Metadata" field', {
								itemIndex: i,
							});
						}
					}
					if (Object.keys(body).length === 0) {
						throw new NodeOperationError(this.getNode(), 'Provide text or metadata to update', {
							itemIndex: i,
						});
					}
					responseData = await request('PUT', `/v1/memories/${encodeURIComponent(memoryId)}/`, body);
				} else if (operation === 'delete') {
					const memoryId = this.getNodeParameter('memoryId', i) as string;
					responseData = await request('DELETE', `/v1/memories/${encodeURIComponent(memoryId)}/`);
				}

				const arr = Array.isArray(responseData) ? responseData : [responseData];
				for (const entry of arr) {
					returnData.push({ json: entry, pairedItem: { item: i } });
				}
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({ json: { error: (error as Error).message }, pairedItem: { item: i } });
					continue;
				}
				throw new NodeApiError(this.getNode(), error as JsonObject, { itemIndex: i });
			}
		}

		return [returnData];
	}
}

function buildEntityFilters(
	ids: Record<string, string>,
	ctx: IExecuteFunctions,
	itemIndex: number,
): IDataObject {
	const clauses: IDataObject[] = Object.entries(ids)
		.filter(([, value]) => value)
		.map(([key, value]) => ({ [key]: value }));

	if (clauses.length === 0) {
		throw new NodeOperationError(
			ctx.getNode(),
			'Provide at least one of User ID, Agent ID, App ID, or Run ID',
			{ itemIndex },
		);
	}

	return clauses.length === 1 ? clauses[0] : { OR: clauses };
}

// Polls GET /v1/event/{id}/ until the memory-addition event resolves.
async function pollEvent(
	request: (m: IHttpRequestMethods, u: string) => Promise<IDataObject>,
	eventId: string,
	ctx: IExecuteFunctions,
	itemIndex: number,
): Promise<IDataObject | IDataObject[]> {
	for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
		const event = await request('GET', `/v1/event/${encodeURIComponent(eventId)}/`);
		const status = event.status as string;
		if (status === 'SUCCEEDED') {
			// Match the shape of search/getAll (a clean array); fall back to the envelope.
			return Array.isArray(event.results) ? (event.results as IDataObject[]) : event;
		}
		if (status === 'FAILED') {
			const reason = (event.error as string) || (event.message as string) || 'unknown error';
			throw new NodeOperationError(
				ctx.getNode(),
				`Mem0 memory event ${eventId} failed: ${reason}`,
				{ itemIndex },
			);
		}
		await sleep(POLL_INTERVAL_MS);
	}
	throw new NodeOperationError(
		ctx.getNode(),
		`Timed out waiting for memory event ${eventId} to complete`,
		{ itemIndex },
	);
}
