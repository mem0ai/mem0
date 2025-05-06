import dotenv from "dotenv";
dotenv.config();

import { createMem0 } from "../../src";
import { generateText, LanguageModelV1Prompt } from "ai";
import { testConfig } from "../../config/test-config";

describe("GOOGLE MEM0 Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(30000);
  let mem0: any;

  beforeEach(() => {
    mem0 = createMem0({
      provider: "google",
      apiKey: process.env.GOOGLE_API_KEY,
      mem0Config: {
        user_id: userId
      }
    });
  });

  it("should retrieve memories and generate text using Mem0 Google provider", async () => {
    const messages: LanguageModelV1Prompt = [
      {
        role: "user",
        content: [
          { type: "text", text: "Suggest me a good car to buy." },
          { type: "text", text: " Write only the car name and it's color." },
        ],
      },
    ];
    
    const { text } = await generateText({
      model: mem0("gemini-1.5-pro-latest"),
      messages: messages
    });

    // Expect text to be a string
    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should generate text using google provider with memories", async () => {
    const prompt = "Suggest me a good car to buy.";

    const { text } = await generateText({
      model: mem0("gemini-1.5-pro-latest"),
      prompt: prompt
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should handle Google provider specific settings", async () => {
    const prompt = "What are the safety features of modern cars?";

    const { text } = await generateText({
      model: mem0("gemini-1.5-pro-latest", {
        safetySettings: [
          { category: "HARM_CATEGORY_DANGEROUS_CONTENT", threshold: "BLOCK_MEDIUM_AND_ABOVE" }
        ]
      }),
      prompt: prompt
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });
}); 