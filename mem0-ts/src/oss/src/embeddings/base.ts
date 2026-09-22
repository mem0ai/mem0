export interface Embedder {
  embed(
    text: string,
    memoryAction?: "add" | "update" | "search",
  ): Promise<number[]>;
  embedBatch(
    texts: string[],
    memoryAction?: "add" | "update" | "search",
  ): Promise<number[][]>;
}
