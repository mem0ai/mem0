import { Mistral } from "@mistralai/mistralai";
import { EmbeddingConfig } from "../types";
import { Embedder } from "./base";

/**
 * Embedder implementation using the Mistral API.
 *
 * This class communicates with Mistral’s embedding endpoint to transform
 * text (or batches of texts) into dense vector embeddings.
 */
export class MistralEmbedder implements Embedder {
  /**
   * The Mistral API client instance used to make embedding requests.
   * */
  private mistral: Mistral;
  /**
   * The model name to use for embedding generation. Defaults to `"mistral-embed"`.
   * */
  private model: string;

  /**
   * Creates a new `MistralEmbedder` instance.
   *
   * @param config - The embedding configuration, including API key and model name.
   *
   * @throws Will throw an error if the `apiKey` is not provided.
   */
  constructor(config: EmbeddingConfig) {
    if (!config.apiKey) {
      throw new Error("Mistral API key is required");
    }

    this.mistral = new Mistral({
      apiKey: config.apiKey,
    });

    this.model = config.model || "mistral-embed";
  }

  /**
   * Generates an embedding vector for a single text input using the configured Mistral model.
   *
   * @param text - The text to embed.
   * @returns A promise that resolves to a number array representing the embedding vector.
   */
  async embed(text: string): Promise<number[]> {
    const response = await this.mistral.embeddings.create({
      model: this.model,
      inputs: [text],
    });

    return response.data[0]?.embedding || [];
  }

  /**
   * Generates embedding vectors for a batch of text inputs.
   *
   * @param texts - An array of text strings to embed.
   * @returns A promise that resolves to an array of embedding vectors,
   *          one for each input string.
   */
  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await this.mistral.embeddings.create({
      model: this.model,
      inputs: texts,
    });

    return response.data.map((item) => item.embedding || []);
  }
}
