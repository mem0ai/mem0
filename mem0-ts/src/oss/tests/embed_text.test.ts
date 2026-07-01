/// <reference types="jest" />
import {
  DEFAULT_EMBED_TOKEN_LIMIT,
  truncateTextToTokenLimit,
} from "../src/utils/embed_text";

describe("truncateTextToTokenLimit", () => {
  it("returns short text unchanged", () => {
    const text = "user: hello\n";
    expect(truncateTextToTokenLimit(text)).toBe(text);
  });

  it("truncates long text using char budget", () => {
    const longText = "x".repeat(DEFAULT_EMBED_TOKEN_LIMIT * 4 + 100);
    const truncated = truncateTextToTokenLimit(longText);
    expect(truncated.length).toBe(DEFAULT_EMBED_TOKEN_LIMIT * 4);
  });
});
