import dotenv from "dotenv";
dotenv.config();

import { createMem0 } from "../../src";
import { generateText, LanguageModelV1Prompt } from "ai";
import { testConfig } from "../../config/test-config";

describe("GOOGLE MEM0 Tests", () => {
  const { userId } = testConfig;
  jest.setTimeout(50000);
  
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

  it("should retrieve memories and generate text using Google provider", async () => {
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
      // @ts-ignore
      model: mem0("gemini-2.5-pro-preview-05-06"),
      messages: messages
    });

    // Expect text to be a string
    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });

  it("should generate text using Google provider with memories", async () => {
    const prompt = "Suggest me a good car to buy.";

    const { text } = await generateText({
      // @ts-ignore
      model: mem0("gemini-2.5-pro-preview-05-06"),
      prompt: prompt
    });

    expect(typeof text).toBe('string');
    expect(text.length).toBeGreaterThan(0);
  });
}); 