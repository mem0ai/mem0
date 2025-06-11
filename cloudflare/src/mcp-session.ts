// cloudflare/src/mcp-session.ts

interface JSONRPCRequest {
    jsonrpc: "2.0";
    id: number | string | null;
    method: string;
    params?: any;
}

interface JSONRPCResponse {
    jsonrpc: "2.0";
    id: number | string | null;
    result?: any;
    error?: {
        code: number;
        message: string;
        data?: any;
    };
}

export class McpSession implements DurableObject {
	state: DurableObjectState;
	backendUrl!: string;
	clientName!: string;
	userId!: string;
    sseController?: ReadableStreamDefaultController;
    sessionReady: boolean = false;
    keepAliveInterval?: any;

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
                console.log("Stream already closed during cleanup");
            }
            this.sseController = undefined;
        }
        if (this.keepAliveInterval) {
            clearInterval(this.keepAliveInterval);
            this.keepAliveInterval = undefined;
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

        // Create SSE stream following official MCP SSE pattern
        const readable = new ReadableStream({
            start: (controller) => {
                console.log("MCP SSE stream started");
                this.sseController = controller;
                this.sessionReady = true;

                // Send endpoint event (official MCP SSE protocol requirement)
                // The endpoint should match our routing pattern: /mcp/{client_name}/messages/{user_id}
                const endpointEvent = `event: endpoint\ndata: /mcp/${this.clientName}/messages/${this.userId}\n\n`;
                controller.enqueue(encoder.encode(endpointEvent));
                console.log("Sent MCP endpoint event");

                // Start sending keep-alive pings every 30 seconds
                this.keepAliveInterval = setInterval(() => {
                    if (this.sseController) {
                        try {
                            const keepAliveComment = ': keep-alive\\n\\n';
                            this.sseController.enqueue(encoder.encode(keepAliveComment));
                        } catch(e) {
                            console.error("Error sending keep-alive, closing session:", e);
                            this.cleanupSession();
                        }
                    }
                }, 30000); // 30 seconds

                // Handle client disconnection
                request.signal?.addEventListener('abort', () => {
                    console.log("SSE stream aborted by client");
                    this.cleanupSession();
                });
            },
            cancel: () => {
                console.log("SSE stream cancelled");
                this.cleanupSession();
            }
        });

        return new Response(readable, {
            headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            },
        });
    }

    async handlePostMessage(request: Request): Promise<Response> {
        if (!this.sessionReady || !this.sseController) {
            return new Response("MCP session not ready", { status: 408 });
        }

        let message: JSONRPCRequest | undefined;
        try {
            const messageText = await request.text();
            message = JSON.parse(messageText) as JSONRPCRequest;
            
            console.log("Processing MCP message:", message.method, "ID:", message.id);

            // Proxy the request to backend, passing the request ID
            const backendResponseJson = await this.proxyToBackend(messageText, message.id);

            // Send response via SSE using proper MCP SSE format
            const encoder = new TextEncoder();
            const sseMessage = `event: message\ndata: ${JSON.stringify(backendResponseJson)}\n\n`;
            this.sseController.enqueue(encoder.encode(sseMessage));
            
            console.log("MCP response sent via SSE for ID:", message.id);

            return new Response(JSON.stringify({status: "ok"}), { 
                status: 200, 
                headers: {'Content-Type': 'application/json'} 
            });

        } catch (error: any) {
            console.error("Error processing MCP message:", error);
            
            if (this.sseController) {
                const errorResponse: JSONRPCResponse = {
                    jsonrpc: "2.0",
                    id: message?.id ?? null,
                    error: {
                        code: -32603,
                        message: error.message
                    }
                };
                
                const encoder = new TextEncoder();
                const errorSseMessage = `event: message\ndata: ${JSON.stringify(errorResponse)}\n\n`;
                this.sseController.enqueue(encoder.encode(errorSseMessage));
            }
            
            return new Response("Internal Server Error", { status: 500 });
        }
    }

    async proxyToBackend(message: string, requestId: number | string | null) {
        const url = `${this.backendUrl}/mcp/messages/`;
        console.log(`Proxying to backend: ${url} for request ID: ${requestId}`);
        const startTime = Date.now();

        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            console.error(`Backend request timed out from worker for ID: ${requestId}`);
            controller.abort()
        }, 55000); // 55s timeout, less than client's 60s

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
                signal: controller.signal,
            });

            const duration = Date.now() - startTime;
            console.log(`Backend responded for ID ${requestId} in ${duration}ms with status ${response.status}`);

            if (!response.ok) {
                const errorText = await response.text();
                console.error(`Backend error for ID ${requestId}: ${response.status} ${errorText}`);
                return { jsonrpc: "2.0", id: requestId, error: { code: response.status, message: "Backend Error", data: errorText }};
            }

            const responseText = await response.text();
            try {
                const jsonResponse = JSON.parse(responseText);
                if (!('id' in jsonResponse) || jsonResponse.id !== requestId) {
                    console.log(`Backend response for ID ${requestId} had mismatched or missing ID. Original ID: ${jsonResponse.id}. Patching to ${requestId}.`);
                    jsonResponse.id = requestId;
                }
                return jsonResponse;
            } catch (e: any) {
                console.error(`Failed to parse backend response as JSON for ID ${requestId}. Error:`, e.message);
                console.error(`Raw backend response text for ID ${requestId}:`, responseText);
                return { jsonrpc: "2.0", id: requestId, error: { code: -32002, message: "Backend response is not valid JSON", data: responseText }};
            }

        } catch (error: any) {
            const duration = Date.now() - startTime;
            if (error.name === 'AbortError') {
                console.error(`Error proxying to backend: fetch aborted after ${duration}ms for ID ${requestId}.`);
                return { jsonrpc: "2.0", id: requestId, error: { code: -32000, message: "Proxy Timeout", data: `Request to backend timed out after ${duration}ms` }};
            }
            console.error(`Error proxying to backend after ${duration}ms for ID ${requestId}:`, error);
            return { jsonrpc: "2.0", id: requestId, error: { code: -32000, message: "Proxy Error", data: error.message }};
        } finally {
            clearTimeout(timeoutId);
        }
    }
}

interface Env {
	BACKEND_URL: string;
} 