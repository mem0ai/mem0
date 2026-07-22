import {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class Mem0Api implements ICredentialType {
	name = 'mem0Api';

	displayName = 'Mem0 API';

	documentationUrl = 'https://docs.mem0.ai/platform/quickstart';

	properties: INodeProperties[] = [
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			description: 'Your Mem0 API key (starts with "m0-"). Create one at app.mem0.ai → Settings → API Keys.',
		},
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'https://api.mem0.ai',
			description: 'Mem0 API base URL. Override only for self-hosted or non-default deployments.',
		},
	];

	// Injects "Authorization: Token <apiKey>" on every request, matching the
	// scheme used by Mem0's official SDKs (Authorization: Token m0-...).
	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Token {{$credentials.apiKey}}',
			},
		},
	};

	// Cheap authenticated GET; validates the key when the user clicks "Test".
	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/v1/ping/',
			method: 'GET',
		},
	};
}
