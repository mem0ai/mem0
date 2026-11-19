/// <reference types="jest" />
/**
 * Unit tests for parse_vision_messages (utils/memory.ts).
 *
 * Covers two parity fixes vs the Python parse_vision_messages:
 *  - system messages are preserved (not silently dropped);
 *  - image description uses the configured LLM, not a hardcoded OpenAI client.
 */
import { parse_vision_messages } from "../src/utils/memory";
import type { LLM } from "../src/llms/base";
import type { Message } from "../src/types";

function fakeLlm(description = "a photo of a cat"): LLM & {
  generateResponse: jest.Mock;
} {
  return {
    generateResponse: jest.fn().mockResolvedValue(description),
    generateChat: jest.fn(),
  } as any;
}

describe("parse_vision_messages", () => {
  it("preserves system messages instead of dropping them", async () => {
    const messages: Message[] = [
      { role: "system", content: "You summarize concisely." },
      { role: "user", content: "I love hiking." },
    ];

    const result = await parse_vision_messages(messages);

    expect(result).toEqual(messages);
  });

  it("passes plain user/assistant messages through unchanged", async () => {
    const messages: Message[] = [
      { role: "user", content: "hi" },
      { role: "assistant", content: "hello" },
    ];

    const result = await parse_vision_messages(messages);

    expect(result).toEqual(messages);
  });

  it("describes an image with the configured LLM (not a hardcoded OpenAI client)", async () => {
    const llm = fakeLlm("a golden retriever on a beach");
    const messages: Message[] = [
      {
        role: "user",
        content: {
          type: "image_url",
          image_url: { url: "https://example.com/dog.jpg" },
        },
      },
    ];

    const result = await parse_vision_messages(messages, llm);

    expect(llm.generateResponse).toHaveBeenCalledTimes(1);
    // The image_url is forwarded to the configured LLM for description.
    const sent = llm.generateResponse.mock.calls[0][0];
    expect(sent).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          content: {
            type: "image_url",
            image_url: { url: "https://example.com/dog.jpg" },
          },
        }),
      ]),
    );
    expect(result).toEqual([
      { role: "user", content: "a golden retriever on a beach" },
    ]);
  });

  it("keeps a system message alongside an image message", async () => {
    const llm = fakeLlm("a sunset");
    const messages: Message[] = [
      { role: "system", content: "Describe vividly." },
      {
        role: "user",
        content: {
          type: "image_url",
          image_url: { url: "https://example.com/sunset.jpg" },
        },
      },
    ];

    const result = await parse_vision_messages(messages, llm);

    expect(result).toEqual([
      { role: "system", content: "Describe vividly." },
      { role: "user", content: "a sunset" },
    ]);
  });

  it("throws when an image_url content part is missing its url", async () => {
    const llm = fakeLlm();
    const messages: Message[] = [
      {
        role: "user",
        content: { type: "image_url", image_url: { url: "" } },
      },
    ];

    await expect(parse_vision_messages(messages, llm)).rejects.toThrow(
      /missing image_url\.url/,
    );
  });
});
