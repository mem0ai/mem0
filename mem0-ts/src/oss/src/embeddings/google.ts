import type { GoogleGenAI } from "@google/genai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";
import { loadPeer } from "../utils/load_peer";

export class GoogleEmbedder implements Embedder {
  private google!: GoogleGenAI;
  private model: string;
  private embeddingDims: number | undefined;
  private readonly apiKey: string | undefined;

  constructor(config: EmbeddingConfig) {
    this.apiKey = config.apiKey || process.env.GOOGLE_API_KEY;
    this.model = config.model || "gemini-embedding-001";
    this.embeddingDims = config.embeddingDims;
  }

  private async ensureClient(): Promise<void> {
    if (this.google) return;
    const sdk = await loadPeer(
      "@google/genai",
      "Google embedder",
      () => import("@google/genai"),
    );
    this.google = new sdk.GoogleGenAI({ apiKey: this.apiKey });
  }

  async embed(text: string): Promise<number[]> {
    await this.ensureClient();
    const response = await this.google.models.embedContent({
      model: this.model,
      contents: text,
      ...(this.embeddingDims !== undefined && {
        config: { outputDimensionality: this.embeddingDims },
      }),
    });
    return response.embeddings![0].values!;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    await this.ensureClient();
    const response = await this.google.models.embedContent({
      model: this.model,
      // Pass each text as its own content part. The GenAI SDK normalizes a
      // plain string array into a single multipart content item, so models
      // like gemini-embedding-002 return one combined vector instead of one
      // vector per text (see issue #7488).
      contents: texts.map((text) => ({ parts: [{ text }] })),
      ...(this.embeddingDims !== undefined && {
        config: { outputDimensionality: this.embeddingDims },
      }),
    });
    const embeddings = response.embeddings ?? [];
    if (embeddings.length !== texts.length) {
      throw new Error(
        `Google embedBatch() returned ${embeddings.length} embeddings for ${texts.length} texts using model '${this.model}'`,
      );
    }
    return embeddings.map((item) => item.values!);
  }
}
