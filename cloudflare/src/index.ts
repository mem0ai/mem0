import { McpSession } from './mcp-session';

export interface Env {
	MCP_SESSION: DurableObjectNamespace;
	BACKEND_URL: string;
}

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
		const url = new URL(request.url);
		const pathParts = url.pathname.split('/').filter(Boolean);

		// Expected URL format: /mcp/{client_name}/sse/{user_id}
		if (pathParts.length < 4 || pathParts[0] !== 'mcp' || pathParts[2] !== 'sse') {
			return new Response('Invalid MCP URL format. Expected /mcp/{client_name}/sse/{user_id}', { status: 400 });
		}

		const client_name = pathParts[1];
		const user_id = pathParts[3];

		// We use a combination of user_id and client_name to create a unique durable object.
		// This ensures that a user can have separate sessions for different clients (e.g., claude, cursor).
		const doId = `${user_id}::${client_name}`;
		const id = env.MCP_SESSION.idFromName(doId);
		const stub = env.MCP_SESSION.get(id);

		// Pass the backend URL to the durable object via a header.
		// This makes the durable object more portable and easier to test.
		const requestWithBackendUrl = new Request(request.url, request);
		requestWithBackendUrl.headers.set('X-Backend-Url', env.BACKEND_URL);
		requestWithBackendUrl.headers.set('X-Client-Name', client_name);
		requestWithBackendUrl.headers.set('X-User-Id', user_id);

		// Forward the request to the Durable Object.
		return stub.fetch(requestWithBackendUrl);
	},
};

export { McpSession }; 