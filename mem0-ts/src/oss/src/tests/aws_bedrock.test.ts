import { AWSBedrockLLM, extractProvider } from "../llms/aws_bedrock";

/**
 * Fake BedrockRuntimeClient capturing the Converse command input and returning
 * a scripted response — exercises request shaping + response parsing without
 * the AWS SDK or live credentials.
 */
class FakeBedrockClient {
  public lastInput: any = null;
  public response: any;
  constructor(response: any) {
    this.response = response;
  }
  async send(command: any) {
    // ConverseCommand stores its input on `.input` (mirrored by our fake command).
    this.lastInput = command?.input ?? command;
    return this.response;
  }
}

// The provider lazily requires the AWS SDK in its constructor. Mock the module
// so construction succeeds and ConverseCommand simply wraps its input.
jest.mock(
  "@aws-sdk/client-bedrock-runtime",
  () => ({
    BedrockRuntimeClient: class {
      constructor(public config: any) {}
    },
    ConverseCommand: class {
      input: any;
      constructor(input: any) {
        this.input = input;
      }
    },
    InvokeModelCommand: class {
      input: any;
      constructor(input: any) {
        this.input = input;
      }
    },
  }),
  { virtual: true },
);

function makeLLM(client: FakeBedrockClient, overrides: any = {}) {
  return new AWSBedrockLLM({
    model: "anthropic.claude-3-5-sonnet-20240620-v1:0",
    client,
    ...overrides,
  });
}

describe("extractProvider", () => {
  it("detects the model family from the Bedrock model id", () => {
    expect(extractProvider("anthropic.claude-3-5-sonnet-20240620-v1:0")).toBe(
      "anthropic",
    );
    expect(extractProvider("amazon.nova-pro-v1:0")).toBe("amazon");
    expect(extractProvider("meta.llama3-70b-instruct-v1:0")).toBe("meta");
    expect(extractProvider("mistral.mistral-large-2407-v1:0")).toBe("mistral");
  });

  it("throws on an unknown provider", () => {
    expect(() => extractProvider("totally-unknown-model")).toThrow(
      /Unknown provider/,
    );
  });
});

describe("AWSBedrockLLM", () => {
  const textResponse = {
    output: { message: { content: [{ text: "hello from bedrock" }] } },
  };

  it("returns assistant text from a Converse response", async () => {
    const client = new FakeBedrockClient(textResponse);
    const llm = makeLLM(client);
    const out = await llm.generateResponse([{ role: "user", content: "hi" }]);
    expect(out).toBe("hello from bedrock");
  });

  it("lifts system messages into the top-level system block", async () => {
    const client = new FakeBedrockClient(textResponse);
    const llm = makeLLM(client);
    await llm.generateResponse([
      { role: "system", content: "be terse" },
      { role: "user", content: "hi" },
    ]);
    expect(client.lastInput.system).toEqual([{ text: "be terse" }]);
    expect(client.lastInput.messages).toEqual([
      { role: "user", content: [{ text: "hi" }] },
    ]);
  });

  it("omits topP for anthropic models even when configured", async () => {
    const client = new FakeBedrockClient(textResponse);
    const llm = makeLLM(client, { topP: 0.9, temperature: 0.2 });
    await llm.generateResponse([{ role: "user", content: "hi" }]);
    expect(client.lastInput.inferenceConfig.topP).toBeUndefined();
    expect(client.lastInput.inferenceConfig.temperature).toBe(0.2);
  });

  it("includes topP for non-anthropic models", async () => {
    const client = new FakeBedrockClient(textResponse);
    const llm = makeLLM(client, {
      model: "meta.llama3-70b-instruct-v1:0",
      topP: 0.9,
    });
    await llm.generateResponse([{ role: "user", content: "hi" }]);
    expect(client.lastInput.inferenceConfig.topP).toBe(0.9);
  });

  it("converts OpenAI-style tools to Converse toolConfig and parses toolUse", async () => {
    const toolResponse = {
      output: {
        message: {
          content: [{ toolUse: { name: "add_memory", input: { text: "x" } } }],
        },
      },
    };
    const client = new FakeBedrockClient(toolResponse);
    const llm = makeLLM(client);
    const tools = [
      {
        type: "function",
        function: {
          name: "add_memory",
          description: "store a memory",
          parameters: { type: "object", properties: {} },
        },
      },
    ];
    const out = await llm.generateResponse(
      [{ role: "user", content: "remember x" }],
      undefined,
      tools,
    );
    expect(client.lastInput.toolConfig.tools[0].toolSpec.name).toBe(
      "add_memory",
    );
    expect(typeof out).toBe("object");
    expect((out as any).toolCalls[0]).toEqual({
      name: "add_memory",
      arguments: JSON.stringify({ text: "x" }),
    });
  });

  it("never sends an empty messages array", async () => {
    const client = new FakeBedrockClient(textResponse);
    const llm = makeLLM(client);
    await llm.generateResponse([{ role: "system", content: "only system" }]);
    expect(client.lastInput.messages).toEqual([
      { role: "user", content: [{ text: "" }] },
    ]);
  });

  it("wraps SDK errors with a provider-tagged message", async () => {
    const client = {
      send: async () => {
        throw new Error("AccessDeniedException");
      },
    } as any;
    const llm = makeLLM(client);
    await expect(
      llm.generateResponse([{ role: "user", content: "hi" }]),
    ).rejects.toThrow(/AWS Bedrock LLM failed: AccessDeniedException/);
  });

  it("generateChat returns text content with assistant role", async () => {
    const client = new FakeBedrockClient(textResponse);
    const llm = makeLLM(client);
    const res = await llm.generateChat([{ role: "user", content: "hi" }]);
    expect(res).toEqual({ content: "hello from bedrock", role: "assistant" });
  });

  describe("invoke_model API (#6023)", () => {
    // Fake client returning a raw JSON body string, as InvokeModel does.
    function makeInvokeClient(bodyObj: any) {
      return {
        lastInput: null as any,
        async send(command: any) {
          this.lastInput = command?.input ?? command;
          return { body: JSON.stringify(bodyObj) };
        },
      };
    }

    it("uses InvokeModel with an anthropic body and parses content", async () => {
      const client = makeInvokeClient({ content: [{ text: "legacy reply" }] });
      const llm = new AWSBedrockLLM({
        model: "anthropic.claude-v2",
        bedrockApi: "invoke_model",
        client: client as any,
      });
      const res = await llm.generateResponse([{ role: "user", content: "hi" }]);
      expect(res).toBe("legacy reply");
      const body = JSON.parse(client.lastInput.body);
      expect(body.anthropic_version).toBe("bedrock-2023-05-31");
      expect(client.lastInput.modelId).toBe("anthropic.claude-v2");
    });

    it("builds an ai21/j2 body and parses completions", async () => {
      const client = makeInvokeClient({
        completions: [{ data: { text: "j2 output" } }],
      });
      const llm = new AWSBedrockLLM({
        model: "ai21.j2-ultra-v1",
        bedrockApi: "invoke_model",
        client: client as any,
      });
      const res = await llm.generateChat([{ role: "user", content: "hi" }]);
      expect(res).toEqual({ content: "j2 output", role: "assistant" });
    });

    it("defaults to converse when bedrockApi is not set", async () => {
      const client = new FakeBedrockClient(textResponse);
      const llm = makeLLM(client);
      await llm.generateResponse([{ role: "user", content: "hi" }]);
      // Converse path stores modelId + messages (not a raw JSON body string).
      expect(client.lastInput.messages).toBeDefined();
      expect(client.lastInput.body).toBeUndefined();
    });
  });
});
