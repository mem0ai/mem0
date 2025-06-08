import { McpSession } from './mcp-session';

export interface Env {
	MCP_SESSION: DurableObjectNamespace;
	BACKEND_URL: string;
}

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
		const url = new URL(request.url);
		const pathParts = url.pathname.split('/').filter(Boolean);

		// Support multiple formats:
		// New format: /mcp/{user_id}/sse or /mcp/{user_id}/messages  
		// Old format: /mcp/{client_name}/sse/{user_id} or /mcp/{client_name}/messages/{user_id}
		let user_id: string;
		let client_name: string = 'claude'; // default client
		let endpoint: string;

		if (pathParts.length === 3 && pathParts[0] === 'mcp') {
			// New format: /mcp/{user_id}/sse or /mcp/{user_id}/messages
			user_id = pathParts[1];
			endpoint = pathParts[2];
			if (endpoint !== 'sse' && endpoint !== 'messages') {
				return new Response('Invalid endpoint. Expected /mcp/{user_id}/sse or /mcp/{user_id}/messages', { status: 400 });
			}
		} else if (pathParts.length === 4 && pathParts[0] === 'mcp') {
			// Old format: /mcp/{client_name}/sse/{user_id} or /mcp/{client_name}/messages/{user_id}
			client_name = pathParts[1];
			endpoint = pathParts[2];
			user_id = pathParts[3];  
			if (endpoint !== 'sse' && endpoint !== 'messages') {
				return new Response('Invalid endpoint. Expected sse or messages', { status: 400 });
			}
		} else {
			return new Response('Invalid MCP URL format. Expected /mcp/{user_id}/sse, /mcp/{user_id}/messages, /mcp/{client_name}/sse/{user_id}, or /mcp/{client_name}/messages/{user_id}', { status: 400 });
		}

		// Create Durable Object ID from user_id and client_name
		const doId = `${user_id}::${client_name}`;
		const id = env.MCP_SESSION.idFromName(doId);
		const stub = env.MCP_SESSION.get(id);

		// Create a new request with the correct path for the Durable Object
		let newPath: string;
		if (endpoint === 'sse') {
			newPath = '/sse';
		} else {
			newPath = '/messages';
		}

		const newUrl = new URL(request.url);
		newUrl.pathname = newPath;
		
		const requestWithBackendUrl = new Request(newUrl.toString(), request);
		requestWithBackendUrl.headers.set('X-Backend-Url', env.BACKEND_URL);
		requestWithBackendUrl.headers.set('X-Client-Name', client_name);
		requestWithBackendUrl.headers.set('X-User-Id', user_id);

		// Forward the request to the Durable Object.
		return stub.fetch(requestWithBackendUrl);
	},
};

export { McpSession }; 