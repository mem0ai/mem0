import { generateText, streamText } from "ai";
import { testConfig } from "../config/test-config";

interface Provider {
  name: string;
  activeModel: string;
  apiKey: string | undefined;
}

describe.each(testConfig.providers)('TEXT/STREAM PROPERTIES: Tests with model %s', (provider: Provider) => {
  const { userId } = testConfig;
  let mem0: ReturnType<typeof testConfig.createTestClient>;
  jest.setTimeout(50000);

  beforeEach(() => {
    mem0 = testConfig.createTestClient(provider);
  });

  it("should stream text with onChunk handler", async () => {
    const chunkTexts: string[] = [];
    const { textStream } = streamText({
      model: mem0(provider.activeModel, {
        user_id: userId, // Use the uniform userId
      }),
      prompt: "Write only the name of the car I prefer and its color.",
    });

    // Wait for the stream to complete
    for await (const _ of textStream) {
      chunkTexts.push(_);
    }

    // Ensure chunks are collected
    expect(chunkTexts.length).toBeGreaterThan(0);
    expect(chunkTexts.every((text) => typeof text === "string" || typeof text === "object")).toBe(true);
  });

  it("should call onFinish handler without throwing an error", async () => {
    streamText({
      model: mem0(provider.activeModel, {
        user_id: userId, // Use the uniform userId
      }),
      prompt: "Write only the name of the car I prefer and its color.",
    });
  });

  it("should generate fullStream with expected usage", async () => {
    const {
      text, // combined text
      usage, // combined usage of all steps
    } = await generateText({
      model: mem0.completion(provider.activeModel, {
        user_id: userId,
      }), // Ensure the model name is correct
      prompt:
        "Suggest me some good cars to buy. Each response MUST HAVE at least 200 words.",
    });

    // Ensure text is a string
    expect(typeof text).toBe("string");

    // Check usage
    expect(usage.inputTokens).toBeGreaterThanOrEqual(10);
    expect(usage.inputTokens).toBeLessThanOrEqual(500);
    expect(usage.outputTokens).toBeGreaterThanOrEqual(10);
    expect(usage.totalTokens).toBeGreaterThan(10);
  });
});
