// cloudflare/src/mcp-session.ts

export class McpSession implements DurableObject {
	state: DurableObjectState;
	backendUrl!: string;
	clientName!: string;
	userId!: string;
    sseController?: ReadableStreamDefaultController;
    sessionReady: boolean = false;

	constructor(state: DurableObjectState) {
		this.state = state;
	}

    private cleanupSession() {
        if (this.sseController) {
            try {
                if (this.sseController.desiredSize !== null) {
                    this.sseController.close();
                }
            } catch (e) {
                // Stream already closed, ignore the error
                console.log("Stream already closed during cleanup");
            }
            this.sseController = undefined;
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
        // Clean up any existing session
        if (this.sseController) {
            console.log("Cleaning up existing SSE session before creating new one");
            this.cleanupSession();
        }

        const encoder = new TextEncoder();

        // Create a ReadableStream for SSE
        const readable = new ReadableStream({
            start: (controller) => {
                console.log("SSE ReadableStream started");
                this.sseController = controller;
                this.sessionReady = true;
                console.log("SSE session ready");

                // Send initial connection confirmation immediately
                const initialMessage = "data: " + JSON.stringify({type: "connection", status: "connected"}) + "\n\n";
                try {
                    controller.enqueue(encoder.encode(initialMessage));
                    console.log("Initial SSE message sent successfully");
                } catch (e) {
                    console.error("Failed to send initial SSE message:", e);
                }

                // Handle client disconnection
                request.signal?.addEventListener('abort', () => {
                    console.log("SSE stream aborted by client. Releasing controller.");
                    this.cleanupSession();
                });
            },
            cancel: () => {
                console.log("SSE stream cancelled");
                this.cleanupSession();
            }
        });

        // Return SSE response with proper headers
        return new Response(readable, {
            headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'X-Accel-Buffering': 'no', // Disable nginx buffering
                'Transfer-Encoding': 'chunked',
            },
        });
    }

    async handlePostMessage(request: Request): Promise<Response> {
        // Simple retry mechanism - wait for session to be ready
        let retries = 0;
        while ((!this.sessionReady || !this.sseController) && retries < 50) {
            console.log("Session not ready, waiting...", retries);
            await new Promise(resolve => setTimeout(resolve, 100)); // Wait 100ms
            retries++;
        }

        if (!this.sessionReady || !this.sseController) {
            return new Response("Session initialization timeout", { status: 408 });
        }

        return this.processMessage(request);
    }

    private async processMessage(request: Request): Promise<Response> {
        if (!this.sseController) {
            return new Response("No active SSE session for this client.", { status: 400 });
        }

        try {
            const message = await request.text();
            console.log("Processing message:", message.substring(0, 200) + "...");
            
            // Proxy the POST request to the backend
            const backendResponseJson = await this.proxyToBackend(message);
            console.log("Backend response:", JSON.stringify(backendResponseJson).substring(0, 200) + "...");

            // Send the backend's response via SSE
            const encoder = new TextEncoder();
            const sseMessage = "data: " + JSON.stringify(backendResponseJson) + "\n\n";
            this.sseController.enqueue(encoder.encode(sseMessage));
            console.log("Response sent via SSE successfully");

            // Return success acknowledgement for the POST request
            return new Response(JSON.stringify({status: "ok"}), { 
                status: 200, 
                headers: {'Content-Type': 'application/json'} 
            });

        } catch (e: any) {
            console.error("Error in processMessage:", e);
            if (this.sseController) {
                try {
                    // Send error via SSE stream
                    const errorPayload = { jsonrpc: "2.0", error: { code: -32603, message: e.message } };
                    const encoder = new TextEncoder();
                    const errorMessage = "data: " + JSON.stringify(errorPayload) + "\n\n";
                    this.sseController.enqueue(encoder.encode(errorMessage));
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