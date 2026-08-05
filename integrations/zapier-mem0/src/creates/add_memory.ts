import type { ZObject, Bundle, AddResponse, EventResponse } from '../types';
import { captureEvent } from '../telemetry';

const POLL_INTERVAL_MS = 1500;
// Bounded to a 60s poll budget, under Zapier's per-step execution timeout.
const MAX_POLL_ATTEMPTS = 40;

// Polls GET /v1/event/{id}/ until the async memory-addition event resolves.
const pollEvent = async (z: ZObject, eventId: string): Promise<EventResponse> => {
	for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt++) {
		const res = await z.request({ url: `/v1/event/${eventId}/`, method: 'GET' });
		const data = res.data as EventResponse;
		const status = data && data.status;
		if (status === 'SUCCEEDED') {
			return data;
		}
		if (status === 'FAILED') {
			const reason = (data && (data.error || data.message)) || 'unknown error';
			throw new z.errors.Error(`Mem0 memory event ${eventId} failed: ${reason}`, 'Mem0EventFailed', 400);
		}
		await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
	}
	throw new z.errors.Error(
		`Timed out waiting for memory event ${eventId}. The add was accepted and is ` +
			`likely still completing on the server — a timeout here does not mean it failed.`,
		'Mem0Timeout',
		408,
	);
};

const perform = async (z: ZObject, bundle: Bundle): Promise<AddResponse | EventResponse> => {
	// Zapier boolean fields can arrive as the strings 'true'/'false'; coerce
	// explicitly so "Infer = No" / "Wait = No" are honored.
	const infer = String(bundle.inputData.infer) !== 'false';
	// Waiting is opt-in (the poll path can exceed Zapier's step timeout).
	const wait = String(bundle.inputData.waitForCompletion) === 'true';

	const body: Record<string, unknown> = {
		messages: [{ role: bundle.inputData.role || 'user', content: bundle.inputData.content }],
		infer,
	};
	if (bundle.inputData.user_id) body.user_id = bundle.inputData.user_id;
	if (bundle.inputData.agent_id) body.agent_id = bundle.inputData.agent_id;
	if (bundle.inputData.run_id) body.run_id = bundle.inputData.run_id;
	if (bundle.inputData.metadata) {
		try {
			body.metadata =
				typeof bundle.inputData.metadata === 'string'
					? JSON.parse(bundle.inputData.metadata)
					: bundle.inputData.metadata;
		} catch {
			throw new z.errors.Error('Metadata must be valid JSON.', 'InvalidInput', 400);
		}
	}
	// Custom extraction controls (optional): steer what the API extracts.
	if (bundle.inputData.custom_instructions) {
		body.custom_instructions = bundle.inputData.custom_instructions;
	}
	if (bundle.inputData.custom_categories) {
		try {
			body.custom_categories =
				typeof bundle.inputData.custom_categories === 'string'
					? JSON.parse(bundle.inputData.custom_categories)
					: bundle.inputData.custom_categories;
		} catch {
			throw new z.errors.Error('Custom Categories must be valid JSON.', 'InvalidInput', 400);
		}
	}
	if (bundle.inputData.includes) body.includes = bundle.inputData.includes;
	if (bundle.inputData.excludes) body.excludes = bundle.inputData.excludes;

	captureEvent('zapier.add_memory', bundle.authData?.apiKey, { infer, wait });

	const response = await z.request({
		url: '/v3/memories/add/',
		method: 'POST',
		body,
	});

	// Default to an empty object so an empty/no-content 2xx body can't crash the
	// `.status` / `.event_id` reads below.
	const data = (response.data ?? {}) as AddResponse;

	// Add returns {event_id, status:PENDING|RUNNING}; poll only when opted in.
	if (wait && data.event_id && data.status !== 'SUCCEEDED' && data.status !== 'FAILED') {
		return pollEvent(z, data.event_id);
	}
	if (data.status === 'FAILED') {
		const reason = data.error || data.message || 'unknown error';
		throw new z.errors.Error(`Mem0 memory add failed: ${reason}`, 'Mem0EventFailed', 400);
	}
	return data;
};

export default {
	key: 'add_memory',
	noun: 'Memory',
	display: {
		label: 'Add Memory',
		description: 'Extract and store memories from a message.',
	},
	operation: {
		perform,
		inputFields: [
			{
				key: 'content',
				label: 'Content',
				type: 'text',
				required: true,
				helpText: 'The message content to extract memories from.',
			},
			{
				key: 'role',
				label: 'Role',
				choices: { user: 'User', assistant: 'Assistant', system: 'System' },
				default: 'user',
			},
			{ key: 'user_id', label: 'User ID', type: 'string', required: true, helpText: 'Scope this memory to a user. Mem0 requires at least one entity ID.' },
			{ key: 'agent_id', label: 'Agent ID', type: 'string' },
			{ key: 'run_id', label: 'Run ID', type: 'string' },
			{ key: 'metadata', label: 'Metadata (JSON)', type: 'string' },
			{
				key: 'custom_instructions',
				label: 'Custom Instructions',
				type: 'text',
				helpText: 'Optional instructions that steer what the extractor keeps or ignores.',
			},
			{
				key: 'custom_categories',
				label: 'Custom Categories (JSON)',
				type: 'string',
				helpText:
					'Optional taxonomy for categorising memories, as a JSON array of {category: description} objects.',
			},
			{
				key: 'includes',
				label: 'Includes',
				type: 'text',
				helpText: 'Optional: only extract memories matching this description.',
			},
			{
				key: 'excludes',
				label: 'Excludes',
				type: 'text',
				helpText: 'Optional: skip memories matching this description.',
			},
			{
				key: 'infer',
				label: 'Infer',
				type: 'boolean',
				default: 'true',
				helpText: 'Run LLM extraction over the message. Turn off to store it verbatim.',
			},
			{
				key: 'waitForCompletion',
				label: 'Wait for Completion',
				type: 'boolean',
				default: 'false',
				helpText:
					'Poll until extraction finishes and return the resulting memories. ' +
					'Leave off (default) to return immediately with an event ID — extraction can take ' +
					'longer than Zapier allows this step to run, and a timeout does not mean the add failed.',
			},
		],
		// Default (no-wait) returns the accepted event; the wait path returns the resolved event.
		sample: { event_id: '00000000-0000-0000-0000-000000000000', status: 'PENDING' },
	},
};
