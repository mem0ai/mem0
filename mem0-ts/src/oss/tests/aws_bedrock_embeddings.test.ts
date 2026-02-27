/**
 * AWS Bedrock Embedder unit tests.
 *
 * Tests the AWSBedrockEmbedder implementation with mocked AWS SDK.
 */

/// <reference types="jest" />

// Mock the AWS SDK before importing the embedder
const mockSend = jest.fn();

jest.mock(
  "@aws-sdk/client-bedrock-runtime",
  () => ({
    BedrockRuntimeClient: jest.fn().mockImplementation(() => ({
      send: mockSend,
    })),
    InvokeModelCommand: jest.fn().mockImplementation((params) => params),
  }),
  { virtual: true },
);

import { AWSBedrockEmbedder } from "../src/embeddings/aws_bedrock";

describe("AWSBedrockEmbedder", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("constructor", () => {
    it("should create embedder with default config", () => {
      const embedder = new AWSBedrockEmbedder({});

      expect(embedder).toBeDefined();
    });

    it("should create embedder with custom model", () => {
      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      expect(embedder).toBeDefined();
    });

    it("should create embedder with region config", () => {
      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        region: "us-west-2",
      });

      expect(embedder).toBeDefined();
    });

    it("should create embedder with credentials", () => {
      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        credentials: {
          accessKeyId: "test-key",
          secretAccessKey: "test-secret",
        },
      });

      expect(embedder).toBeDefined();
    });

    it("should create embedder with session token", () => {
      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        credentials: {
          accessKeyId: "test-key",
          secretAccessKey: "test-secret",
          sessionToken: "test-session",
        },
      });

      expect(embedder).toBeDefined();
    });

    it("should create embedder with normalize option", () => {
      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        normalize: true,
      });

      expect(embedder).toBeDefined();
    });
  });

  describe("embed - Amazon Titan", () => {
    it("should generate embedding for text", async () => {
      const mockEmbedding = [0.1, 0.2, 0.3, 0.4, 0.5];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
      });

      const result = await embedder.embed("Hello, world!");

      expect(result).toEqual(mockEmbedding);
      expect(mockSend).toHaveBeenCalledTimes(1);
    });

    it("should use correct input format for Titan", async () => {
      const mockEmbedding = [0.1, 0.2, 0.3];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
      });

      await embedder.embed("Test text");

      expect(mockSend).toHaveBeenCalledWith(
        expect.objectContaining({
          modelId: "amazon.titan-embed-text-v1",
          body: JSON.stringify({ inputText: "Test text" }),
        }),
      );
    });

    it("should normalize embedding when normalize option is true", async () => {
      // Vector [3, 4] should normalize to [0.6, 0.8] (magnitude = 5)
      const mockEmbedding = [3, 4];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        normalize: true,
      });

      const result = await embedder.embed("Test");

      expect(result[0]).toBeCloseTo(0.6, 5);
      expect(result[1]).toBeCloseTo(0.8, 5);
    });

    it("should not normalize when normalize option is false", async () => {
      const mockEmbedding = [3, 4];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        normalize: false,
      });

      const result = await embedder.embed("Test");

      expect(result).toEqual(mockEmbedding);
    });

    it("should handle Titan v2 model", async () => {
      const mockEmbedding = [0.1, 0.2, 0.3];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v2:0",
      });

      const result = await embedder.embed("Test");

      expect(result).toEqual(mockEmbedding);
    });
  });

  describe("embed - Cohere", () => {
    it("should generate embedding for text", async () => {
      const mockEmbeddings = [[0.1, 0.2, 0.3, 0.4, 0.5]];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embeddings: mockEmbeddings }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      const result = await embedder.embed("Hello, world!");

      expect(result).toEqual(mockEmbeddings[0]);
      expect(mockSend).toHaveBeenCalledTimes(1);
    });

    it("should use correct input format for Cohere", async () => {
      const mockEmbeddings = [[0.1, 0.2, 0.3]];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embeddings: mockEmbeddings }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      await embedder.embed("Test text");

      expect(mockSend).toHaveBeenCalledWith(
        expect.objectContaining({
          modelId: "cohere.embed-english-v3",
          body: JSON.stringify({
            texts: ["Test text"],
            input_type: "search_document",
          }),
        }),
      );
    });

    it("should normalize Cohere embedding when normalize option is true", async () => {
      const mockEmbeddings = [[3, 4]];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embeddings: mockEmbeddings }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
        normalize: true,
      });

      const result = await embedder.embed("Test");

      expect(result[0]).toBeCloseTo(0.6, 5);
      expect(result[1]).toBeCloseTo(0.8, 5);
    });

    it("should handle multilingual model", async () => {
      const mockEmbeddings = [[0.1, 0.2, 0.3]];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embeddings: mockEmbeddings }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-multilingual-v3",
      });

      const result = await embedder.embed("Bonjour le monde!");

      expect(result).toEqual(mockEmbeddings[0]);
    });
  });

  describe("embedBatch - Amazon Titan", () => {
    it("should process texts sequentially for Titan", async () => {
      const mockEmbedding1 = [0.1, 0.2, 0.3];
      const mockEmbedding2 = [0.4, 0.5, 0.6];

      mockSend
        .mockResolvedValueOnce({
          body: new TextEncoder().encode(
            JSON.stringify({ embedding: mockEmbedding1 }),
          ),
        })
        .mockResolvedValueOnce({
          body: new TextEncoder().encode(
            JSON.stringify({ embedding: mockEmbedding2 }),
          ),
        });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
      });

      const result = await embedder.embedBatch(["Text 1", "Text 2"]);

      expect(result).toEqual([mockEmbedding1, mockEmbedding2]);
      expect(mockSend).toHaveBeenCalledTimes(2);
    });

    it("should return empty array for empty input", async () => {
      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
      });

      const result = await embedder.embedBatch([]);

      expect(result).toEqual([]);
      expect(mockSend).not.toHaveBeenCalled();
    });

    it("should handle single item batch", async () => {
      const mockEmbedding = [0.1, 0.2, 0.3];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
      });

      const result = await embedder.embedBatch(["Single text"]);

      expect(result).toEqual([mockEmbedding]);
      expect(mockSend).toHaveBeenCalledTimes(1);
    });
  });

  describe("embedBatch - Cohere", () => {
    it("should batch process texts for Cohere", async () => {
      const mockEmbeddings = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
      ];

      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embeddings: mockEmbeddings }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      const result = await embedder.embedBatch(["Text 1", "Text 2"]);

      expect(result).toEqual(mockEmbeddings);
      expect(mockSend).toHaveBeenCalledTimes(1); // Single batch call
    });

    it("should use correct batch input format for Cohere", async () => {
      const mockEmbeddings = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9],
      ];

      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embeddings: mockEmbeddings }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      await embedder.embedBatch(["Text 1", "Text 2", "Text 3"]);

      expect(mockSend).toHaveBeenCalledWith(
        expect.objectContaining({
          body: JSON.stringify({
            texts: ["Text 1", "Text 2", "Text 3"],
            input_type: "search_document",
          }),
        }),
      );
    });

    it("should return empty array for empty input", async () => {
      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      const result = await embedder.embedBatch([]);

      expect(result).toEqual([]);
      expect(mockSend).not.toHaveBeenCalled();
    });

    it("should normalize batch embeddings when option is true", async () => {
      const mockEmbeddings = [
        [3, 4],
        [6, 8],
      ];

      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embeddings: mockEmbeddings }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
        normalize: true,
      });

      const result = await embedder.embedBatch(["Text 1", "Text 2"]);

      // [3,4] -> [0.6, 0.8], [6,8] -> [0.6, 0.8]
      expect(result[0][0]).toBeCloseTo(0.6, 5);
      expect(result[0][1]).toBeCloseTo(0.8, 5);
      expect(result[1][0]).toBeCloseTo(0.6, 5);
      expect(result[1][1]).toBeCloseTo(0.8, 5);
    });
  });

  describe("error handling", () => {
    it("should throw error when embedding is missing in Amazon response", async () => {
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(JSON.stringify({})),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
      });

      await expect(embedder.embed("Test")).rejects.toThrow(
        "No embedding found in Amazon Titan response",
      );
    });

    it("should throw error when embeddings are missing in Cohere response", async () => {
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(JSON.stringify({})),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      await expect(embedder.embed("Test")).rejects.toThrow(
        "No embeddings found in Cohere response",
      );
    });

    it("should throw error when embeddings array is empty in Cohere response", async () => {
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(JSON.stringify({ embeddings: [] })),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      await expect(embedder.embed("Test")).rejects.toThrow(
        "No embeddings found in Cohere response",
      );
    });

    it("should propagate AWS SDK errors", async () => {
      const error = new Error("AWS SDK error");
      mockSend.mockRejectedValueOnce(error);

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
      });

      await expect(embedder.embed("Test")).rejects.toThrow("AWS SDK error");
    });
  });

  describe("normalization edge cases", () => {
    it("should handle zero vector without error", async () => {
      const mockEmbedding = [0, 0, 0];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        normalize: true,
      });

      const result = await embedder.embed("Test");

      // Zero vector should remain zero vector
      expect(result).toEqual([0, 0, 0]);
    });

    it("should correctly normalize high-dimensional vectors", async () => {
      // Create a vector with known magnitude
      const dimension = 1536;
      const value = 1 / Math.sqrt(dimension);
      const mockEmbedding = new Array(dimension).fill(value);

      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
        normalize: true,
      });

      const result = await embedder.embed("Test");

      // Check that the result is a unit vector (magnitude ≈ 1)
      const magnitude = Math.sqrt(
        result.reduce((sum, val) => sum + val * val, 0),
      );
      expect(magnitude).toBeCloseTo(1, 5);
    });
  });

  describe("provider detection", () => {
    it("should detect Amazon provider for titan models", async () => {
      const mockEmbedding = [0.1, 0.2, 0.3];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "amazon.titan-embed-text-v1",
      });

      await embedder.embed("Test");

      expect(mockSend).toHaveBeenCalledWith(
        expect.objectContaining({
          body: expect.stringContaining("inputText"),
        }),
      );
    });

    it("should detect Cohere provider for cohere models", async () => {
      const mockEmbeddings = [[0.1, 0.2, 0.3]];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embeddings: mockEmbeddings }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "cohere.embed-english-v3",
      });

      await embedder.embed("Test");

      expect(mockSend).toHaveBeenCalledWith(
        expect.objectContaining({
          body: expect.stringContaining("texts"),
        }),
      );
    });

    it("should default to Amazon for unknown models", async () => {
      const mockEmbedding = [0.1, 0.2, 0.3];
      mockSend.mockResolvedValueOnce({
        body: new TextEncoder().encode(
          JSON.stringify({ embedding: mockEmbedding }),
        ),
      });

      const embedder = new AWSBedrockEmbedder({
        model: "some.unknown-model-v1",
      });

      await embedder.embed("Test");

      // Should use Amazon Titan format (inputText)
      expect(mockSend).toHaveBeenCalledWith(
        expect.objectContaining({
          body: expect.stringContaining("inputText"),
        }),
      );
    });
  });
});
