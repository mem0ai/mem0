/// <reference types="jest" />
import { Memory } from "../src";

jest.setTimeout(30000);

describe("Custom prompt JSON requirement (#3559)", () => {
  let llmGenerateResponse: jest.Mock;
  let embedderEmbed: jest.Mock;

  function createMemoryWithCustomPrompt(customPrompt: string): Memory {
    const memory = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: {
          apiKey: "test-key",
          model: "text-embedding-3-small",
        },
      },
      vectorStore: {
        provider: "memory",
        config: {
          collectionName: "test-memories",
          dimension: 1536,
        },
      },
      llm: {
        provider: "openai",
        config: {
          apiKey: "test-key",
          model: "gpt-4-turbo-preview",
        },
      },
      customPrompt,
      disableHistory: true,
    });

    llmGenerateResponse = jest.fn();
    embedderEmbed = jest.fn().mockResolvedValue(new Array(1536).fill(0));

    llmGenerateResponse
      .mockResolvedValueOnce(JSON.stringify({ facts: ["Test fact"] }))
      .mockResolvedValueOnce(
        JSON.stringify({
          memory: [{ id: "0", text: "Test fact", event: "ADD" }],
        }),
      );

    (memory as any).llm = {
      generateResponse: llmGenerateResponse,
      generateChat: jest.fn(),
    };
    (memory as any).embedder = { embed: embedderEmbed };

    return memory;
  }

  it("should include 'json' in user message when custom prompt lacks json", async () => {
    const memory = createMemoryWithCustomPrompt(
      "You are an assistant that extracts user preferences.",
    );

    await memory.add("I like pizza", { userId: "test-user" });

    expect(llmGenerateResponse).toHaveBeenCalled();
    const [messages] = llmGenerateResponse.mock.calls[0];
    const combined = messages.map((m: any) => m.content).join(" ");
    expect(combined.toLowerCase()).toContain("json");
  });

  it("should include 'json' in user message even when custom prompt contains json", async () => {
    const memory = createMemoryWithCustomPrompt(
      "Extract facts and return as json.",
    );

    await memory.add("I like pizza", { userId: "test-user" });

    expect(llmGenerateResponse).toHaveBeenCalled();
    const [messages] = llmGenerateResponse.mock.calls[0];
    const userMessage = messages.find((m: any) => m.role === "user");
    expect(userMessage.content.toLowerCase()).toContain("json");
  });

  it("should not modify prompts when no custom prompt is set", async () => {
    const memory = new Memory({
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: { apiKey: "test-key", model: "text-embedding-3-small" },
      },
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test-memories", dimension: 1536 },
      },
      llm: {
        provider: "openai",
        config: { apiKey: "test-key", model: "gpt-4-turbo-preview" },
      },
      disableHistory: true,
    });

    const mockGenerate = jest.fn();
    const mockEmbed = jest.fn().mockResolvedValue(new Array(1536).fill(0));

    mockGenerate
      .mockResolvedValueOnce(JSON.stringify({ facts: ["Test fact"] }))
      .mockResolvedValueOnce(
        JSON.stringify({
          memory: [{ id: "0", text: "Test fact", event: "ADD" }],
        }),
      );

    (memory as any).llm = {
      generateResponse: mockGenerate,
      generateChat: jest.fn(),
    };
    (memory as any).embedder = { embed: mockEmbed };

    await memory.add("I like pizza", { userId: "test-user" });

    expect(mockGenerate).toHaveBeenCalled();
    const [messages] = mockGenerate.mock.calls[0];
    const combined = messages.map((m: any) => m.content).join(" ");
    expect(combined.toLowerCase()).toContain("json");
  });
});
