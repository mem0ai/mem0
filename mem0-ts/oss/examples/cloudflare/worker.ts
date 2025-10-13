import Mem0WorkerClient from './mem0-worker-client';

// Read env from global bindings (Cloudflare Workers / Wrangler style)
declare const MEM0_API_BASE: string | undefined;
declare const MEM0_API_KEY: string | undefined;

const client = new Mem0WorkerClient({
  baseUrl: typeof MEM0_API_BASE === 'string' ? MEM0_API_BASE : 'https://mem0.example.com',
  apiKey: typeof MEM0_API_KEY === 'string' ? MEM0_API_KEY : undefined,
});

addEventListener('fetch', (event: any) => {
  event.respondWith(handle(event.request));
});

async function handle(request: Request): Promise<Response> {
  const url = new URL(request.url);

  if (url.pathname === '/create' && request.method === 'POST') {
    try {
      const payload = await request.json();
      const result = await client.createMemory(payload);
      return new Response(JSON.stringify(result), {status: 201, headers: {'Content-Type': 'application/json'}});
    } catch (err: any) {
      return new Response(JSON.stringify({error: String(err), details: err?.body || null}), {status: err?.status || 500, headers: {'Content-Type': 'application/json'}});
    }
  }

  if (url.pathname === '/query' && request.method === 'POST') {
    try {
      const query = await request.json();
      const result = await client.queryMemory(query);
      return new Response(JSON.stringify(result), {status: 200, headers: {'Content-Type': 'application/json'}});
    } catch (err: any) {
      return new Response(JSON.stringify({error: String(err), details: err?.body || null}), {status: err?.status || 500, headers: {'Content-Type': 'application/json'}});
    }
  }

  return new Response('OK', {status: 200});
}
