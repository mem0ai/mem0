// cloudflare/src/mcp-session.ts

export class McpSession implements DurableObject {
	state: DurableObjectState;
	backendUrl!: string;
	clientName!: string;
	userId!: string;
    sseWriter?: WritableStreamDefaultWriter;
    sessionReady: boolean = false;

	constructor(state: DurableObjectState) {
		this.state = state;
	}

    private cleanupWriter() {
        if (this.sseWriter) {
            this.sseWriter.close().catch((e) => {
                console.log("Error closing writer during cleanup:", e);
            });
            this.sseWriter = undefined;
        }
        this.sessionReady = false;
    }

	async fetch(request: Request): Promise<Response> {
		this.backendUrl = request.headers.get('X-Backend-Url')!;
		this.clientName = request.headers.get('X-Client-Name')!;
		this.userId = request.headers.get('X-User-Id')!;

		if (!this.backendUrl || !this.clientName || !this.userId) {
			return new Response('Internal error: Missing backend URL or client identifiers.', { status: 500 });
		}

		const url = new URL(request.url);
		const path = url.pathname;

        if (path === '/sse' && request.method === 'GET') {
            return this.handleSseRequest(request);
        } else if (path === '/messages' && request.method === 'POST') {
            return this.handlePostMessage(request);
        } else if (path === '/sse' && request.method === 'POST') {
            // Support legacy POST to SSE endpoint
            return this.handlePostMessage(request);
        }

        return new Response(`Method ${request.method} not allowed for path ${path}`, { status: 405 });
	}

    async handleSseRequest(request: Request): Promise<Response> {
        // If there's an existing writer, try to close it first
        if (this.sseWriter) {
            console.log("Cleaning up existing SSE session before creating new one");
            try {
                await this.sseWriter.close();
            } catch (e) {
                console.log("Error closing existing writer:", e);
            }
            this.sseWriter = undefined;
        }

        const { readable, writable } = new TransformStream({
            start() {
                console.log("SSE TransformStream started");
            },
            transform(chunk, controller) {
                console.log("SSE transform:", chunk);
                controller.enqueue(chunk);
            }
        });

        this.sseWriter = writable.getWriter();

        // Handle client disconnection using request signal
        request.signal?.addEventListener('abort', () => {
            console.log("SSE stream aborted by client. Releasing writer.");
            this.cleanupWriter();
        });

        // Handle stream errors
        this.sseWriter.closed.then(() => {
            console.log("SSE writer closed normally. Releasing writer.");
            this.sseWriter = undefined;
        }).catch((err: Error) => {
            console.log("SSE writer error. Releasing writer.", err.message);
            this.cleanupWriter();
        });

        // Send initial connection confirmation immediately
        const encoder = new TextEncoder();
        const initialMessage = "data: {\"type\":\"connection\",\"status\":\"connected\"}\n\n";
        
        // Write immediately without await to avoid blocking
        this.sseWriter.write(encoder.encode(initialMessage)).then(() => {
            // Mark session as ready
            this.sessionReady = true;
            console.log("SSE session ready");
        }).catch((e) => {
            console.error("Failed to write initial SSE message:", e);
        });

        // Return a streaming response that will be held open.
        return new Response(readable, {
            headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control',
            },
        });
    }

    async handlePostMessage(request: Request): Promise<Response> {
        // Simple retry mechanism - wait for session to be ready
        let retries = 0;
        while ((!this.sessionReady || !this.sseWriter) && retries < 50) {
            console.log("Session not ready, waiting...", retries);
            await new Promise(resolve => setTimeout(resolve, 100)); // Wait 100ms
            retries++;
        }

        if (!this.sessionReady || !this.sseWriter) {
            return new Response("Session initialization timeout", { status: 408 });
        }

        return this.processMessage(request);
    }

    private async processMessage(request: Request): Promise<Response> {
        if (!this.sseWriter) {
            return new Response("No active SSE session for this client.", { status: 400 });
        }

        try {
            const message = await request.text();
            
            // Proxy the POST request to the backend. The backend will run the tool.
            const backendResponseJson = await this.proxyToBackend(message);

            // Format the backend's response as an SSE 'data' event and write it to the open stream.
            const sseMessage = `data: ${JSON.stringify(backendResponseJson)}\n\n`;
            const encoder = new TextEncoder();
            await this.sseWriter.write(encoder.encode(sseMessage));

            // The client is listening on the SSE stream, not for this POST response.
            // Return a simple success acknowledgement for the POST request itself.
            return new Response(JSON.stringify({status: "ok"}), { status: 200, headers: {'Content-Type': 'application/json'} });

        } catch (e: any) {
            console.error("Error in processMessage:", e);
            if (this.sseWriter) {
                try {
                    // Try to inform the client of the error via the SSE stream.
                    const errorPayload = { jsonrpc: "2.0", error: { code: -32603, message: e.message } };
                    const errorSseMessage = `data: ${JSON.stringify(errorPayload)}\n\n`;
                    const encoder = new TextEncoder();
                    await this.sseWriter.write(encoder.encode(errorSseMessage));
                } catch (writeError) {
                    console.error("Failed to write error to SSE stream:", writeError);
                }
            }
            return new Response("Internal Server Error", { status: 500 });
        }
    }

	async proxyToBackend(message: string | ArrayBuffer) {
		const url = `${this.backendUrl}/mcp/messages/`;
		try {
			const response = await fetch(url, {
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
				return { jsonrpc: "2.0", error: { code: response.status, message: "Backend Error", data: errorText }};
			}

			return await response.json();
		} catch (error: any) {
			console.error('Error proxying to backend:', error);
			return { jsonrpc: "2.0", error: { code: -32000, message: "Proxy Error", data: error.message }};
		}
	}
}

interface Env {
	BACKEND_URL: string;
} 