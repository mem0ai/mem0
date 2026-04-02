import { DeepSeekLLM } from "../src/llms/deepseek";

// Mock the openai module
jest.mock("openai", () => {
  const mockCreate = jest.fn();
  return {
    __esModule: true,
    default: jest.fn().mockImplementation(() => ({
      chat: {
        completions: {
          create: mockCreate,
        },
      },
    })),
    mockCreate,
  };
});

// Helper to get mockCreate from the mocked module
function getMockCreate() {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const OpenAI = require("openai");
  return OpenAI.mockCreate;
}

describe("DeepSeekLLM", () => {
  const apiKey = "test-deepseek-key";

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("constructor", () => {
    it("should initialize with provided API key and default model", () => {
      const llm = new DeepSeekLLM({ apiKey });
      expect(llm).toBeInstanceOf(DeepSeekLLM);
    });

    it("should use DEEPSEEK_API_KEY env var if no apiKey in config", () => {
      process.env.DEEPSEEK_API_KEY = "env-api-key";
      const llm = new DeepSeekLLM({});
      expect(llm).toBeInstanceOf(DeepSeekLLM);
      delete process.env.DEEPSEEK_API_KEY;
    });

    it("should throw if no API key is provided", () => {
      delete process.env.DEEPSEEK_API_KEY;
      expect(() => new DeepSeekLLM({})).toThrow("DeepSeek API key is required");
    });

    it("should accept a custom baseURL", () => {
      const llm = new DeepSeekLLM({
        apiKey,
        baseURL: "https://custom.deepseek.example.com/v1",
      });
      expect(llm).toBeInstanceOf(DeepSeekLLM);
    });
  });

  describe("generateResponse", () => {
    it("should return text content for a plain response", async () => {
      const mockCreate = getMockCreate();
      mockCreate.mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: "assistant",
              content: "Hello from DeepSeek!",
              tool_calls: null,
            },
          },
        ],
      });

      const llm = new DeepSeekLLM({ apiKey });
      const result = await llm.generateResponse([
        { role: "user", content: "Hi" },
      ]);
      expect(result).toBe("Hello from DeepSeek!");
    });

    it("should return LLMResponse with toolCalls when tool_calls present", async () => {
      const mockCreate = getMockCreate();
      mockCreate.mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: "assistant",
              content: null,
              tool_calls: [
                {
                  function: {
                    name: "add_memory",
                    arguments: '{"memory": "test"}',
                  },
                },
              ],
            },
          },
        ],
      });

      const llm = new DeepSeekLLM({ apiKey });
      const result = await llm.generateResponse(
        [{ role: "user", content: "Remember this" }],
        undefined,
        [{ type: "function", function: { name: "add_memory" } }],
      );
      expect(result).toEqual({
        content: "",
        role: "assistant",
        toolCalls: [{ name: "add_memory", arguments: '{"memory": "test"}' }],
      });
    });

    it("should pass responseFormat to the API", async () => {
      const mockCreate = getMockCreate();
      mockCreate.mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: "assistant",
              content: '{"key":"val"}',
              tool_calls: null,
            },
          },
        ],
      });

      const llm = new DeepSeekLLM({ apiKey, model: "deepseek-reasoner" });
      await llm.generateResponse([{ role: "user", content: "Return JSON" }], {
        type: "json_object",
      });
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ response_format: { type: "json_object" } }),
      );
    });
  });

  describe("generateChat", () => {
    it("should return LLMResponse with content and role", async () => {
      const mockCreate = getMockCreate();
      mockCreate.mockResolvedValueOnce({
        choices: [
          {
            message: {
              role: "assistant",
              content: "Chat reply",
            },
          },
        ],
      });

      const llm = new DeepSeekLLM({ apiKey });
      const result = await llm.generateChat([
        { role: "user", content: "Chat message" },
      ]);
      expect(result).toEqual({ content: "Chat reply", role: "assistant" });
    });
  });
});
