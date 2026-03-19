import { Ollama } from "ollama";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";
import { logger } from "../utils/logger";

export class OllamaEmbedder implements Embedder {
  private ollama: Ollama;
  private model: string;
  private embeddingDims?: number;
  // Using this variable to avoid calling the Ollama server multiple times
  private initialized: boolean = false;

  constructor(config: EmbeddingConfig) {
    this.ollama = new Ollama({
      host: config.url || config.baseURL || "http://localhost:11434",
    });
    this.model = config.model || "nomic-embed-text:latest";
    this.embeddingDims = config.embeddingDims || 768;
    this.ensureModelExists().catch((err) => {
      logger.error(`Error ensuring model exists: ${err}`);
    });
  }

  async embed(text: string): Promise<number[]> {
    try {
      await this.ensureModelExists();
    } catch (err) {
      logger.error(`Error ensuring model exists: ${err}`);
    }
    // Coerce defensively since callers may pass values parsed from untrusted LLM JSON output.
    const input = typeof text === "string" ? text : JSON.stringify(text);
    const response = await this.ollama.embed({
      model: this.model,
      input,
    });
    if (!response.embeddings || response.embeddings.length === 0) {
      throw new Error(
        `Ollama embed() returned no embeddings for model '${this.model}'`,
      );
    }
    return response.embeddings[0];
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await Promise.all(texts.map((text) => this.embed(text)));
    return response;
  }

  private static normalizeModelName(name: string): string {
    return name.includes(":") ? name : `${name}:latest`;
  }

  private async ensureModelExists(): Promise<boolean> {
    if (this.initialized) {
      return true;
    }
    const local_models = await this.ollama.list();
    const target = OllamaEmbedder.normalizeModelName(this.model);
    if (
      !local_models.models.find(
        (m: any) => OllamaEmbedder.normalizeModelName(m.name) === target,
      )
    ) {
      logger.info(`Pulling model ${this.model}...`);
      await this.ollama.pull({ model: this.model });
    }
    this.initialized = true;
    return true;
  }
}
