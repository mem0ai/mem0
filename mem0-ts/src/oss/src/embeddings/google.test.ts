import { GoogleEmbedder } from "./google";

jest.mock("@google/genai", () => ({
  GoogleGenAI: jest.fn().mockImplementation(() => ({
    models: {
      embedContent: jest.fn(),
    },
  })),
}));

// Re-import the mocked module so the mock class is available.
import { GoogleGenAI } from "@google/genai";

const mockedGenAI = GoogleGenAI as jest.MockedClass<typeof GoogleGenAI>;

describe("GoogleEmbedder", () => {
  let embedContent: jest.Mock;

  beforeEach(() => {
    embedContent = jest.fn();
    (mockedGenAI as any).mockImplementation(() => ({
      models: { embedContent },
    }));
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("embed() passes a single string content", async () => {
    embedContent.mockResolvedValue({ embeddings: [{ values: [0.1, 0.2] }] });
    const embedder = new GoogleEmbedder({ model: "gemini-embedding-001" });
    const result = await embedder.embed("hello");
    expect(embedContent).toHaveBeenCalledWith(
      expect.objectContaining({ contents: "hello" }),
    );
    expect(result).toEqual([0.1, 0.2]);
  });

  it("embedBatch() passes one content part per text (#7488)", async () => {
    embedContent.mockResolvedValue({
      embeddings: [{ values: [0.1] }, { values: [0.2] }],
    });
    const embedder = new GoogleEmbedder({ model: "gemini-embedding-002" });
    const result = await embedder.embedBatch(["apples", "sky"]);
    expect(embedContent).toHaveBeenCalledWith(
      expect.objectContaining({
        contents: [
          { parts: [{ text: "apples" }] },
          { parts: [{ text: "sky" }] },
        ],
      }),
    );
    expect(result).toEqual([[0.1], [0.2]]);
  });

  it("embedBatch() throws when the API collapses texts into fewer embeddings", async () => {
    embedContent.mockResolvedValue({
      embeddings: [{ values: [0.1] }], // one combined vector for two texts
    });
    const embedder = new GoogleEmbedder({ model: "gemini-embedding-002" });
    await expect(embedder.embedBatch(["apples", "sky"])).rejects.toThrow(
      "returned 1 embeddings for 2 texts",
    );
  });

  it("embedBatch() forwards outputDimensionality via config", async () => {
    embedContent.mockResolvedValue({
      embeddings: [{ values: [0.1] }],
    });
    const embedder = new GoogleEmbedder({
      model: "gemini-embedding-001",
      embeddingDims: 8,
    });
    await embedder.embedBatch(["hello"]);
    expect(embedContent).toHaveBeenCalledWith(
      expect.objectContaining({ config: { outputDimensionality: 8 } }),
    );
  });
});
