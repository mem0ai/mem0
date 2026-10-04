import type { InvokeModelCommand } from "@aws-sdk/client-bedrock-runtime";
import { AWSBedrockEmbedder } from "../src/embeddings/aws_bedrock";
import type { Embedder } from "../src/embeddings/base";
import { EmbedderFactory } from "../src/utils/factory";

/**
 * Only the network boundary is faked: `BedrockRuntimeClient.send` never leaves
 * the process. `InvokeModelCommand` stays the real class from the AWS SDK, so
 * every assertion below runs against the exact payload Bedrock would receive.
 */
const mockSend = jest.fn();
const mockClientConfigs: any[] = [];
const mockClientConstructor = jest
  .fn()
  .mockImplementation((config: unknown) => {
    mockClientConfigs.push(config);
    return { send: mockSend };
  });

jest.mock("@aws-sdk/client-bedrock-runtime", () => {
  const actual = jest.requireActual("@aws-sdk/client-bedrock-runtime");
  return {
    ...actual,
    BedrockRuntimeClient: mockClientConstructor,
  };
});

const encode = (payload: unknown) => ({
  body: new TextEncoder().encode(JSON.stringify(payload)),
});

const titanReply = (embedding: number[]) =>
  encode({ embedding, inputTextTokenCount: embedding.length });

const cohereReply = (embeddings: number[][]) =>
  encode({ embeddings, id: "req-1", response_type: "embeddings_floats" });

const commandAt = (index: number): InvokeModelCommand =>
  mockSend.mock.calls[index][0];

const requestBodyAt = (index: number) =>
  JSON.parse(new TextDecoder().decode(commandAt(index).input.body));

describe("AWSBedrockEmbedder", () => {
  const savedEnv = { ...process.env };

  beforeEach(() => {
    jest.clearAllMocks();
    mockClientConfigs.length = 0;
    delete process.env.AWS_REGION;
  });

  afterAll(() => {
    process.env = savedEnv;
  });

  describe("Titan models", () => {
    it("sends inputText and returns the embedding vector", async () => {
      mockSend.mockResolvedValueOnce(titanReply([0.1, 0.2, 0.3]));
      const embedder = new AWSBedrockEmbedder({});

      const embedding = await embedder.embed("hello world");

      expect(embedding).toEqual([0.1, 0.2, 0.3]);
      expect(mockSend).toHaveBeenCalledTimes(1);
      expect(commandAt(0).input.modelId).toBe("amazon.titan-embed-text-v1");
      expect(commandAt(0).input.contentType).toBe("application/json");
      expect(commandAt(0).input.accept).toBe("application/json");
      expect(requestBodyAt(0)).toEqual({ inputText: "hello world" });
    });

    it("forwards dimensions to Titan V2 when embeddingDims is set", async () => {
      mockSend.mockResolvedValueOnce(titanReply([0.1, 0.2]));
      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v2:0",
        embeddingDims: 512,
      });

      await embedder.embed("hello");

      expect(requestBodyAt(0)).toEqual({ inputText: "hello", dimensions: 512 });
    });

    it("omits dimensions on Titan V1, which rejects the field", async () => {
      mockSend.mockResolvedValueOnce(titanReply([0.1, 0.2]));
      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        embeddingDims: 512,
      });

      await embedder.embed("hello");

      expect(requestBodyAt(0)).toEqual({ inputText: "hello" });
    });

    // F6: the old guard was `model.includes("v2")`, which would also match
    // any future/other Titan model whose id merely contains "v2" somewhere
    // (e.g. an image model), wrongly sending `dimensions` to a model that may
    // reject it. Only Titan Text Embeddings V2 should get the field.
    it("does not forward dimensions to a non-Titan-V2 model whose name merely contains v2", async () => {
      mockSend.mockResolvedValueOnce(titanReply([0.1, 0.2]));
      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-image-v2:0",
        embeddingDims: 512,
      });

      await embedder.embed("hello");

      expect(requestBodyAt(0)).toEqual({ inputText: "hello" });
    });

    it("embedBatch issues one request per text and preserves order", async () => {
      mockSend
        .mockResolvedValueOnce(titanReply([1, 1]))
        .mockResolvedValueOnce(titanReply([2, 2]));
      const embedder = new AWSBedrockEmbedder({});

      const embeddings = await embedder.embedBatch(["first", "second"]);

      expect(embeddings).toEqual([
        [1, 1],
        [2, 2],
      ]);
      expect(mockSend).toHaveBeenCalledTimes(2);
      expect(requestBodyAt(0)).toEqual({ inputText: "first" });
      expect(requestBodyAt(1)).toEqual({ inputText: "second" });
    });
  });

  describe("Cohere models", () => {
    it("sends texts with a search_document input type", async () => {
      mockSend.mockResolvedValueOnce(cohereReply([[0.4, 0.5]]));
      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      const embedding = await embedder.embed("hello");

      expect(embedding).toEqual([0.4, 0.5]);
      expect(requestBodyAt(0)).toEqual({
        texts: ["hello"],
        input_type: "search_document",
      });
    });

    it("embedBatch sends every text in a single request", async () => {
      mockSend.mockResolvedValueOnce(cohereReply([[1], [2], [3]]));
      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-multilingual-v3",
      });

      const embeddings = await embedder.embedBatch(["a", "b", "c"]);

      expect(embeddings).toEqual([[1], [2], [3]]);
      expect(mockSend).toHaveBeenCalledTimes(1);
      expect(requestBodyAt(0).texts).toEqual(["a", "b", "c"]);
    });

    it("embedBatch splits requests at Cohere's 96 text limit", async () => {
      const texts = Array.from({ length: 100 }, (_, i) => `text-${i}`);
      mockSend
        .mockResolvedValueOnce(
          cohereReply(texts.slice(0, 96).map((_, i) => [i])),
        )
        .mockResolvedValueOnce(cohereReply(texts.slice(96).map((_, i) => [i])));
      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      const embeddings = await embedder.embedBatch(texts);

      expect(embeddings).toHaveLength(100);
      expect(mockSend).toHaveBeenCalledTimes(2);
      expect(requestBodyAt(0).texts).toHaveLength(96);
      expect(requestBodyAt(1).texts).toEqual([
        "text-96",
        "text-97",
        "text-98",
        "text-99",
      ]);
    });
  });

  describe("Cohere Embed v4", () => {
    // F5: only Embed v4 understands embedding_types / output_dimension, and
    // (when embedding_types is requested) replies with a nested
    // `{ embeddings: { float: [...] } }` shape instead of v3's flat array.
    it("requests embedding_types and output_dimension for v4 models", async () => {
      mockSend.mockResolvedValueOnce(
        encode({ embeddings: { float: [[0.1, 0.2, 0.3]] } }),
      );
      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-v4:0",
        embeddingDims: 512,
      });

      const embedding = await embedder.embed("hello");

      expect(embedding).toEqual([0.1, 0.2, 0.3]);
      expect(requestBodyAt(0)).toEqual({
        texts: ["hello"],
        input_type: "search_document",
        embedding_types: ["float"],
        output_dimension: 512,
      });
    });

    it("omits output_dimension for v4 when embeddingDims is unset", async () => {
      mockSend.mockResolvedValueOnce(
        encode({ embeddings: { float: [[0.1, 0.2]] } }),
      );
      const embedder = new AWSBedrockEmbedder({ model: "cohere.embed-v4:0" });

      await embedder.embed("hello");

      expect(requestBodyAt(0)).toEqual({
        texts: ["hello"],
        input_type: "search_document",
        embedding_types: ["float"],
      });
    });

    it("parses the nested embeddings.float response shape", async () => {
      mockSend.mockResolvedValueOnce(
        encode({
          embeddings: {
            float: [
              [1, 2],
              [3, 4],
            ],
          },
        }),
      );
      const embedder = new AWSBedrockEmbedder({ model: "cohere.embed-v4:0" });

      const embeddings = await embedder.embedBatch(["a", "b"]);

      expect(embeddings).toEqual([
        [1, 2],
        [3, 4],
      ]);
    });
  });

  describe("client configuration", () => {
    it("defaults to the us-west-2 region", async () => {
      mockSend.mockResolvedValueOnce(titanReply([1]));
      await new AWSBedrockEmbedder({}).embed("hello");

      expect(mockClientConfigs[0].region).toBe("us-west-2");
    });

    it("prefers awsRegion over the AWS_REGION environment variable", async () => {
      process.env.AWS_REGION = "eu-central-1";
      mockSend.mockResolvedValueOnce(titanReply([1]));
      await new AWSBedrockEmbedder({ awsRegion: "ap-south-1" }).embed("hello");

      expect(mockClientConfigs[0].region).toBe("ap-south-1");
    });

    it("falls back to the AWS_REGION environment variable", async () => {
      process.env.AWS_REGION = "eu-central-1";
      mockSend.mockResolvedValueOnce(titanReply([1]));
      await new AWSBedrockEmbedder({}).embed("hello");

      expect(mockClientConfigs[0].region).toBe("eu-central-1");
    });

    it("passes explicitly configured credentials to the client", async () => {
      mockSend.mockResolvedValueOnce(titanReply([1]));
      await new AWSBedrockEmbedder({
        awsAccessKeyId: "AKIA_TEST",
        awsSecretAccessKey: "secret",
        awsSessionToken: "token",
      }).embed("hello");

      expect(mockClientConfigs[0].credentials).toEqual({
        accessKeyId: "AKIA_TEST",
        secretAccessKey: "secret",
        sessionToken: "token",
      });
    });

    it("leaves credentials unset so the AWS default credential chain applies", async () => {
      mockSend.mockResolvedValueOnce(titanReply([1]));
      await new AWSBedrockEmbedder({}).embed("hello");

      expect(mockClientConfigs[0].credentials).toBeUndefined();
    });

    it("rejects a half-configured credential pair", () => {
      expect(
        () => new AWSBedrockEmbedder({ awsAccessKeyId: "AKIA_TEST" }),
      ).toThrow(/awsAccessKeyId and awsSecretAccessKey/);
      expect(
        () => new AWSBedrockEmbedder({ awsSecretAccessKey: "secret" }),
      ).toThrow(/awsAccessKeyId and awsSecretAccessKey/);
    });

    // Silently ignoring a lone session token would fall back to the ambient
    // credential chain, embedding under an identity the caller never chose.
    it("rejects a session token supplied without the key pair", () => {
      expect(
        () => new AWSBedrockEmbedder({ awsSessionToken: "token" }),
      ).toThrow(/awsAccessKeyId and awsSecretAccessKey/);
    });
  });

  describe("provider registration", () => {
    it("is constructed by EmbedderFactory for the aws_bedrock provider", () => {
      const embedder = EmbedderFactory.create("aws_bedrock", {
        model: "amazon.titan-embed-text-v2:0",
      });

      expect(embedder).toBeInstanceOf(AWSBedrockEmbedder);
    });
  });

  describe("error handling", () => {
    it("wraps Bedrock failures with the model id", async () => {
      mockSend.mockRejectedValueOnce(new Error("AccessDeniedException"));
      const embedder = new AWSBedrockEmbedder({});

      await expect(embedder.embed("hello")).rejects.toThrow(
        "Error getting embedding from AWS Bedrock model amazon.titan-embed-text-v1: AccessDeniedException",
      );
    });

    it("fails when the response carries no embedding", async () => {
      mockSend.mockResolvedValueOnce(encode({ inputTextTokenCount: 3 }));
      const embedder = new AWSBedrockEmbedder({});

      await expect(embedder.embed("hello")).rejects.toThrow(
        /returned no embedding/,
      );
    });

    // F7: `[]` is truthy, so `payload.embedding && [payload.embedding]` used to
    // turn `{"embedding": []}` into `[[]]` -- length 1, which satisfied the
    // length check for a single-input call and handed the caller an empty vector.
    it("rejects a zero-length Titan embedding as no embedding", async () => {
      mockSend.mockResolvedValueOnce(encode({ embedding: [] }));
      const embedder = new AWSBedrockEmbedder({});

      await expect(embedder.embed("hello")).rejects.toThrow(
        /returned no embedding/,
      );
    });

    it("returns an empty array for an empty batch without calling Bedrock", async () => {
      const embedder = new AWSBedrockEmbedder({});

      await expect(embedder.embedBatch([])).resolves.toEqual([]);
      expect(mockSend).not.toHaveBeenCalled();
    });
  });

  describe("dynamic SDK import", () => {
    // These tests replace the module registered for
    // @aws-sdk/client-bedrock-runtime for a single resolution. Restore the
    // working mock afterward so every other test in this file keeps getting
    // the mocked client instead of hitting module resolution for real.
    afterEach(() => {
      jest.resetModules();
      jest.doMock("@aws-sdk/client-bedrock-runtime", () => {
        const actual = jest.requireActual("@aws-sdk/client-bedrock-runtime");
        return { ...actual, BedrockRuntimeClient: mockClientConstructor };
      });
    });

    // F1: loadSdk()'s catch used to rewrite *every* import failure into the
    // "package is required" hint, even when the package is installed but
    // failed to load for an unrelated reason. That discarded the real error.
    it("propagates a non-resolution import error unchanged", async () => {
      jest.resetModules();
      jest.doMock("@aws-sdk/client-bedrock-runtime", () => {
        const err: any = new Error("boom: unrelated crash while loading");
        err.code = "ERR_SOMETHING_ELSE";
        throw err;
      });
      const embedder = new AWSBedrockEmbedder({});

      await expect(embedder.embed("hello")).rejects.toThrow(
        "boom: unrelated crash while loading",
      );
    });

    // F1: a genuine resolution failure should still get the friendly install
    // hint, with the original error preserved as `cause` for debugging.
    it("gives an install hint for a genuine module-not-found error, preserving the cause", async () => {
      jest.resetModules();
      jest.doMock("@aws-sdk/client-bedrock-runtime", () => {
        const err: any = new Error(
          "Cannot find module '@aws-sdk/client-bedrock-runtime'",
        );
        err.code = "MODULE_NOT_FOUND";
        throw err;
      });
      const embedder = new AWSBedrockEmbedder({});

      await expect(embedder.embed("hello")).rejects.toThrow(
        /npm install @aws-sdk\/client-bedrock-runtime/,
      );
      await expect(embedder.embed("hello")).rejects.toMatchObject({
        cause: expect.objectContaining({ code: "MODULE_NOT_FOUND" }),
      });
    });
  });

  describe("client promise retry", () => {
    // F2: getClient() used to memoize the client promise before it resolved,
    // so a rejected construction (e.g. a transient credentials failure) was
    // cached forever -- every later embed() call on that instance would
    // reject immediately without ever retrying.
    it("retries client construction after a failure instead of caching the rejection", async () => {
      mockClientConstructor.mockImplementationOnce(() => {
        throw new Error("credentials not ready");
      });
      mockSend.mockResolvedValueOnce(titanReply([1, 2, 3]));
      const embedder = new AWSBedrockEmbedder({});

      await expect(embedder.embed("hello")).rejects.toThrow(
        "credentials not ready",
      );
      await expect(embedder.embed("hello")).resolves.toEqual([1, 2, 3]);
    });
  });

  describe("memoryAction -> Cohere input_type", () => {
    // F3: buildRequestBody() used to hardcode `input_type: "search_document"`
    // regardless of the caller's action, so `Memory.search()` (which calls
    // `embed(query, "search")`) embedded the query in document mode.
    //
    // Typed as `Embedder` (not `AWSBedrockEmbedder`) because that is how
    // memory/index.ts actually calls it: the interface already declares an
    // optional `memoryAction` second parameter, so a narrower concrete
    // `embed(text: string)` satisfies it structurally and tsc stays silent --
    // the bug is a silent behavioral one, not a compile error.
    it("sends search_query for a search action", async () => {
      mockSend.mockResolvedValueOnce(cohereReply([[0.1]]));
      const embedder: Embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      await embedder.embed("query text", "search");

      expect(requestBodyAt(0)).toEqual({
        texts: ["query text"],
        input_type: "search_query",
      });
    });

    it("sends search_document for add and update actions", async () => {
      mockSend
        .mockResolvedValueOnce(cohereReply([[0.1]]))
        .mockResolvedValueOnce(cohereReply([[0.2]]));
      const embedder: Embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      await embedder.embed("doc one", "add");
      await embedder.embed("doc two", "update");

      expect(requestBodyAt(0).input_type).toBe("search_document");
      expect(requestBodyAt(1).input_type).toBe("search_document");
    });

    // Titan has no input_type concept; buildRequestBody() must not add one
    // even when a memoryAction is explicitly passed through.
    it("Titan ignores memoryAction and never sends input_type", async () => {
      mockSend.mockResolvedValueOnce(titanReply([1, 2]));
      const embedder: Embedder = new AWSBedrockEmbedder({});

      await embedder.embed("hello", "search");

      expect(requestBodyAt(0)).toEqual({ inputText: "hello" });
    });
  });

  describe("Titan embedBatch concurrency", () => {
    afterEach(() => {
      // This test sets a persistent mockImplementation (not a *Once), so
      // clear it explicitly -- jest.clearAllMocks() in the top beforeEach
      // clears call data but not implementations.
      mockSend.mockReset();
    });

    // F4: embedBatch() used to Promise.all-fan-out one InvokeModel call per
    // text with no cap, so a large batch could open hundreds of concurrent
    // requests at once. TITAN_MAX_CONCURRENCY bounds this to a small pool
    // while still preserving output order.
    it("never runs more than TITAN_MAX_CONCURRENCY Titan requests at once, and preserves order", async () => {
      let active = 0;
      let peak = 0;
      mockSend.mockImplementation(async (command: InvokeModelCommand) => {
        active++;
        peak = Math.max(peak, active);
        const body = JSON.parse(
          new TextDecoder().decode(command.input.body as Uint8Array),
        );
        await new Promise((resolve) => setTimeout(resolve, 10));
        active--;
        const index = Number(body.inputText.split("-")[1]);
        return titanReply([index]);
      });
      const embedder = new AWSBedrockEmbedder({});
      const texts = Array.from({ length: 10 }, (_, i) => `text-${i}`);

      const embeddings = await embedder.embedBatch(texts);

      expect(peak).toBeGreaterThan(1);
      expect(peak).toBeLessThanOrEqual(4);
      expect(embeddings).toEqual(texts.map((_, i) => [i]));
      expect(mockSend).toHaveBeenCalledTimes(10);
    });
  });
});
