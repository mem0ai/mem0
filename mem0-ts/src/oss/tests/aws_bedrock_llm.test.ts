/// <reference types="jest" />

const mockSend = jest.fn();

// Mock the AWS SDK module before importing the LLM
jest.mock(
  "@aws-sdk/client-bedrock-runtime",
  () => ({
    BedrockRuntimeClient: jest.fn().mockImplementation(() => ({
      send: mockSend,
    })),
    ConverseCommand: jest.fn().mockImplementation((input) => ({
      input,
      type: "ConverseCommand",
    })),
    InvokeModelCommand: jest.fn().mockImplementation((input) => ({
      input,
      type: "InvokeModelCommand",
    })),
  }),
  { virtual: true },
);

import { AWSBedrockLLM, AWSBedrockConfig } from "../src/llms/aws_bedrock";

describe("AWSBedrockLLM", () => {
  const defaultConfig: AWSBedrockConfig = {
    model: "anthropic.claude-3-sonnet-20240229-v1:0",
    region: "us-east-1",
    maxTokens: 2000,
    temperature: 0.5,
    topP: 0.9,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("constructor", () => {
    it("should create instance with valid config", () => {
      const llm = new AWSBedrockLLM(defaultConfig);
      expect(llm).toBeInstanceOf(AWSBedrockLLM);
    });

    it("should use default model if not provided", () => {
      const llm = new AWSBedrockLLM({ region: "us-east-1" });
      expect(llm).toBeInstanceOf(AWSBedrockLLM);
    });

    it("should configure credentials when provided", () => {
      const llm = new AWSBedrockLLM({
        ...defaultConfig,
        credentials: {
          accessKeyId: "test-key",
          secretAccessKey: "test-secret",
          sessionToken: "test-token",
        },
      });
      expect(llm).toBeInstanceOf(AWSBedrockLLM);
    });

    it("should throw error for unknown provider in model", () => {
      expect(() => {
        new AWSBedrockLLM({
          model: "unknown-provider.model-v1",
          region: "us-east-1",
        });
      }).toThrow("Unknown provider in model");
    });
  });

  describe("generateResponse - Anthropic (Converse API)", () => {
    it("should generate response for anthropic model", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Hello! How can I help you today?" }],
          },
        },
      });

      const llm = new AWSBedrockLLM(defaultConfig);
      const response = await llm.generateResponse([
        { role: "user", content: "Hello!" },
      ]);

      expect(response).toBe("Hello! How can I help you today?");
      expect(mockSend).toHaveBeenCalledTimes(1);

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("ConverseCommand");
      expect(command.input.modelId).toBe(
        "anthropic.claude-3-sonnet-20240229-v1:0",
      );
      expect(command.input.messages).toEqual([
        { role: "user", content: [{ text: "Hello!" }] },
      ]);
      expect(command.input.inferenceConfig).toEqual({
        maxTokens: 2000,
        temperature: 0.5,
        topP: 0.9,
      });
    });

    it("should handle system messages for anthropic", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "I am a helpful assistant." }],
          },
        },
      });

      const llm = new AWSBedrockLLM(defaultConfig);
      await llm.generateResponse([
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Who are you?" },
      ]);

      const command = mockSend.mock.calls[0][0];
      expect(command.input.system).toEqual([
        { text: "You are a helpful assistant." },
      ]);
      expect(command.input.messages).toEqual([
        { role: "user", content: [{ text: "Who are you?" }] },
      ]);
    });

    it("should handle tool calls in response", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [
              { text: "Let me search for that." },
              {
                toolUse: {
                  name: "search",
                  input: { query: "weather in NYC" },
                },
              },
            ],
          },
        },
      });

      const tools = [
        {
          type: "function" as const,
          function: {
            name: "search",
            description: "Search the web",
            parameters: {
              type: "object",
              properties: {
                query: { type: "string" },
              },
              required: ["query"],
            },
          },
        },
      ];

      const llm = new AWSBedrockLLM(defaultConfig);
      const response = await llm.generateResponse(
        [{ role: "user", content: "What's the weather in NYC?" }],
        undefined,
        tools,
      );

      expect(response).toEqual({
        content: "Let me search for that.",
        role: "assistant",
        toolCalls: [
          {
            name: "search",
            arguments: '{"query":"weather in NYC"}',
          },
        ],
      });

      const command = mockSend.mock.calls[0][0];
      expect(command.input.toolConfig).toEqual({
        tools: [
          {
            toolSpec: {
              name: "search",
              description: "Search the web",
              inputSchema: {
                json: {
                  type: "object",
                  properties: {
                    query: { type: "string" },
                  },
                  required: ["query"],
                },
              },
            },
          },
        ],
      });
    });

    it("should handle empty response", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [],
          },
        },
      });

      const llm = new AWSBedrockLLM(defaultConfig);
      const response = await llm.generateResponse([
        { role: "user", content: "Hello!" },
      ]);

      expect(response).toBe("");
    });
  });

  describe("generateResponse - Amazon (Converse API)", () => {
    it("should generate response for amazon nova model", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Response from Amazon Nova" }],
          },
        },
      });

      const llm = new AWSBedrockLLM({
        model: "amazon.nova-pro-v1:0",
        region: "us-east-1",
      });

      const response = await llm.generateResponse([
        { role: "user", content: "Hello from Amazon!" },
      ]);

      expect(response).toBe("Response from Amazon Nova");

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("ConverseCommand");
      expect(command.input.modelId).toBe("amazon.nova-pro-v1:0");
    });

    it("should generate response for amazon titan model", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Response from Amazon Titan" }],
          },
        },
      });

      const llm = new AWSBedrockLLM({
        model: "amazon.titan-text-express-v1",
        region: "us-east-1",
      });

      const response = await llm.generateResponse([
        { role: "user", content: "Hello!" },
      ]);

      expect(response).toBe("Response from Amazon Titan");
    });
  });

  describe("generateResponse - Meta (Converse API)", () => {
    it("should generate response for meta llama model", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Response from Llama" }],
          },
        },
      });

      const llm = new AWSBedrockLLM({
        model: "meta.llama3-70b-instruct-v1:0",
        region: "us-east-1",
      });

      const response = await llm.generateResponse([
        { role: "user", content: "Hello from Meta!" },
      ]);

      expect(response).toBe("Response from Llama");

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("ConverseCommand");
    });
  });

  describe("generateResponse - Mistral (Converse API)", () => {
    it("should generate response for mistral model", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Response from Mistral" }],
          },
        },
      });

      const llm = new AWSBedrockLLM({
        model: "mistral.mistral-7b-instruct-v0:2",
        region: "us-east-1",
      });

      const response = await llm.generateResponse([
        { role: "user", content: "Hello from Mistral!" },
      ]);

      expect(response).toBe("Response from Mistral");

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("ConverseCommand");
    });
  });

  describe("generateResponse - Cohere (Converse API)", () => {
    it("should generate response for cohere model", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Response from Cohere" }],
          },
        },
      });

      const llm = new AWSBedrockLLM({
        model: "cohere.command-text-v14",
        region: "us-east-1",
      });

      const response = await llm.generateResponse([
        { role: "user", content: "Hello from Cohere!" },
      ]);

      expect(response).toBe("Response from Cohere");

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("ConverseCommand");
    });
  });

  describe("generateResponse - AI21 (InvokeModel API)", () => {
    it("should generate response for ai21 model using invoke_model", async () => {
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({
            completions: [{ data: { text: "Response from AI21" } }],
          }),
        ),
      });

      const llm = new AWSBedrockLLM({
        model: "ai21.j2-ultra-v1",
        region: "us-east-1",
      });

      const response = await llm.generateResponse([
        { role: "user", content: "Hello from AI21!" },
      ]);

      expect(response).toBe("Response from AI21");

      const command = mockSend.mock.calls[0][0];
      expect(command.type).toBe("InvokeModelCommand");
      expect(command.input.modelId).toBe("ai21.j2-ultra-v1");
      expect(command.input.accept).toBe("application/json");
      expect(command.input.contentType).toBe("application/json");
    });
  });

  describe("generateChat", () => {
    it("should return LLMResponse format", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Chat response" }],
          },
        },
      });

      const llm = new AWSBedrockLLM(defaultConfig);
      const response = await llm.generateChat([
        { role: "user", content: "Hello!" },
      ]);

      expect(response).toEqual({
        content: "Chat response",
        role: "assistant",
      });
    });

    it("should handle tool calls in generateChat", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [
              {
                toolUse: {
                  name: "get_weather",
                  input: { location: "Paris" },
                },
              },
            ],
          },
        },
      });

      const llm = new AWSBedrockLLM(defaultConfig);
      const response = await llm.generateChat([
        { role: "user", content: "Weather in Paris?" },
      ]);

      // When generateChat returns an LLMResponse with toolCalls
      expect(response.role).toBe("assistant");
    });
  });

  describe("tool conversion", () => {
    it("should convert OpenAI tool format to Bedrock format", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Using tool..." }],
          },
        },
      });

      const tools = [
        {
          type: "function" as const,
          function: {
            name: "calculate",
            description: "Perform calculations",
            parameters: {
              type: "object",
              properties: {
                expression: { type: "string", description: "Math expression" },
                precision: { type: "number", description: "Decimal places" },
              },
              required: ["expression"],
            },
          },
        },
      ];

      const llm = new AWSBedrockLLM(defaultConfig);
      await llm.generateResponse(
        [{ role: "user", content: "Calculate 2+2" }],
        undefined,
        tools,
      );

      const command = mockSend.mock.calls[0][0];
      expect(command.input.toolConfig.tools).toEqual([
        {
          toolSpec: {
            name: "calculate",
            description: "Perform calculations",
            inputSchema: {
              json: {
                type: "object",
                properties: {
                  expression: {
                    type: "string",
                    description: "Math expression",
                  },
                  precision: { type: "number", description: "Decimal places" },
                },
                required: ["expression"],
              },
            },
          },
        },
      ]);
    });

    it("should handle tools without description", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Done" }],
          },
        },
      });

      const tools = [
        {
          type: "function" as const,
          function: {
            name: "simple_tool",
            parameters: {
              type: "object",
              properties: {},
            },
          },
        },
      ];

      const llm = new AWSBedrockLLM(defaultConfig);
      await llm.generateResponse(
        [{ role: "user", content: "Use tool" }],
        undefined,
        tools,
      );

      const command = mockSend.mock.calls[0][0];
      expect(command.input.toolConfig.tools[0].toolSpec.description).toBe("");
    });

    it("should handle tools without parameters", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Done" }],
          },
        },
      });

      const tools = [
        {
          type: "function" as const,
          function: {
            name: "no_params_tool",
            description: "A tool without explicit parameters",
          },
        },
      ];

      const llm = new AWSBedrockLLM(defaultConfig);
      await llm.generateResponse(
        [{ role: "user", content: "Use tool" }],
        undefined,
        tools,
      );

      const command = mockSend.mock.calls[0][0];
      expect(command.input.toolConfig.tools).toHaveLength(1);
      expect(command.input.toolConfig.tools[0].toolSpec.name).toBe(
        "no_params_tool",
      );
      expect(
        command.input.toolConfig.tools[0].toolSpec.inputSchema.json,
      ).toEqual({
        type: "object",
        properties: {},
      });
    });
  });

  describe("message formatting", () => {
    it("should handle MultiModalMessages content type", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "I see an image" }],
          },
        },
      });

      const llm = new AWSBedrockLLM(defaultConfig);
      await llm.generateResponse([
        {
          role: "user",
          content: {
            type: "image_url",
            image_url: { url: "https://example.com/image.png" },
          },
        },
      ]);

      const command = mockSend.mock.calls[0][0];
      expect(command.input.messages[0].content[0].text).toBe(
        "https://example.com/image.png",
      );
    });

    it("should handle assistant messages", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Continuing..." }],
          },
        },
      });

      const llm = new AWSBedrockLLM(defaultConfig);
      await llm.generateResponse([
        { role: "user", content: "Start" },
        { role: "assistant", content: "Middle" },
        { role: "user", content: "Continue" },
      ]);

      const command = mockSend.mock.calls[0][0];
      expect(command.input.messages).toHaveLength(3);
      expect(command.input.messages[1]).toEqual({
        role: "assistant",
        content: [{ text: "Middle" }],
      });
    });
  });

  describe("default configuration", () => {
    it("should use default values when not specified", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [{ text: "Response" }],
          },
        },
      });

      const llm = new AWSBedrockLLM({ region: "us-west-2" });
      await llm.generateResponse([{ role: "user", content: "Test" }]);

      const command = mockSend.mock.calls[0][0];
      expect(command.input.inferenceConfig).toEqual({
        maxTokens: 2000,
        temperature: 0.1,
        topP: 0.9,
      });
    });
  });

  describe("error handling", () => {
    it("should propagate errors from client", async () => {
      mockSend.mockRejectedValueOnce(new Error("AWS API Error"));

      const llm = new AWSBedrockLLM(defaultConfig);

      await expect(
        llm.generateResponse([{ role: "user", content: "Hello!" }]),
      ).rejects.toThrow("AWS API Error");
    });
  });

  describe("provider detection", () => {
    const providerModels = [
      { model: "anthropic.claude-v2", provider: "anthropic" },
      { model: "amazon.titan-text-express-v1", provider: "amazon" },
      { model: "meta.llama2-70b-chat-v1", provider: "meta" },
      { model: "mistral.mixtral-8x7b-instruct-v0:1", provider: "mistral" },
      { model: "cohere.command-text-v14", provider: "cohere" },
      { model: "ai21.j2-mid-v1", provider: "ai21" },
    ];

    providerModels.forEach(({ model, provider }) => {
      it(`should detect ${provider} provider from model: ${model}`, () => {
        const llm = new AWSBedrockLLM({ model, region: "us-east-1" });
        expect(llm).toBeInstanceOf(AWSBedrockLLM);
      });
    });
  });

  describe("multiple tool calls", () => {
    it("should handle multiple tool calls in a single response", async () => {
      mockSend.mockResolvedValueOnce({
        output: {
          message: {
            content: [
              { text: "I'll help with both." },
              {
                toolUse: {
                  name: "get_weather",
                  input: { location: "NYC" },
                },
              },
              {
                toolUse: {
                  name: "get_weather",
                  input: { location: "LA" },
                },
              },
            ],
          },
        },
      });

      const tools = [
        {
          type: "function" as const,
          function: {
            name: "get_weather",
            description: "Get weather for a location",
            parameters: {
              type: "object",
              properties: {
                location: { type: "string" },
              },
              required: ["location"],
            },
          },
        },
      ];

      const llm = new AWSBedrockLLM(defaultConfig);
      const response = await llm.generateResponse(
        [{ role: "user", content: "Weather in NYC and LA?" }],
        undefined,
        tools,
      );

      expect(response).toEqual({
        content: "I'll help with both.",
        role: "assistant",
        toolCalls: [
          { name: "get_weather", arguments: '{"location":"NYC"}' },
          { name: "get_weather", arguments: '{"location":"LA"}' },
        ],
      });
    });
  });
});
