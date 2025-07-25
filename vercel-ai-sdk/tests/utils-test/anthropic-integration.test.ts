import dotenv from "dotenv";
dotenv.config();

import { retrieveMemories } from "../../src";
import { generateText } from "ai";
import { LanguageModelV2Prompt } from '@ai-sdk/provider';
import { testConfig } from "../../config/test-config";
import { createAnthropic } from "@ai-sdk/anthropic";

describe("ANTHROPIC Integration Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(30000);

  let anthropic: any;

  beforeEach(() => {
    anthropic = createAnthropic({
      apiKey: process.env.ANTHROPIC_API_KEY,
    });
  });

  it("should retrieve memories and generate text using ANTHROPIC provider", async () => {
    const messages: LanguageModelV2Prompt = [
      {
        role: "user",
        content: [
          { type: "text", text: "Suggest me a good car to buy." },
          { type: "text", text: " Write only the car name and it's color." },
        ],
      },
    ];

    // Retrieve memories based on previous messages
    const memories = await retrieveMemories(messages, { user_id: userId });
    
    const { text } = await generateText({
      // @ts-ignore
      model: anthropic("claude-3-haiku-20240307"),
      messages: messages,
      system: memories.length > 0 ? memories : "No Memories Found"
    });

    // Expect text to be a string
    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should generate text using ANTHROPIC provider with memories", async () => {
    const prompt = "Suggest me a good car to buy.";
    const memories = await retrieveMemories(prompt, { user_id: userId });

    const { text } = await generateText({
      // @ts-ignore
      model: anthropic("claude-3-haiku-20240307"),
      prompt: prompt,
      system: memories.length > 0 ? memories : "No Memories Found"
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });
});