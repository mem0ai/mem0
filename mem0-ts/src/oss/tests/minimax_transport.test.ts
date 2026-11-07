/// <reference types="jest" />

// Inject only the HTTP transport: both SDKs still serialize real requests.
const mockFetch = jest.fn();
jest.mock("openai", () => {
  const { default: ActualOpenAI } = jest.requireActual("openai");
  return class extends ActualOpenAI {
    constructor(options: any) {
      super({ ...options, fetch: mockFetch });
    }
  };
});
jest.mock("@anthropic-ai/sdk", () => {
  const { default: ActualAnthropic } = jest.requireActual("@anthropic-ai/sdk");
  return {
    __esModule: true,
    default: class extends ActualAnthropic {
      constructor(options: any) {
        super({ ...options, fetch: mockFetch });
      }
    },
  };
});

import { MiniMaxLLM } from "../src/llms/minimax";
import { AnthropicLLM } from "../src/llms/anthropic";

const messages = [
  { role: "system", content: "Remember facts." },
  { role: "user", content: "Hello" },
];

beforeEach(() => {
  mockFetch.mockReset();
  delete process.env.MINIMAX_API_BASE;
  mockFetch.mockResolvedValue(
    new Response(
      JSON.stringify({
        id: "chat-test",
        object: "chat.completion",
        created: 0,
        choices: [
          {
            index: 0,
            message: { role: "assistant", content: "OK" },
            finish_reason: "stop",
          },
        ],
      }),
      { headers: { "content-type": "application/json" } },
    ),
  );
});

describe.each([
  undefined,
  "https://api.minimaxi.com/v1",
  "https://custom.example/v1",
])("MiniMax endpoint %s", (baseURL) => {
  test.each([
    undefined,
    "MiniMax-M3.1-Flash",
    "MiniMax-M3",
    "MiniMax-M2.7",
    "saved-custom-model",
  ])("serializes model %s", async (model) => {
    const llm = new MiniMaxLLM({ apiKey: "test-key", baseURL, model });
    const tools = [
      {
        type: "function",
        function: { name: "remember", parameters: { type: "object" } },
      },
    ];
    expect(
      await llm.generateResponse(messages, { type: "json_object" }, tools),
    ).toBe("OK");
    const [url, init] = mockFetch.mock.calls[0];
    expect(String(url)).toBe(
      `${baseURL || "https://api.minimax.io/v1"}/chat/completions`,
    );
    expect(JSON.parse(init.body)).toEqual({
      model: model || "MiniMax-M3.1-Flash",
      messages,
      tools,
      tool_choice: "auto",
      response_format: { type: "json_object" },
    });
  });

  test("generateChat uses the same default", async () => {
    const llm = new MiniMaxLLM({ apiKey: "test-key", baseURL });
    expect(await llm.generateChat(messages)).toEqual({
      content: "OK",
      role: "assistant",
    });
    expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
      model: "MiniMax-M3.1-Flash",
      messages,
    });
  });
});

describe.each(["api.minimax.io", "api.minimaxi.com"])(
  "MiniMax Messages endpoint %s",
  (host) => {
    test.each(["MiniMax-M3.1-Flash", "MiniMax-M3"])(
      "serializes explicit model %s",
      async (model) => {
        mockFetch.mockResolvedValue(
          new Response(
            JSON.stringify({
              id: "msg-test",
              type: "message",
              role: "assistant",
              model,
              content: [{ type: "text", text: "OK" }],
              stop_reason: "end_turn",
              usage: { input_tokens: 1, output_tokens: 1 },
            }),
            { headers: { "content-type": "application/json" } },
          ),
        );
        const llm = new AnthropicLLM({
          apiKey: "test-key",
          model,
          baseURL: `https://${host}/anthropic`,
        });
        expect(await llm.generateResponse(messages)).toBe("OK");
        const [url, init] = mockFetch.mock.calls[0];
        expect(String(url)).toBe(`https://${host}/anthropic/v1/messages`);
        expect(JSON.parse(init.body)).toEqual({
          model,
          system: messages[0].content,
          messages: [messages[1]],
          max_tokens: 2000,
          temperature: 0.1,
        });
      },
    );
  },
);
