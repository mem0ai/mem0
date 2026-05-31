import dotenv from "dotenv";
dotenv.config();

import { retrieveMemories } from "../../src";
import { generateText } from "ai";
import { LanguageModelV2Prompt } from '@ai-sdk/provider';
import { testConfig } from "../../config/test-config";
import { createGoogleGenerativeAI } from "@ai-sdk/google";

describe("GOOGLE Integration Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(30000);
  let google: any;

  beforeEach(() => {
    google = createGoogleGenerativeAI({
      apiKey: process.env.GOOGLE_API_KEY,
    });
  });

  it("should retrieve memories and generate text using Google provider", async () => {
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
      model: google("gemini-1.5-flash"),
      messages: messages,
      system: memories,
    });

    // Expect text to be a string
    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should generate text using Google provider with memories", async () => {
    const prompt = "Suggest me a good car to buy.";
    const memories = await retrieveMemories(prompt, { user_id: userId });

    const { text } = await generateText({
      model: google("gemini-1.5-flash"),
      prompt: prompt,
      system: memories
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });
}); 