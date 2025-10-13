// Minimal mem0 client for edge runtimes using fetch
// This file intentionally avoids Node-specific APIs (fs, streams, native bindings).

type Mem0ClientOptions = {
  baseUrl: string; // e.g. https://mem0.example.com
  apiKey?: string;
};

export class Mem0WorkerClient {
  baseUrl: string;
  apiKey?: string;

  constructor(opts: Mem0ClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, "");
    this.apiKey = opts.apiKey;
  }

  // Example: create a memory entry
  async createMemory(payload: Record<string, unknown>) {
    return this.request('/v1/memories', {
      method: 'POST',
      body: JSON.stringify(payload),
      headers: {'Content-Type': 'application/json'},
    });
  }

  async queryMemory(query: Record<string, unknown>) {
    return this.request('/v1/memories/query', {
      method: 'POST',
      body: JSON.stringify(query),
      headers: {'Content-Type': 'application/json'},
    });
  }

  private async request(path: string, init: RequestInit = {}) {
    const headers = new Headers(init.headers as HeadersInit);
    if (this.apiKey) headers.set('Authorization', `Bearer ${this.apiKey}`);

    const res = await fetch(this.baseUrl + path, {
      ...init,
      headers,
    });

    const contentType = res.headers.get('content-type') || '';
    if (!res.ok) {
      const body = contentType.includes('application/json') ? await res.json().catch(() => null) : await res.text().catch(() => null);
      const err: any = new Error(`mem0 request failed: ${res.status} ${res.statusText}`);
      err.status = res.status;
      err.body = body;
      throw err;
    }

    if (contentType.includes('application/json')) return res.json();
    return res.text();
  }
}

export default Mem0WorkerClient;
