import type { ZObject, Bundle } from './types';

// Custom (API key) authentication for Mem0.
// The key is sent as "Authorization: Token <apiKey>" (matches Mem0's SDKs).
const test = (z: ZObject, _bundle: Bundle) => z.request({ url: '/v1/ping/', method: 'GET' });

export default {
	type: 'custom',
	test,
	fields: [
		{
			key: 'apiKey',
			label: 'Mem0 API Key',
			// `password` so Zapier masks the key in the connection UI (it is a secret).
			type: 'password',
			required: true,
			helpText:
				'Your Mem0 API key (starts with `m0-`). Create one at [app.mem0.ai](https://app.mem0.ai) → Settings → API Keys.',
		},
		{
			key: 'baseUrl',
			label: 'Base URL',
			type: 'string',
			required: false,
			default: 'https://api.mem0.ai',
			helpText: 'Override only for self-hosted or non-default deployments.',
		},
	],
	// Shown on the connection label in the Zap editor. Uses the account email
	// from the /v1/ping/ test response so users with multiple Mem0 connections
	// can tell them apart.
	connectionLabel: '{{user_email}}',
};
