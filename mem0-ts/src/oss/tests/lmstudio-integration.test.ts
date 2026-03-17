/// <reference types="jest" />
/**
 * LM Studio integration tests against a real local server.
 * Skipped by default. Enable with: LMSTUDIO_INTEGRATION=1
 *
 * Prerequisites:
 *   1. LM Studio installed with `lms` CLI
 *   2. Server running:  lms server start
 *   3. Embedding model loaded:  lms load text-embedding-nomic-embed-text-v1.5
 *   4. (Optional) Chat model loaded for LLM tests
 */

import { LMStudioEmbedder } from "../src/embeddings/lmstudio";
import { LMStudioLLM } from "../src/llms/lmstudio";

const LMSTUDIO_BASE_URL =
  process.env.LMSTUDIO_BASE_URL || "http://localhost:1234/v1";
const RUN_INTEGRATION = process.env.LMSTUDIO_INTEGRATION === "1";
const describeIf = RUN_INTEGRATION ? describe : describe.skip;

jest.setTimeout(120_000);

async function listModels(): Promise<{
  embedding: string | null;
  chat: string | null;
}> {
  const res = await fetch(`${LMSTUDIO_BASE_URL}/models`);
  const body = await res.json();
  const models: any[] = body.data || [];
  const embedding = models.find(
    (m) => m.id.includes("embed") || m.id.includes("nomic"),
  );
  const chat = models.find(
    (m) => !m.id.includes("embed") && !m.id.includes("nomic"),
  );
  return { embedding: embedding?.id ?? null, chat: chat?.id ?? null };
}

function cosineSim(a: number[], b: number[]): number {
  let dot = 0,
    normA = 0,
    normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  return denom === 0 ? 0 : dot / denom;
}

describeIf("LM Studio Integration", () => {
  it("server is reachable and lists models", async () => {
    const res = await fetch(`${LMSTUDIO_BASE_URL}/models`);
    expect(res.ok).toBe(true);
    const body = await res.json();
    expect(body.data).toBeDefined();
    console.log(
      "Loaded models:",
      body.data.map((m: any) => m.id),
    );
  });

  // ─── Embedder ────────────────────────────────────────────────────────
  describe("LMStudioEmbedder (real server)", () => {
    let embedder: LMStudioEmbedder;
    let modelId: string;

    beforeAll(async () => {
      const models = await listModels();
      if (!models.embedding) throw new Error("No embedding model loaded");
      modelId = models.embedding;
      embedder = new LMStudioEmbedder({
        baseURL: LMSTUDIO_BASE_URL,
        model: modelId,
      });
    });

    it("embed() returns a numeric vector", async () => {
      const vector = await embedder.embed("Hello world");
      expect(Array.isArray(vector)).toBe(true);
      expect(vector.length).toBeGreaterThan(0);
      vector.forEach((v) => expect(typeof v).toBe("number"));
      console.log(`  Model: ${modelId}, dimension: ${vector.length}`);
    });

    it("embed() produces identical output for newline-normalized text", async () => {
      const v1 = await embedder.embed("hello world");
      const v2 = await embedder.embed("hello\nworld");
      expect(v1.length).toBe(v2.length);
      const totalDiff = v1.reduce((s, val, i) => s + Math.abs(val - v2[i]), 0);
      expect(totalDiff).toBeLessThan(0.001);
    });

    it("embedBatch() returns correct number of vectors", async () => {
      const vectors = await embedder.embedBatch(["first", "second", "third"]);
      expect(vectors).toHaveLength(3);
      vectors.forEach((v) => {
        expect(v.length).toBe(vectors[0].length);
        v.forEach((val) => expect(typeof val).toBe("number"));
      });
    });

    it("semantically similar texts have higher cosine similarity", async () => {
      const [v1, v2, v3] = await Promise.all([
        embedder.embed("I love hiking in the mountains"),
        embedder.embed("I enjoy trekking through mountain trails"),
        embedder.embed("The stock market crashed yesterday"),
      ]);
      const simSimilar = cosineSim(v1, v2);
      const simDifferent = cosineSim(v1, v3);
      console.log(
        `  Similar: ${simSimilar.toFixed(4)}, Different: ${simDifferent.toFixed(4)}`,
      );
      expect(Number.isFinite(simSimilar)).toBe(true);
      expect(Number.isFinite(simDifferent)).toBe(true);
      expect(simSimilar).toBeGreaterThan(simDifferent);
    });

    it("embed() handles empty string", async () => {
      const vector = await embedder.embed("");
      expect(Array.isArray(vector)).toBe(true);
      expect(vector.length).toBeGreaterThan(0);
    });

    it("embed() handles long text", async () => {
      const longText = "This is a test sentence. ".repeat(200);
      const vector = await embedder.embed(longText);
      expect(Array.isArray(vector)).toBe(true);
      expect(vector.length).toBeGreaterThan(0);
    });
  });

  // ─── LLM ─────────────────────────────────────────────────────────────
  describe("LMStudioLLM (real server)", () => {
    let llm: LMStudioLLM;
    let chatModelId: string | null;

    beforeAll(async () => {
      const models = await listModels();
      chatModelId = models.chat;
      if (!chatModelId) {
        console.warn("No chat model loaded — LLM tests will be skipped");
        return;
      }
      llm = new LMStudioLLM({ baseURL: LMSTUDIO_BASE_URL, model: chatModelId });
    });

    it("generateResponse() returns a response", async () => {
      if (!chatModelId) return;
      const result = await llm.generateResponse([
        { role: "user", content: "Say hello in exactly 3 words." },
      ]);
      if (typeof result === "string") {
        expect(result.length).toBeGreaterThan(0);
        console.log(`  Response (string): ${result.slice(0, 100)}`);
      } else {
        expect(result).toHaveProperty("content");
        expect(result.content.length).toBeGreaterThan(0);
        console.log(`  Response (object): ${result.content.slice(0, 100)}`);
      }
    });

    it("generateChat() returns LLMResponse with content and role", async () => {
      if (!chatModelId) return;
      const result = await llm.generateChat([
        { role: "user", content: "What is 2+2?" },
      ]);
      expect(result).toHaveProperty("content");
      expect(result).toHaveProperty("role");
      expect(result.role).toBe("assistant");
      expect(result.content.length).toBeGreaterThan(0);
      console.log(`  Chat: ${result.content.slice(0, 100)}`);
    });

    it("generateChat() handles multi-turn conversation", async () => {
      if (!chatModelId) return;
      const result = await llm.generateChat([
        { role: "user", content: "My name is Alice." },
        { role: "assistant", content: "Hello Alice!" },
        { role: "user", content: "What is my name?" },
      ]);
      expect(result.content.length).toBeGreaterThan(0);
      console.log(`  Multi-turn: ${result.content.slice(0, 100)}`);
    });
  });
});
