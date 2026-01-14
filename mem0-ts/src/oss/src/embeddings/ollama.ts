import type { Ollama } from "ollama";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";
import { logger } from "../utils/logger";

let OllamaClient: typeof Ollama | null = null;

async function getOllamaClient(): Promise<typeof Ollama> {
  if (!OllamaClient) {
    try {
      const ollamaModule = await import("ollama");
      OllamaClient = ollamaModule.Ollama;
    } catch (error) {
      throw new Error(
        "The 'ollama' package is required to use Ollama provider. " +
          "Please install it with: npm install ollama"
      );
    }
  }
  return OllamaClient;
}

export class OllamaEmbedder implements Embedder {
  private ollama: Ollama | null = null;
  private model: string;
  private embeddingDims?: number;
  private host: string;
  // Using this variable to avoid calling the Ollama server multiple times
  private initialized: boolean = false;

  constructor(config: EmbeddingConfig) {
    this.host = config.url || "http://localhost:11434";
    this.model = config.model || "nomic-embed-text:latest";
    this.embeddingDims = config.embeddingDims || 768;
  }

  private async getClient(): Promise<Ollama> {
    if (!this.ollama) {
      const OllamaClass = await getOllamaClient();
      this.ollama = new OllamaClass({ host: this.host });
    }
    return this.ollama;
  }

  async embed(text: string): Promise<number[]> {
    const ollama = await this.getClient();
    try {
      await this.ensureModelExists(ollama);
    } catch (err) {
      logger.error(`Error ensuring model exists: ${err}`);
    }
    const response = await ollama.embeddings({
      model: this.model,
      prompt: text,
    });
    return response.embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await Promise.all(texts.map((text) => this.embed(text)));
    return response;
  }

  private async ensureModelExists(ollama: Ollama): Promise<boolean> {
    if (this.initialized) {
      return true;
    }
    const local_models = await ollama.list();
    if (!local_models.models.find((m: any) => m.name === this.model)) {
      logger.info(`Pulling model ${this.model}...`);
      await ollama.pull({ model: this.model });
    }
    this.initialized = true;
    return true;
  }
}
