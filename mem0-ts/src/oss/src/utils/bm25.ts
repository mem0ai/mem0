export class BM25 {
  private documents: string[][];
  private k1: number;
  private b: number;
  private avgDocLength: number;
  private docFreq: Map<string, number>;
  private docLengths: number[];
  private idf: Map<string, number>;

  constructor(documents: string[][], k1 = 1.5, b = 0.75) {
    this.documents = documents;
    this.k1 = k1;
    this.b = b;
    this.docLengths = documents.map((doc) => doc.length);
    this.avgDocLength =
      this.docLengths.reduce((a, b) => a + b, 0) / documents.length;
    this.docFreq = new Map();
    this.idf = new Map();
    this.computeIdf();
  }

  private computeIdf() {
    const N = this.documents.length;

    // Count document frequency for each term
    for (const doc of this.documents) {
      const terms = new Set(doc);
      for (const term of terms) {
        this.docFreq.set(term, (this.docFreq.get(term) || 0) + 1);
      }
    }

    // Compute IDF for each term
    for (const [term, freq] of this.docFreq) {
      this.idf.set(term, Math.log((N - freq + 0.5) / (freq + 0.5) + 1));
    }
  }

  private score(query: string[], doc: string[], index: number): number {
    let score = 0;
    const docLength = this.docLengths[index];

    for (const term of query) {
      const tf = doc.filter((t) => t === term).length;
      const idf = this.idf.get(term) || 0;

      score +=
        (idf * tf * (this.k1 + 1)) /
        (tf +
          this.k1 * (1 - this.b + (this.b * docLength) / this.avgDocLength));
    }

    return score;
  }

  search(query: string[]): string[][] {
    const scores = this.documents.map((doc, idx) => ({
      doc,
      score: this.score(query, doc, idx),
    }));

    return scores.sort((a, b) => b.score - a.score).map((item) => item.doc);
  }
}
