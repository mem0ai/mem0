import { Embeddings } from "@langchain/core/embeddings";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

export class LangchainEmbedder implements Embedder {
  private embedderInstance: Embeddings;
  private batchSize?: number; // Some LC embedders have batch size

  constructor(config: EmbeddingConfig) {
    // Check if config.model is provided and is an object (the instance)
    if (!config.model || typeof config.model !== "object") {
      throw new Error(
        "Langchain embedder provider requires an initialized Langchain Embeddings instance passed via the 'model' field in the embedder config.",
      );
    }
    // Basic check for embedding methods
    if (
      typeof (config.model as any).embedQuery !== "function" ||
      typeof (config.model as any).embedDocuments !== "function"
    ) {
      throw new Error(
        "Provided Langchain 'instance' in the 'model' field does not appear to be a valid Langchain Embeddings instance (missing embedQuery or embedDocuments method).",
      );
    }
    this.embedderInstance = config.model as Embeddings;
    // Store batch size if the instance has it (optional)
    this.batchSize = (this.embedderInstance as any).batchSize;
  }

  async embed(text: string): Promise<number[]> {
    try {
      // Use embedQuery for single text embedding
      return await this.embedderInstance.embedQuery(text);
    } catch (error) {
      console.error("Error embedding text with Langchain Embedder:", error);
      throw error;
    }
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    try {
      // Use embedDocuments for batch embedding
      // Langchain's embedDocuments handles batching internally if needed/supported
      return await this.embedderInstance.embedDocuments(texts);
    } catch (error) {
      console.error("Error embedding batch with Langchain Embedder:", error);
      throw error;
    }
  }
}
