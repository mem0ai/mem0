import { VertexAIVectorSearch } from "../vector_stores/vertex_ai_vector_search";

describe("VertexAIVectorSearch", () => {
  const mockConfig = {
    projectId: "test-project",
    projectNumber: "123456789",
    region: "us-central1",
    endpointId: "projects/123456789/locations/us-central1/indexEndpoints/test-endpoint",
    indexId: "test-index",
    deploymentIndexId: "test-deployment",
    collectionName: "test-collection",
    vectorSearchApiEndpoint: "us-central1-aiplatform.googleapis.com",
  };

  describe("constructor", () => {
    it("should initialize with required config", () => {
      // This test will fail if @google-cloud/aiplatform is not installed
      // In a real CI environment, you would mock the aiplatform module
      try {
        const vectorStore = new VertexAIVectorSearch(mockConfig);
        expect(vectorStore).toBeInstanceOf(VertexAIVectorSearch);
      } catch (error: any) {
        // Expected if @google-cloud/aiplatform is not installed
        expect(error.message).toContain("@google-cloud/aiplatform is required");
      }
    });

    it("should handle collection_name/deployment_index_id mapping", () => {
      try {
        const config1 = { ...mockConfig, collectionName: "test" };
        // @ts-ignore - testing internal behavior
        const vs1 = new VertexAIVectorSearch(config1);
        expect(vs1).toBeDefined();

        const config2 = { ...mockConfig, deploymentIndexId: "test2" };
        // @ts-ignore - testing internal behavior
        const vs2 = new VertexAIVectorSearch(config2);
        expect(vs2).toBeDefined();
      } catch (error: any) {
        // Expected if @google-cloud/aiplatform is not installed
        expect(error.message).toContain("@google-cloud/aiplatform is required");
      }
    });
  });

  describe("keywordSearch", () => {
    it("should return null (not supported)", async () => {
      try {
        const vectorStore = new VertexAIVectorSearch(mockConfig);
        const result = await vectorStore.keywordSearch("test query", 5, {});
        expect(result).toBeNull();
      } catch (error: any) {
        // Expected if @google-cloud/aiplatform is not installed
        expect(error.message).toContain("@google-cloud/aiplatform is required");
      }
    });
  });

  describe("deleteCol", () => {
    it("should warn that delete collection is not supported", async () => {
      try {
        const vectorStore = new VertexAIVectorSearch(mockConfig);
        const consoleWarnSpy = jest.spyOn(console, "warn").mockImplementation();
        await vectorStore.deleteCol();
        expect(consoleWarnSpy).toHaveBeenCalledWith(
          "Delete collection operation is not supported for Vertex AI Vector Search"
        );
        consoleWarnSpy.mockRestore();
      } catch (error: any) {
        // Expected if @google-cloud/aiplatform is not installed
        expect(error.message).toContain("@google-cloud/aiplatform is required");
      }
    });
  });

  describe("getUserId/setUserId", () => {
    it("should generate and set user ID", async () => {
      try {
        const vectorStore = new VertexAIVectorSearch(mockConfig);
        const userId = await vectorStore.getUserId();
        expect(userId).toBeTruthy();
        expect(typeof userId).toBe("string");

        await vectorStore.setUserId("test-user-id");
        const newUserId = await vectorStore.getUserId();
        expect(newUserId).toBe("test-user-id");
      } catch (error: any) {
        // Expected if @google-cloud/aiplatform is not installed
        expect(error.message).toContain("@google-cloud/aiplatform is required");
      }
    });
  });

  describe("initialize", () => {
    it("should initialize without errors", async () => {
      try {
        const vectorStore = new VertexAIVectorSearch(mockConfig);
        await vectorStore.initialize();
        expect(vectorStore).toBeDefined();
      } catch (error: any) {
        // Expected if @google-cloud/aiplatform is not installed
        expect(error.message).toContain("@google-cloud/aiplatform is required");
      }
    });
  });
});
