/// <reference types="jest" />
/**
 * Tests for Qdrant Cloud URL port extraction workaround (qdrant/qdrant-js#59).
 *
 * Verifies that when a `url` config is provided, the port is extracted and
 * passed explicitly to QdrantClient to avoid "Illegal host" errors.
 */

jest.setTimeout(15000);

let capturedParams: Record<string, any> | undefined;

// Mock QdrantClient to capture constructor params
jest.mock("@qdrant/js-client-rest", () => {
  return {
    QdrantClient: jest.fn().mockImplementation((params: any) => {
      capturedParams = params;
      // Return a mock client that satisfies initialize()
      return {
        createCollection: jest.fn().mockResolvedValue(undefined),
        getCollection: jest.fn().mockResolvedValue({
          config: { params: { vectors: { size: 768 } } },
        }),
        scroll: jest.fn().mockResolvedValue({ points: [] }),
        upsert: jest.fn().mockResolvedValue(undefined),
        retrieve: jest.fn().mockResolvedValue([]),
        search: jest.fn().mockResolvedValue([]),
        delete: jest.fn().mockResolvedValue(undefined),
        deleteCollection: jest.fn().mockResolvedValue(undefined),
      };
    }),
  };
});

import { Qdrant } from "../src/vector_stores/qdrant";

beforeEach(() => {
  capturedParams = undefined;
  (require("@qdrant/js-client-rest").QdrantClient as jest.Mock).mockClear();
});

describe("Qdrant URL port extraction (qdrant/qdrant-js#59 workaround)", () => {
  it("extracts port from HTTPS URL with explicit port", () => {
    new Qdrant({
      url: "https://my-cluster.us-west-1-0.aws.cloud.qdrant.io:6333",
      apiKey: "test-key",
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });

    expect(capturedParams).toBeDefined();
    expect(capturedParams!.url).toBe(
      "https://my-cluster.us-west-1-0.aws.cloud.qdrant.io:6333",
    );
    expect(capturedParams!.port).toBe(6333);
    expect(capturedParams!.apiKey).toBe("test-key");
  });

  it("extracts port from HTTP URL with explicit port", () => {
    new Qdrant({
      url: "http://localhost:6333",
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });

    expect(capturedParams).toBeDefined();
    expect(capturedParams!.url).toBe("http://localhost:6333");
    expect(capturedParams!.port).toBe(6333);
  });

  it("defaults to port 6333 when HTTPS URL has no explicit port", () => {
    new Qdrant({
      url: "https://my-cluster.cloud.qdrant.io",
      apiKey: "test-key",
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });

    expect(capturedParams).toBeDefined();
    expect(capturedParams!.url).toBe("https://my-cluster.cloud.qdrant.io");
    expect(capturedParams!.port).toBe(6333);
  });

  it("defaults to port 6333 when HTTP URL has no explicit port", () => {
    new Qdrant({
      url: "http://localhost",
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });

    expect(capturedParams).toBeDefined();
    expect(capturedParams!.port).toBe(6333);
  });

  it("host+port config overrides URL-extracted port", () => {
    new Qdrant({
      url: "https://my-cluster.cloud.qdrant.io:6333",
      host: "custom-host",
      port: 9999,
      apiKey: "test-key",
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });

    expect(capturedParams).toBeDefined();
    expect(capturedParams!.host).toBe("custom-host");
    expect(capturedParams!.port).toBe(9999);
  });

  it("handles invalid URL gracefully without crashing", () => {
    expect(() => {
      new Qdrant({
        url: "not-a-valid-url",
        collectionName: "test",
        embeddingModelDims: 768,
        dimension: 768,
      });
    }).not.toThrow();

    expect(capturedParams).toBeDefined();
    expect(capturedParams!.url).toBe("not-a-valid-url");
    expect(capturedParams!.port).toBe(6333);
  });

  it("does not pass port when using pre-configured client", () => {
    const mockClient: any = {
      createCollection: jest.fn().mockResolvedValue(undefined),
      getCollection: jest.fn().mockResolvedValue({
        config: { params: { vectors: { size: 768 } } },
      }),
      scroll: jest.fn().mockResolvedValue({ points: [] }),
      upsert: jest.fn().mockResolvedValue(undefined),
      retrieve: jest.fn().mockResolvedValue([]),
      search: jest.fn().mockResolvedValue([]),
      delete: jest.fn().mockResolvedValue(undefined),
      deleteCollection: jest.fn().mockResolvedValue(undefined),
    };

    new Qdrant({
      client: mockClient,
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });

    // QdrantClient constructor should NOT have been called
    expect(
      require("@qdrant/js-client-rest").QdrantClient,
    ).not.toHaveBeenCalled();
  });

  it("defaults to 6333 when HTTPS URL uses default port 443", () => {
    new Qdrant({
      url: "https://my-cluster.cloud.qdrant.io:443",
      apiKey: "test-key",
      collectionName: "test",
      embeddingModelDims: 768,
      dimension: 768,
    });

    // 443 is default for HTTPS, so URL.port returns empty string — we default to 6333
    expect(capturedParams).toBeDefined();
    expect(capturedParams!.port).toBe(6333);
  });
});
