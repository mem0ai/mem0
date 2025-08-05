import dotenv from "dotenv";
dotenv.config();

import { createMem0, retrieveMemories } from "../../src";
import { generateText } from "ai";
import { LanguageModelV2Prompt } from '@ai-sdk/provider';
import { testConfig } from "../../config/test-config";
import { createGroq } from "@ai-sdk/groq";

describe("GROQ MEM0 Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(30000);

  let mem0: any;

  beforeEach(() => {
    mem0 = createMem0({
      provider: "groq",
      apiKey: process.env.GROQ_API_KEY,
      mem0Config: {
        user_id: userId
      }
    });
  });

  it("should retrieve memories and generate text using GROQ provider", async () => {
    const messages: LanguageModelV2Prompt = [
      {
        role: "user",
        content: [
          { type: "text", text: "Suggest me a good car to buy." },
          { type: "text", text: " Write only the car name and it's color." },
        ],
      },
    ];

    
    const { text } = await generateText({
      // @ts-ignore
      model: mem0("llama3-8b-8192"),
      messages: messages
    });

    // Expect text to be a string
    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should generate text using GROQ provider with memories", async () => {
    const prompt = "Suggest me a good car to buy.";

    const { text } = await generateText({
      // @ts-ignore
      model: mem0("llama3-8b-8192"),
      prompt: prompt
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });
});