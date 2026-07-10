import { AWSBedrockLLM } from "../llms/aws_bedrock";
import { LLMFactory } from "../utils/factory";

const sendMock = jest.fn();
const clientCtor = jest.fn();
const converseCtor = jest.fn().mockImplementation((input) => ({ input }));

jest.mock("@aws-sdk/client-bedrock-runtime", () => ({
  BedrockRuntimeClient: jest.fn().mockImplementation((args) => {
    clientCtor(args);
    return { send: sendMock };
  }),
  ConverseCommand: jest.fn().mockImplementation((input) => converseCtor(input)),
}));

function mockText(text: string) {
  sendMock.mockResolvedValue({
    output: { message: { content: [{ text }] } },
  });
}

describe("AWSBedrockLLM", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.AWS_REGION;
    delete process.env.AWS_DEFAULT_REGION;
    delete process.env.AWS_ACCESS_KEY_ID;
    delete process.env.AWS_SECRET_ACCESS_KEY;
    mockText("hello");
  });

  it("registers the aws_bedrock and bedrock providers with LLMFactory", () => {
    expect(LLMFactory.create("aws_bedrock", {})).toBeInstanceOf(AWSBedrockLLM);
    expect(LLMFactory.create("bedrock", {})).toBeInstanceOf(AWSBedrockLLM);
  });

  it("does not import the AWS SDK at construction time", () => {
    // Constructing must not instantiate the client (lazy loading), so users
    // without the SDK installed can still import the module.
    new AWSBedrockLLM({ awsRegion: "us-east-1" });
    expect(clientCtor).not.toHaveBeenCalled();
  });

  it("returns text and passes system + inferenceConfig to Converse", async () => {
    const llm = new AWSBedrockLLM({
      awsRegion: "us-west-2",
      model: "anthropic.claude-3-5-sonnet-20240620-v1:0",
    });

    const result = await llm.generateResponse([
      { role: "system", content: "be terse" },
      { role: "user", content: "Hi" },
    ]);

    expect(result).toBe("hello");
    expect(clientCtor).toHaveBeenCalledWith({ region: "us-west-2" });

    const input = converseCtor.mock.calls[0][0];
    expect(input.modelId).toBe("anthropic.claude-3-5-sonnet-20240620-v1:0");
    expect(input.system).toEqual([{ text: "be terse" }]);
    expect(input.messages).toEqual([
      { role: "user", content: [{ text: "Hi" }] },
    ]);
    // Anthropic must not receive topP alongside temperature.
    expect(input.inferenceConfig).toEqual({
      maxTokens: 2000,
      temperature: 0.1,
    });
  });

  it("keeps topP for non-anthropic providers", async () => {
    const llm = new AWSBedrockLLM({
      awsRegion: "us-west-2",
      model: "meta.llama3-70b-instruct-v1:0",
      topP: 0.9,
    });

    await llm.generateResponse([{ role: "user", content: "Hi" }]);

    const input = converseCtor.mock.calls[0][0];
    expect(input.inferenceConfig.topP).toBe(0.9);
  });

  it("maps tool definitions and toolUse responses to toolCalls", async () => {
    sendMock.mockResolvedValue({
      output: {
        message: {
          content: [
            { text: "calling" },
            {
              toolUse: {
                name: "add_memory",
                input: { data: "likes coffee" },
              },
            },
          ],
        },
      },
    });

    const llm = new AWSBedrockLLM({ awsRegion: "us-west-2" });
    const tools = [
      {
        type: "function",
        function: {
          name: "add_memory",
          description: "store a memory",
          parameters: { type: "object", properties: {} },
        },
      },
    ];

    const result = await llm.generateResponse(
      [{ role: "user", content: "remember I like coffee" }],
      undefined,
      tools,
    );

    const input = converseCtor.mock.calls[0][0];
    expect(input.toolConfig.tools[0].toolSpec.name).toBe("add_memory");
    expect(result).toEqual({
      content: "calling",
      role: "assistant",
      toolCalls: [
        {
          name: "add_memory",
          arguments: JSON.stringify({ data: "likes coffee" }),
        },
      ],
    });
  });

  it("drops tools for providers that do not support the tool-use API", async () => {
    const llm = new AWSBedrockLLM({
      awsRegion: "us-west-2",
      model: "meta.llama3-70b-instruct-v1:0",
    });
    const tools = [
      {
        type: "function",
        function: {
          name: "add_memory",
          description: "store a memory",
          parameters: { type: "object", properties: {} },
        },
      },
    ];

    const result = await llm.generateResponse(
      [{ role: "user", content: "Hi" }],
      undefined,
      tools,
    );

    // No toolConfig is sent for unsupported families; the plain text response
    // is returned instead of a toolCalls payload.
    const input = converseCtor.mock.calls[0][0];
    expect(input.toolConfig).toBeUndefined();
    expect(result).toBe("hello");
  });

  it("keeps tools for supported providers", async () => {
    const llm = new AWSBedrockLLM({
      awsRegion: "us-west-2",
      model: "cohere.command-r-plus-v1:0",
    });
    const tools = [
      {
        type: "function",
        function: {
          name: "add_memory",
          description: "store a memory",
          parameters: { type: "object", properties: {} },
        },
      },
    ];

    await llm.generateResponse(
      [{ role: "user", content: "Hi" }],
      undefined,
      tools,
    );

    const input = converseCtor.mock.calls[0][0];
    expect(input.toolConfig.tools[0].toolSpec.name).toBe("add_memory");
  });

  it("resolves the provider for region-prefixed model ids", () => {
    // A cross-region inference profile id still resolves to the underlying
    // provider family, so tool support is gated correctly.
    expect(
      () =>
        new AWSBedrockLLM({
          model: "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
        }),
    ).not.toThrow();
  });

  it("throws on an unknown provider in the model id", () => {
    expect(() => new AWSBedrockLLM({ model: "acme.super-model-v1:0" })).toThrow(
      /Unknown AWS Bedrock provider/,
    );
  });

  it("reads region and credentials from the environment", async () => {
    process.env.AWS_REGION = "eu-central-1";
    process.env.AWS_ACCESS_KEY_ID = "AKIA_TEST";
    process.env.AWS_SECRET_ACCESS_KEY = "secret";

    const llm = new AWSBedrockLLM({});
    await llm.generateChat([{ role: "user", content: "Hi" }]);

    expect(clientCtor).toHaveBeenCalledWith({
      region: "eu-central-1",
      credentials: {
        accessKeyId: "AKIA_TEST",
        secretAccessKey: "secret",
        sessionToken: undefined,
      },
    });
  });
});
