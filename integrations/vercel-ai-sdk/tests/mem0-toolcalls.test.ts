import dotenv from "dotenv";
dotenv.config();

import { addMemories, createMem0 } from "../src";
import { generateText, tool } from "ai";
import { testConfig } from "../config/test-config";
import { z } from "zod";

describe("Tool Calls Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(30000);

  beforeEach(async () => {
    await addMemories([{
      role: "user",
      content: [{ type: "text", text: "I live in Mumbai" }],
    }], { user_id: userId });
  });

  it("should Execute a Tool Call Using OpenAI", async () => {
    const mem0OpenAI = createMem0({
      provider: "openai",
      apiKey: process.env.OPENAI_API_KEY,
      mem0Config: {
        user_id: userId,
      },
    });

    const result = await generateText({
      model: mem0OpenAI("gpt-4o"),
      tools: {
        weather: tool({
          description: "Get the weather in a location",
          inputSchema: z.object({
            location: z.string().describe("The location to get the weather for"),
          }),
          execute: async ({ location }) => ({
            location,
            temperature: 72 + Math.floor(Math.random() * 21) - 10,
          }),
        }),
      },
      prompt: "What is the temperature in the city that I live in?",
    });

    // Check if the response is valid
    expect(result).toHaveProperty('text');
    expect(typeof result.text).toBe("string");
    
    // For tool calls, we should have either text response or tool call results
    if (result.text && result.text.length > 0) {
      expect(result.text.length).toBeGreaterThan(0);
      // Check if the response mentions weather or temperature
      expect(result.text.toLowerCase()).toMatch(/(weather|temperature|mumbai)/);
    } else {
      // If text is empty, check if there are tool call results
      expect(result).toHaveProperty('toolResults');
      expect(Array.isArray(result.toolResults)).toBe(true);
      expect(result.toolResults.length).toBeGreaterThan(0);
    }
  });

  it("should Execute a Tool Call Using Anthropic", async () => {
    const mem0Anthropic = createMem0({
      provider: "anthropic",
      apiKey: process.env.ANTHROPIC_API_KEY,
      mem0Config: {
        user_id: userId,
      },
    });

    const result = await generateText({
      model: mem0Anthropic("claude-3-haiku-20240307"),
      tools: {
        weather: tool({
          description: "Get the weather in a location",
          inputSchema: z.object({
            location: z.string().describe("The location to get the weather for"),
          }),
          execute: async ({ location }) => ({
            location,
            temperature: 72 + Math.floor(Math.random() * 21) - 10,
          }),
        }),
      },
      prompt: "What is the temperature in the city that I live in?",
    });

    // Check if the response is valid
    expect(result).toHaveProperty('text');
    expect(typeof result.text).toBe("string");
    
    if (result.text && result.text.length > 0) {
      expect(result.text.length).toBeGreaterThan(0);
      // Check if the response mentions weather or temperature
      expect(result.text.toLowerCase()).toMatch(/(weather|temperature|mumbai)/);
    } else {
      // If text is empty, check if there are tool call results
      expect(result).toHaveProperty('toolResults');
      expect(Array.isArray(result.toolResults)).toBe(true);
      expect(result.toolResults.length).toBeGreaterThan(0);
    }
  });
});
