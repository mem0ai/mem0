// cloudflare/src/mcp-session.ts

export class McpSession implements DurableObject {
	state: DurableObjectState;
	backendUrl!: string;
	clientName!: string;
	userId!: string;
	webSocket?: WebSocket;

	constructor(state: DurableObjectState, env: Env) {
		this.state = state;
		// `blockConcurrencyWhile()` ensures that no other events are delivered until the promise resolves.
		this.state.blockConcurrencyWhile(async () => {
			// Restore any necessary state from storage.
		});
	}

	async fetch(request: Request): Promise<Response> {
		const url = new URL(request.url);
		this.backendUrl = request.headers.get('X-Backend-Url')!;
		this.clientName = request.headers.get('X-Client-Name')!;
		this.userId = request.headers.get('X-User-Id')!;

		if (!this.backendUrl || !this.clientName || !this.userId) {
			return new Response('Internal error: Missing backend URL or client identifiers.', { status: 500 });
		}

		// The original server supports both GET for SSE and POST for messages.
		// We are upgrading to WebSockets for the primary connection for better stability.
		if (request.method === 'POST' && url.pathname.endsWith('/messages')) {
			return this.handlePostMessage(request);
		} else if (request.method === 'GET') {
			return this.handleWebSocketConnection(request);
		} else {
			return new Response('Unsupported request type.', { status: 405 });
		}
	}

	async handleWebSocketConnection(request: Request): Promise<Response> {
		if (request.headers.get('Upgrade') !== 'websocket') {
			return new Response('Expected a WebSocket upgrade request.', { status: 426 });
		}

		const { 0: client, 1: server } = new WebSocketPair();

		this.webSocket = server;
		this.webSocket.accept();

		this.webSocket.addEventListener('message', async (event) => {
			const message = event.data;
			const backendResponse = await this.proxyToBackend(message);
			if (backendResponse && this.webSocket) {
				// The backend already stringifies its response, so we send it directly.
				this.webSocket.send(backendResponse);
			}
		});

		this.webSocket.addEventListener('close', (event) => {
			console.log(`WebSocket closed: code=${event.code}, reason=${event.reason}`);
			this.webSocket = undefined;
		});

		this.webSocket.addEventListener('error', (err) => {
			console.error('WebSocket error:', err);
		});

		return new Response(null, { status: 101, webSocket: client });
	}

	async handlePostMessage(request: Request): Promise<Response> {
		const message = await request.text();
		const response = await this.proxyToBackend(message);
		return new Response(response, {
			headers: { 'Content-Type': 'application/json' },
		});
	}

	async proxyToBackend(message: string | ArrayBuffer) {
		const url = `${this.backendUrl}/mcp/messages/`;
		try {
			// We need to pass the session_id to the python backend.
			// The original python server seems to get it from a query param. Let's create one.
			const sessionId = this.userId + "::" + this.clientName;
			const urlWithSession = new URL(url);
			urlWithSession.searchParams.set('session_id', sessionId);


			// The python server also expects the user and client context.
			// The original server sets this via contextvars based on the URL.
			// We will emulate this by passing them in headers that the backend can be modified to read.
			const response = await fetch(urlWithSession.toString(), {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'Accept': 'application/json',
					'X-User-Id': this.userId,
					'X-Client-Name': this.clientName,
				},
				body: message,
			});

			if (!response.ok) {
				const errorText = await response.text();
				console.error(`Backend error: ${response.status} ${errorText}`);
				return JSON.stringify({ error: `Backend error: ${response.status}`, details: errorText });
			}

			const data = await response.text();
			return data;
		} catch (error) {
			console.error('Error proxying to backend:', error);
			return JSON.stringify({ error: 'Failed to connect to backend' });
		}
	}
}

interface Env {
	BACKEND_URL: string;
} 