import OpenAI from "openai";
import { XAILLM } from "../llms/xai";
import { LLMFactory } from "../utils/factory";

jest.mock("openai");

const createMock = jest.fn();
const OpenAIMock = OpenAI as unknown as jest.Mock;

describe("XAILLM", () => {
  const ORIGINAL_ENV = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...ORIGINAL_ENV };
    delete process.env.XAI_API_KEY;
    delete process.env.XAI_API_BASE;
    OpenAIMock.mockImplementation(() => ({
      chat: { completions: { create: createMock } },
    }));
    createMock.mockResolvedValue({
      choices: [{ message: { content: "hi", role: "assistant" } }],
    });
  });

  afterAll(() => {
    process.env = ORIGINAL_ENV;
  });

  it("defaults to grok-2-latest and the xAI base URL (matching the Python provider)", async () => {
    const llm = new XAILLM({ apiKey: "test-key" });
    const res = await llm.generateResponse([
      { role: "user", content: "hello" },
    ]);

    expect(OpenAIMock).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "test-key",
        baseURL: "https://api.x.ai/v1",
      }),
    );
    expect(createMock).toHaveBeenCalledWith(
      expect.objectContaining({ model: "grok-2-latest" }),
    );
    expect(res).toBe("hi");
  });

  it("reads XAI_API_KEY / XAI_API_BASE from the environment", () => {
    process.env.XAI_API_KEY = "env-key";
    process.env.XAI_API_BASE = "https://custom.x.ai/v1";

    new XAILLM({});

    expect(OpenAIMock).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "env-key",
        baseURL: "https://custom.x.ai/v1",
      }),
    );
  });

  it("honors explicit config over defaults and environment", async () => {
    process.env.XAI_API_KEY = "env-key";

    const llm = new XAILLM({
      apiKey: "explicit-key",
      baseURL: "https://proxy.example.com/v1",
      model: "grok-3",
    });
    await llm.generateResponse([{ role: "user", content: "hello" }]);

    expect(OpenAIMock).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "explicit-key",
        baseURL: "https://proxy.example.com/v1",
      }),
    );
    expect(createMock).toHaveBeenCalledWith(
      expect.objectContaining({ model: "grok-3" }),
    );
  });

  it("throws when no API key is configured", () => {
    expect(() => new XAILLM({})).toThrow("xAI API key is required");
  });

  it("wraps downstream failures with an xAI-specific message", async () => {
    createMock.mockRejectedValueOnce(new Error("boom"));
    const llm = new XAILLM({ apiKey: "test-key" });

    await expect(
      llm.generateResponse([{ role: "user", content: "hi" }]),
    ).rejects.toThrow("xAI LLM failed: boom");
  });

  it('is registered in the LLM factory under "xai"', () => {
    const llm = LLMFactory.create("xai", { apiKey: "test-key" });
    expect(llm).toBeInstanceOf(XAILLM);
  });
});
