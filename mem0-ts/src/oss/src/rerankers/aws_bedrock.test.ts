/**
 * Fake BedrockAgentRuntimeClient capturing the RerankCommand input and
 * returning a scripted response — exercises request shaping + response
 * parsing without the AWS SDK or live credentials.
 */
class FakeBedrockAgentRuntimeClient {
  public lastInput: any = null;
  public response: any;
  constructor(response: any) {
    this.response = response;
  }
  async send(command: any) {
    this.lastInput = command?.input ?? command;
    return this.response;
  }
}

// The provider loads the AWS SDK on first use via dynamic import(). Mock the
// module so it resolves and RerankCommand simply wraps its input.
jest.mock(
  "@aws-sdk/client-bedrock-agent-runtime",
  () => ({
    BedrockAgentRuntimeClient: class {
      constructor(public config: any) {}
    },
    RerankCommand: class {
      input: any;
      constructor(input: any) {
        this.input = input;
      }
    },
  }),
  { virtual: true },
);

import { AWSBedrockReranker } from "./aws_bedrock";

function makeReranker(
  client: FakeBedrockAgentRuntimeClient,
  overrides: any = {},
) {
  return new AWSBedrockReranker({ client, ...overrides });
}

describe("AWSBedrockReranker", () => {
  it("defaults to the cohere.rerank-v3-5:0 model and us-west-2 region", async () => {
    const client = new FakeBedrockAgentRuntimeClient({ results: [] });
    const reranker = makeReranker(client);

    await reranker.rerank("q", ["a"]);

    expect(
      client.lastInput.rerankingConfiguration.bedrockRerankingConfiguration
        .modelConfiguration.modelArn,
    ).toBe("arn:aws:bedrock:us-west-2::foundation-model/cohere.rerank-v3-5:0");
  });

  it("expands a short model id to a region-scoped foundation-model ARN", async () => {
    const client = new FakeBedrockAgentRuntimeClient({ results: [] });
    const reranker = makeReranker(client, {
      model: "amazon.rerank-v1:0",
      awsRegion: "eu-central-1",
    });

    await reranker.rerank("q", ["a"]);

    expect(
      client.lastInput.rerankingConfiguration.bedrockRerankingConfiguration
        .modelConfiguration.modelArn,
    ).toBe("arn:aws:bedrock:eu-central-1::foundation-model/amazon.rerank-v1:0");
  });

  it("passes a full ARN through unchanged", async () => {
    const arn =
      "arn:aws:bedrock:us-east-1::foundation-model/cohere.rerank-v3-5:0";
    const client = new FakeBedrockAgentRuntimeClient({ results: [] });
    const reranker = makeReranker(client, {
      model: arn,
      awsRegion: "us-west-2",
    });

    await reranker.rerank("q", ["a"]);

    expect(
      client.lastInput.rerankingConfiguration.bedrockRerankingConfiguration
        .modelConfiguration.modelArn,
    ).toBe(arn);
  });

  it("sends the query and documents in the Bedrock Rerank request shape", async () => {
    const client = new FakeBedrockAgentRuntimeClient({ results: [] });
    const reranker = makeReranker(client, { topK: 3 });

    await reranker.rerank("what does the user do", ["alpha", "beta"]);

    expect(client.lastInput.queries).toEqual([
      { textQuery: { text: "what does the user do" }, type: "TEXT" },
    ]);
    expect(client.lastInput.sources).toEqual([
      {
        inlineDocumentSource: { textDocument: { text: "alpha" }, type: "TEXT" },
        type: "INLINE",
      },
      {
        inlineDocumentSource: { textDocument: { text: "beta" }, type: "TEXT" },
        type: "INLINE",
      },
    ]);
    expect(
      client.lastInput.rerankingConfiguration.bedrockRerankingConfiguration
        .numberOfResults,
    ).toBe(3);
  });

  it("defaults numberOfResults to documents.length when neither the call nor config sets topK", async () => {
    const client = new FakeBedrockAgentRuntimeClient({ results: [] });
    const reranker = makeReranker(client);

    await reranker.rerank("q", ["a", "b", "c"]);

    expect(
      client.lastInput.rerankingConfiguration.bedrockRerankingConfiguration
        .numberOfResults,
    ).toBe(3);
  });

  it("returns Bedrock's ranked results as {index, rerankScore}", async () => {
    const client = new FakeBedrockAgentRuntimeClient({
      results: [
        { index: 2, relevanceScore: 0.9 },
        { index: 0, relevanceScore: 0.31 },
      ],
    });
    const reranker = makeReranker(client);

    const results = await reranker.rerank("q", ["x", "y", "z"]);

    expect(results).toEqual([
      { index: 2, rerankScore: 0.9 },
      { index: 0, rerankScore: 0.31 },
    ]);
  });

  it("returns an empty array without calling Bedrock when there are no documents", async () => {
    const client = new FakeBedrockAgentRuntimeClient({ results: [] });
    const reranker = makeReranker(client);

    const results = await reranker.rerank("q", []);

    expect(results).toEqual([]);
    expect(client.lastInput).toBeNull();
  });

  it("falls back to the original order with rerankScore 0.0 when the Bedrock call fails", async () => {
    const client = new FakeBedrockAgentRuntimeClient(null);
    client.send = async () => {
      throw new Error("bedrock is down");
    };
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const reranker = makeReranker(client);

    const results = await reranker.rerank("q", ["a", "b", "c"]);

    expect(results).toEqual([
      { index: 0, rerankScore: 0.0 },
      { index: 1, rerankScore: 0.0 },
      { index: 2, rerankScore: 0.0 },
    ]);
    expect(warnSpy).toHaveBeenCalled();

    warnSpy.mockRestore();
  });

  it("slices the fallback results by topK when the Bedrock call fails", async () => {
    const client = new FakeBedrockAgentRuntimeClient(null);
    client.send = async () => {
      throw new Error("bedrock is down");
    };
    jest.spyOn(console, "warn").mockImplementation(() => {});
    const reranker = makeReranker(client, { topK: 2 });

    const results = await reranker.rerank("q", ["a", "b", "c"]);

    expect(results).toEqual([
      { index: 0, rerankScore: 0.0 },
      { index: 1, rerankScore: 0.0 },
    ]);

    (console.warn as jest.Mock).mockRestore();
  });

  it("passes explicit AWS credentials through to the client config", async () => {
    let capturedConfig: any = null;

    jest.resetModules();
    jest.doMock(
      "@aws-sdk/client-bedrock-agent-runtime",
      () => ({
        BedrockAgentRuntimeClient: class {
          constructor(config: any) {
            capturedConfig = config;
          }
        },
        RerankCommand: class {
          input: any;
          constructor(input: any) {
            this.input = input;
          }
        },
      }),
      { virtual: true },
    );

    const { AWSBedrockReranker: FreshReranker } = await import("./aws_bedrock");
    const reranker = new FreshReranker({
      awsRegion: "ap-southeast-1",
      awsAccessKeyId: "AKIA_TEST",
      awsSecretAccessKey: "SECRET_TEST",
      awsSessionToken: "SESSION_TOKEN_TEST",
    });

    await reranker.rerank("q", []);
    // rerank() with no documents short-circuits before constructing the
    // client, so force construction directly to inspect the config.
    // @ts-expect-error accessing a private method for the test
    await reranker.getClient();

    expect(capturedConfig).toEqual({
      region: "ap-southeast-1",
      credentials: {
        accessKeyId: "AKIA_TEST",
        secretAccessKey: "SECRET_TEST",
        sessionToken: "SESSION_TOKEN_TEST",
      },
    });
  });
});
