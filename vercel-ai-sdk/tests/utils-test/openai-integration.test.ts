import dotenv from "dotenv";
dotenv.config();

import { retrieveMemories } from "../../src";
import { generateText, LanguageModelV1Prompt } from "ai";
import { testConfig } from "../../config/test-config";
import { createOpenAI } from "@ai-sdk/openai";

describe("OPENAI Integration Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(30000);
  let openai: any;

  beforeEach(() => {
    openai = createOpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });
  });

  it("should retrieve memories and generate text using OpenAI provider", async () => {
    const messages: LanguageModelV1Prompt = [
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
      model: openai("gpt-4-turbo"),
      messages: messages,
      system: memories,
    });

    // Expect text to be a string
    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should generate text using openai provider with memories", async () => {
    const prompt = "Suggest me a good car to buy.";
    const memories = await retrieveMemories(prompt, { user_id: userId });

    const { text } = await generateText({
      model: openai("gpt-4-turbo"),
      prompt: prompt,
      system: memories
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });
});