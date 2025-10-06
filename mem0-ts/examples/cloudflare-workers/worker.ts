/**
 * Cloudflare Worker example using mem0ai
 *
 * This example demonstrates how to use mem0ai in a Cloudflare Worker
 * to create a chat agent with persistent memory.
 */

import { CloudflareWorkerMemoryClient } from "../../src/workers";

// Types for the request/response
interface ChatRequest {
  message: string;
  user_id: string;
}

interface ChatResponse {
  response: string;
  memories_added: number;
  relevant_memories: Array<{
    memory: string;
    score: number;
  }>;
}

interface Env {
  MEM0_API_KEY: string;
  OPENAI_API_KEY: string;
}

/**
 * Simple OpenAI client for Cloudflare Workers
 */
class OpenAIClient {
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  async chat(
    messages: Array<{ role: string; content: string }>,
  ): Promise<string> {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages,
        max_tokens: 1000,
        temperature: 0.7,
      }),
    });

    if (!response.ok) {
      throw new Error(`OpenAI API error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
  }
}

/**
 * Main chat handler with persistent memory
 */
async function handleChat(
  request: ChatRequest,
  env: Env,
): Promise<ChatResponse> {
  // Initialize clients
  const memory = new CloudflareWorkerMemoryClient({
    apiKey: env.MEM0_API_KEY,
  });

  const openai = new OpenAIClient(env.OPENAI_API_KEY);

  const { message, user_id } = request;

  try {
    // Search for relevant memories
    const relevantMemories = await memory.search(message, {
      user_id,
      limit: 5,
    });

    // Build context from memories
    const memoryContext = relevantMemories
      .map((m) => `- ${m.memory}`)
      .join("\n");

    // Create system prompt with memory context
    const systemPrompt = `You are a helpful AI assistant with access to the user's conversation history and preferences.

${memoryContext ? `Here's what you know about the user:\n${memoryContext}\n` : ""}

Respond naturally and refer to relevant memories when appropriate. Be helpful and engaging.`;

    // Generate response using OpenAI
    const aiResponse = await openai.chat([
      { role: "system", content: systemPrompt },
      { role: "user", content: message },
    ]);

    // Store the conversation in memory
    const memoryResult = await memory.add(
      [
        { role: "user", content: message },
        { role: "assistant", content: aiResponse },
      ],
      { user_id },
    );

    return {
      response: aiResponse,
      memories_added: memoryResult.length,
      relevant_memories: relevantMemories.slice(0, 3).map((m) => ({
        memory: m.memory,
        score: m.score || 0,
      })),
    };
  } catch (error: any) {
    console.error("Chat handler error:", error);
    throw new Error(`Failed to process chat: ${error.message}`);
  }
}

/**
 * Cloudflare Worker fetch event handler
 */
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Handle CORS preflight requests
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
      });
    }

    // Handle POST requests to /chat
    if (
      request.method === "POST" &&
      new URL(request.url).pathname === "/chat"
    ) {
      try {
        const chatRequest: ChatRequest = await request.json();

        // Validate request
        if (!chatRequest.message || !chatRequest.user_id) {
          return new Response(
            JSON.stringify({
              error: "Missing required fields: message and user_id",
            }),
            {
              status: 400,
              headers: {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
              },
            },
          );
        }

        // Process chat
        const response = await handleChat(chatRequest, env);

        return new Response(JSON.stringify(response), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
          },
        });
      } catch (error: any) {
        console.error("Request processing error:", error);
        return new Response(
          JSON.stringify({
            error: "Internal server error",
            details: error.message,
          }),
          {
            status: 500,
            headers: {
              "Content-Type": "application/json",
              "Access-Control-Allow-Origin": "*",
            },
          },
        );
      }
    }

    // Handle GET request for health check
    if (
      request.method === "GET" &&
      new URL(request.url).pathname === "/health"
    ) {
      return new Response(
        JSON.stringify({
          status: "healthy",
          timestamp: new Date().toISOString(),
          mem0_available: !!env.MEM0_API_KEY,
          openai_available: !!env.OPENAI_API_KEY,
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
          },
        },
      );
    }

    // Default 404 response
    return new Response(
      JSON.stringify({
        error: "Not found",
        available_endpoints: [
          "POST /chat - Send a chat message",
          "GET /health - Health check",
        ],
      }),
      {
        status: 404,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      },
    );
  },
};
