import { lemmatizeForBm25 } from "../src/utils/lemmatization";

describe("lemmatizeForBm25", () => {
  const originalSegmenter = Intl.Segmenter;

  afterEach(() => {
    Object.defineProperty(Intl, "Segmenter", {
      value: originalSegmenter,
      configurable: true,
      writable: true,
    });
  });

  it("handles basic English lemmatization with stemming", () => {
    const text = "He is running and eating apples";
    const result = lemmatizeForBm25(text);
    expect(result).toContain("run");
    expect(result).toContain("running");
    expect(result).toContain("eat");
    expect(result).toContain("eating");
  });

  it("handles Chinese segmentation using Intl.Segmenter", () => {
    const text = "我喜歡寫程式";
    const result = lemmatizeForBm25(text, ["zh-TW"]);
    // Verify it gets split into separate terms by verifying the presence of spaces
    expect(result.split(" ").length).toBeGreaterThan(1);
  });

  it("handles custom locales overriding default locale lists", () => {
    const text = "ภาษาไทย";
    const result = lemmatizeForBm25(text, ["th"]);
    expect(result).toContain("ภาษา");
  });

  it("falls back to regex segmenter when Intl.Segmenter is undefined", () => {
    Object.defineProperty(Intl, "Segmenter", {
      value: undefined,
      configurable: true,
      writable: true,
    });

    const text = "He is running and eating apples";
    const result = lemmatizeForBm25(text);
    expect(result).toContain("run");
    expect(result).toContain("running");

    const chineseText = "我喜歡寫程式";
    const chineseResult = lemmatizeForBm25(chineseText);
    expect(chineseResult).toBe("我喜歡寫程式");
  });
});
