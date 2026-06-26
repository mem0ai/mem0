import { FastEmbedEmbedder } from "../embeddings/fastembed";
import { EmbedderFactory } from "../utils/factory";

// ---------------------------------------------------------------------------
// Mock the optional `fastembed` package so tests don't download ONNX models.
// ---------------------------------------------------------------------------

const initMock = jest.fn();

jest.mock(
  "fastembed",
  () => ({
    FlagEmbedding: {
      init: (...args: any[]) => initMock(...args),
    },
    EmbeddingModel: {
      BGESmallENV15: "fast-bge-small-en-v1.5",
      BGEBaseENV15: "fast-bge-base-en-v1.5",
      CUSTOM: "custom",
    },
  }),
  { virtual: true },
);

/** Build a fake FlagEmbedding instance whose embed() yields the given batches. */
function fakeEmbedding(vectorsByText: Record<string, number[]>) {
  return {
    embed: async function* (texts: string[]) {
      yield texts.map((t) => vectorsByText[t] ?? [0, 0, 0]);
    },
    passageEmbed: async function* (texts: string[]) {
      yield texts.map((t) => vectorsByText[t] ?? [0, 0, 0]);
    },
    listSupportedModels: () => [],
  };
}

describe("FastEmbedEmbedder", () => {
  beforeEach(() => {
    initMock.mockReset();
  });

  it("is registered in EmbedderFactory under 'fastembed'", () => {
    const embedder = EmbedderFactory.create("fastembed", {});
    expect(embedder).toBeInstanceOf(FastEmbedEmbedder);
  });

  it("defaults to fast-bge-small-en-v1.5 when no model is provided", async () => {
    initMock.mockResolvedValue(fakeEmbedding({ hello: [0.1, 0.2, 0.3] }));
    const embedder = new FastEmbedEmbedder({});

    await embedder.embed("hello");

    expect(initMock).toHaveBeenCalledTimes(1);
    expect(initMock.mock.calls[0][0]).toMatchObject({
      model: "fast-bge-small-en-v1.5",
    });
  });

  it("applies the default model when model is explicitly undefined (config-merge path)", async () => {
    // ConfigManager.mergeConfig() passes `model: undefined` for fastembed so
    // the provider's own default wins instead of OpenAI's default model.
    initMock.mockResolvedValue(fakeEmbedding({ hi: [0.4] }));
    const embedder = new FastEmbedEmbedder({ model: undefined });

    await embedder.embed("hi");

    expect(initMock.mock.calls[0][0]).toMatchObject({
      model: "fast-bge-small-en-v1.5",
    });
  });

  it("uses the configured model and passes through modelProperties", async () => {
    initMock.mockResolvedValue(fakeEmbedding({ hi: [1, 2] }));
    const embedder = new FastEmbedEmbedder({
      model: "fast-bge-base-en-v1.5",
      modelProperties: { maxLength: 256, showDownloadProgress: false },
    });

    await embedder.embed("hi");

    expect(initMock.mock.calls[0][0]).toMatchObject({
      model: "fast-bge-base-en-v1.5",
      maxLength: 256,
      showDownloadProgress: false,
    });
  });

  it("embeds a single text and normalizes newlines", async () => {
    const captured: string[] = [];
    initMock.mockResolvedValue({
      embed: async function* (texts: string[]) {
        captured.push(...texts);
        yield texts.map(() => [0.5, 0.5]);
      },
      passageEmbed: async function* () {},
      listSupportedModels: () => [],
    });

    const embedder = new FastEmbedEmbedder({});
    const result = await embedder.embed("line one\nline two");

    expect(result).toEqual([0.5, 0.5]);
    expect(captured).toEqual(["line one line two"]);
  });

  it("initializes the model only once across multiple embed calls", async () => {
    initMock.mockResolvedValue(fakeEmbedding({ a: [1], b: [2] }));
    const embedder = new FastEmbedEmbedder({});

    await embedder.embed("a");
    await embedder.embed("b");

    expect(initMock).toHaveBeenCalledTimes(1);
  });

  it("normalizes Float32Array output to a plain number[]", async () => {
    initMock.mockResolvedValue({
      embed: async function* () {
        yield [new Float32Array([0.1, 0.2, 0.3])];
      },
      passageEmbed: async function* () {},
      listSupportedModels: () => [],
    });
    const embedder = new FastEmbedEmbedder({});

    const result = await embedder.embed("x");

    expect(Array.isArray(result)).toBe(true);
    expect(result).not.toBeInstanceOf(Float32Array);
    expect(result).toEqual([
      expect.closeTo(0.1),
      expect.closeTo(0.2),
      expect.closeTo(0.3),
    ]);
  });

  it("embeds a batch of texts in order", async () => {
    initMock.mockResolvedValue(
      fakeEmbedding({ one: [1, 1], two: [2, 2], three: [3, 3] }),
    );
    const embedder = new FastEmbedEmbedder({});

    const result = await embedder.embedBatch(["one", "two", "three"]);

    expect(result).toEqual([
      [1, 1],
      [2, 2],
      [3, 3],
    ]);
  });

  it("returns an empty array for an empty batch without initializing", async () => {
    const embedder = new FastEmbedEmbedder({});
    const result = await embedder.embedBatch([]);

    expect(result).toEqual([]);
    expect(initMock).not.toHaveBeenCalled();
  });

  it("throws a helpful error when model initialization fails", async () => {
    initMock.mockRejectedValue(new Error("unknown model"));
    const embedder = new FastEmbedEmbedder({ model: "not-a-real-model" });

    await expect(embedder.embed("x")).rejects.toThrow(
      /Failed to initialize FastEmbed model 'not-a-real-model'/,
    );
  });

  it("retries initialization after a transient init failure", async () => {
    initMock.mockRejectedValueOnce(new Error("transient init failure"));
    initMock.mockResolvedValueOnce(fakeEmbedding({ second: [0.9] }));
    const embedder = new FastEmbedEmbedder({});

    // First call fails (rejected init promise must not be cached).
    await expect(embedder.embed("first")).rejects.toThrow(
      /Failed to initialize FastEmbed model/,
    );

    // Second call should re-attempt init and succeed.
    const result = await embedder.embed("second");

    expect(initMock).toHaveBeenCalledTimes(2);
    expect(result).toEqual([0.9]);
  });
});
