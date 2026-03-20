import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";
import { loadOptionalDependency } from "../utils/optional-deps";

export class GoogleEmbedder implements Embedder {
  private google: any;
  private model: string;
  private embeddingDims?: number;

  constructor(config: EmbeddingConfig) {
    const GoogleGenAI = loadOptionalDependency<any>(
      "@google/genai",
      "Google embedding provider",
      "GoogleGenAI",
    );
    this.google = new GoogleGenAI({
      apiKey: config.apiKey || process.env.GOOGLE_API_KEY,
    });
    this.model = config.model || "gemini-embedding-001";
    this.embeddingDims = config.embeddingDims || 1536;
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.google.models.embedContent({
      model: this.model,
      contents: text,
      config: { outputDimensionality: this.embeddingDims },
    });
    return response.embeddings![0].values!;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await this.google.models.embedContent({
      model: this.model,
      contents: texts,
      config: { outputDimensionality: this.embeddingDims },
    });
    return response.embeddings!.map((item: any) => item.values!);
  }
}
