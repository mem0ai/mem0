/// <reference types="jest" />
import OpenAI from "openai";
import { OpenAIEmbedder } from "../src/embeddings/openai";

jest.mock("openai", () => {
  return {
    __esModule: true,
    default: jest.fn().mockImplementation(() => ({
      embeddings: {
        create: jest.fn(),
      },
    })),
  };
});

describe("OpenAIEmbedder", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("passes baseURL to OpenAI client when provided", () => {
    new OpenAIEmbedder({
      apiKey: "test-key",
      baseURL: "https://integrate.api.nvidia.com/v1",
      model: "text-embedding-3-small",
    });

    expect(OpenAI).toHaveBeenCalledWith({
      apiKey: "test-key",
      baseURL: "https://integrate.api.nvidia.com/v1",
    });
  });

  it("still initializes when baseURL is omitted", () => {
    new OpenAIEmbedder({
      apiKey: "test-key",
      model: "text-embedding-3-small",
    });

    expect(OpenAI).toHaveBeenCalledWith({
      apiKey: "test-key",
      baseURL: undefined,
    });
  });
});
