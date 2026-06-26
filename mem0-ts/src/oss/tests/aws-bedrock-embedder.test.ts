/// <reference types="jest" />

const mockSend = jest.fn();
const mockBedrockRuntimeClient = jest.fn().mockImplementation(() => ({
  send: mockSend,
}));
const mockInvokeModelCommand = jest.fn().mockImplementation((input) => ({
  input,
}));

jest.mock("@aws-sdk/client-bedrock-runtime", () => ({
  BedrockRuntimeClient: mockBedrockRuntimeClient,
  InvokeModelCommand: mockInvokeModelCommand,
}));

import { AWSBedrockEmbedder } from "../src/embeddings/aws_bedrock";

function responseBody(body: Record<string, unknown>): Uint8Array {
  return new TextEncoder().encode(JSON.stringify(body));
}

describe("AWSBedrockEmbedder", () => {
  beforeEach(() => {
    mockSend.mockReset();
    mockBedrockRuntimeClient.mockClear();
    mockInvokeModelCommand.mockClear();
  });

  it("uses the AWS credential chain and default Titan model", async () => {
    mockSend.mockResolvedValue({
      body: responseBody({ embedding: [0.1, 0.2, 0.3] }),
    });

    const embedder = new AWSBedrockEmbedder({});
    const result = await embedder.embed("hello");

    expect(mockBedrockRuntimeClient).toHaveBeenCalledWith({
      region: "us-west-2",
    });
    expect(mockInvokeModelCommand).toHaveBeenCalledWith({
      modelId: "amazon.titan-embed-text-v1",
      contentType: "application/json",
      accept: "application/json",
      body: JSON.stringify({ inputText: "hello" }),
    });
    expect(result).toEqual([0.1, 0.2, 0.3]);
  });

  it("forwards explicit temporary credentials", async () => {
    mockSend.mockResolvedValue({
      body: responseBody({ embedding: [0.1] }),
    });

    const embedder = new AWSBedrockEmbedder({
      awsRegion: "eu-west-1",
      awsAccessKeyId: "access",
      awsSecretAccessKey: "secret",
      awsSessionToken: "session",
    });
    await embedder.embed("hello");

    expect(mockBedrockRuntimeClient).toHaveBeenCalledWith({
      region: "eu-west-1",
      credentials: {
        accessKeyId: "access",
        secretAccessKey: "secret",
        sessionToken: "session",
      },
    });
  });

  it("rejects incomplete explicit credentials", () => {
    expect(
      () =>
        new AWSBedrockEmbedder({
          awsAccessKeyId: "access",
        }),
    ).toThrow(
      "AWS Bedrock requires both awsAccessKeyId and awsSecretAccessKey",
    );
  });

  it("forwards dimensions only to Titan V2", async () => {
    mockSend.mockResolvedValue({
      body: responseBody({ embedding: [0.1, 0.2] }),
    });

    const embedder = new AWSBedrockEmbedder({
      model: "amazon.titan-embed-text-v2:0",
      embeddingDims: 512,
    });
    await embedder.embed("hello");

    const request = JSON.parse(
      mockInvokeModelCommand.mock.calls[0][0].body,
    ) as Record<string, unknown>;
    expect(request).toEqual({ inputText: "hello", dimensions: 512 });
  });

  it("does not forward dimensions to Titan V1", async () => {
    mockSend.mockResolvedValue({
      body: responseBody({ embedding: [0.1, 0.2] }),
    });

    const embedder = new AWSBedrockEmbedder({
      model: "amazon.titan-embed-text-v1",
      embeddingDims: 512,
    });
    await embedder.embed("hello");

    const request = JSON.parse(
      mockInvokeModelCommand.mock.calls[0][0].body,
    ) as Record<string, unknown>;
    expect(request).toEqual({ inputText: "hello" });
  });

  it("uses Cohere request and response shapes", async () => {
    mockSend.mockResolvedValue({
      body: responseBody({ embeddings: [[0.4, 0.5, 0.6]] }),
    });

    const embedder = new AWSBedrockEmbedder({
      model: "cohere.embed-english-v3",
    });
    const result = await embedder.embed("hello");

    const request = JSON.parse(
      mockInvokeModelCommand.mock.calls[0][0].body,
    ) as Record<string, unknown>;
    expect(request).toEqual({
      texts: ["hello"],
      input_type: "search_document",
    });
    expect(result).toEqual([0.4, 0.5, 0.6]);
  });

  it("batches Cohere inputs in one request", async () => {
    mockSend.mockResolvedValue({
      body: responseBody({
        embeddings: [
          [0.1, 0.2],
          [0.3, 0.4],
        ],
      }),
    });

    const embedder = new AWSBedrockEmbedder({
      model: "cohere.embed-multilingual-v3",
    });
    const result = await embedder.embedBatch(["hello", "world"]);

    expect(mockSend).toHaveBeenCalledTimes(1);
    const request = JSON.parse(
      mockInvokeModelCommand.mock.calls[0][0].body,
    ) as Record<string, unknown>;
    expect(request).toEqual({
      texts: ["hello", "world"],
      input_type: "search_document",
    });
    expect(result).toEqual([
      [0.1, 0.2],
      [0.3, 0.4],
    ]);
  });

  it("preserves input order for Titan batch embeddings", async () => {
    mockSend
      .mockResolvedValueOnce({
        body: responseBody({ embedding: [0.1] }),
      })
      .mockResolvedValueOnce({
        body: responseBody({ embedding: [0.2] }),
      });

    const embedder = new AWSBedrockEmbedder({});
    const result = await embedder.embedBatch(["first", "second"]);

    expect(mockSend).toHaveBeenCalledTimes(2);
    expect(result).toEqual([[0.1], [0.2]]);
  });

  it("throws a model-specific error for malformed responses", async () => {
    mockSend.mockResolvedValue({
      body: responseBody({}),
    });

    const embedder = new AWSBedrockEmbedder({
      model: "amazon.titan-embed-text-v2:0",
    });

    await expect(embedder.embed("hello")).rejects.toThrow(
      "AWS Bedrock model amazon.titan-embed-text-v2:0 returned no embedding",
    );
  });

  it("wraps Bedrock client failures with model context", async () => {
    mockSend.mockRejectedValue(new Error("AccessDeniedException"));

    const embedder = new AWSBedrockEmbedder({
      model: "amazon.titan-embed-text-v2:0",
    });

    await expect(embedder.embed("hello")).rejects.toThrow(
      "Error getting embedding from AWS Bedrock model amazon.titan-embed-text-v2:0: AccessDeniedException",
    );
  });
});
