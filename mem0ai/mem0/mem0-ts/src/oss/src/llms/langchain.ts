import { BaseLanguageModel } from "@langchain/core/language_models/base";
import {
  AIMessage,
  HumanMessage,
  SystemMessage,
  BaseMessage,
} from "@langchain/core/messages";
import { z } from "zod";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types/index";
// Import the schemas directly into LangchainLLM
import { FactRetrievalSchema, MemoryUpdateSchema } from "../prompts";
// Import graph tool argument schemas
import {
  GraphExtractEntitiesArgsSchema,
  GraphRelationsArgsSchema,
  GraphSimpleRelationshipArgsSchema, // Used for delete tool
} from "../graphs/tools";

const convertToLangchainMessages = (messages: Message[]): BaseMessage[] => {
  return messages.map((msg) => {
    const content =
      typeof msg.content === "string"
        ? msg.content
        : JSON.stringify(msg.content);
    switch (msg.role?.toLowerCase()) {
      case "system":
        return new SystemMessage(content);
      case "user":
      case "human":
        return new HumanMessage(content);
      case "assistant":
      case "ai":
        return new AIMessage(content);
      default:
        console.warn(
          `Unsupported message role '${msg.role}' for Langchain. Treating as 'human'.`,
        );
        return new HumanMessage(content);
    }
  });
};

export class LangchainLLM implements LLM {
  private llmInstance: BaseLanguageModel;
  private modelName: string;

  constructor(config: LLMConfig) {
    if (!config.model || typeof config.model !== "object") {
      throw new Error(
        "Langchain provider requires an initialized Langchain instance passed via the 'model' field in the LLM config.",
      );
    }
    if (typeof (config.model as any).invoke !== "function") {
      throw new Error(
        "Provided Langchain 'instance' in the 'model' field does not appear to be a valid Langchain language model (missing invoke method).",
      );
    }
    this.llmInstance = config.model as BaseLanguageModel;
    this.modelName =
      (this.llmInstance as any).modelId ||
      (this.llmInstance as any).model ||
      "langchain-model";
  }

  async generateResponse(
    messages: Message[],
    response_format?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const langchainMessages = convertToLangchainMessages(messages);
    let runnable: any = this.llmInstance;
    const invokeOptions: Record<string, any> = {};
    let isStructuredOutput = false;
    let selectedSchema: z.ZodSchema<any> | null = null;
    let isToolCallResponse = false;

    // --- Internal Schema Selection Logic (runs regardless of response_format) ---
    const systemPromptContent =
      (messages.find((m) => m.role === "system")?.content as string) || "";
    const userPromptContent =
      (messages.find((m) => m.role === "user")?.content as string) || "";
    const toolNames = tools?.map((t) => t.function.name) || [];

    // Prioritize tool call argument schemas
    if (toolNames.includes("extract_entities")) {
      selectedSchema = GraphExtractEntitiesArgsSchema;
      isToolCallResponse = true;
    } else if (toolNames.includes("establish_relationships")) {
      selectedSchema = GraphRelationsArgsSchema;
      isToolCallResponse = true;
    } else if (toolNames.includes("delete_graph_memory")) {
      selectedSchema = GraphSimpleRelationshipArgsSchema;
      isToolCallResponse = true;
    }
    // Check for memory prompts if no tool schema matched
    else if (
      systemPromptContent.includes("Personal Information Organizer") &&
      systemPromptContent.includes("extract relevant pieces of information")
    ) {
      selectedSchema = FactRetrievalSchema;
    } else if (
      userPromptContent.includes("smart memory manager") &&
      userPromptContent.includes("Compare newly retrieved facts")
    ) {
      selectedSchema = MemoryUpdateSchema;
    }

    // --- Apply Structured Output if Schema Selected ---
    if (
      selectedSchema &&
      typeof (this.llmInstance as any).withStructuredOutput === "function"
    ) {
      // Apply if a schema was selected (for memory or single tool calls)
      if (
        !isToolCallResponse ||
        (isToolCallResponse && tools && tools.length === 1)
      ) {
        try {
          runnable = (this.llmInstance as any).withStructuredOutput(
            selectedSchema,
            { name: tools?.[0]?.function.name },
          );
          isStructuredOutput = true;
        } catch (e) {
          isStructuredOutput = false; // Ensure flag is false on error
          // No fallback to response_format here unless explicitly passed
          if (response_format?.type === "json_object") {
            invokeOptions.response_format = { type: "json_object" };
          }
        }
      } else if (isToolCallResponse) {
        // If multiple tools, don't apply structured output, handle via tool binding below
      }
    } else if (selectedSchema && response_format?.type === "json_object") {
      // Schema selected, but no .withStructuredOutput. Try basic response_format only if explicitly requested.
      if (
        (this.llmInstance as any)._identifyingParams?.response_format ||
        (this.llmInstance as any).response_format
      ) {
        invokeOptions.response_format = { type: "json_object" };
      }
    } else if (!selectedSchema && response_format?.type === "json_object") {
      // Explicit JSON request, but no schema inferred. Try basic response_format.
      if (
        (this.llmInstance as any)._identifyingParams?.response_format ||
        (this.llmInstance as any).response_format
      ) {
        invokeOptions.response_format = { type: "json_object" };
      }
    }

    // --- Handle tool binding ---
    if (tools && tools.length > 0) {
      if (typeof (runnable as any).bindTools === "function") {
        try {
          runnable = (runnable as any).bindTools(tools);
        } catch (e) {}
      } else {
      }
    }

    // --- Invoke and Process Response ---
    try {
      const response = await runnable.invoke(langchainMessages, invokeOptions);

      if (isStructuredOutput && !isToolCallResponse) {
        // Memory prompt with structured output
        return JSON.stringify(response);
      } else if (isStructuredOutput && isToolCallResponse) {
        // Tool call with structured arguments
        if (response?.tool_calls && Array.isArray(response.tool_calls)) {
          const mappedToolCalls = response.tool_calls.map((call: any) => ({
            name: call.name || tools?.[0]?.function.name || "unknown_tool",
            arguments:
              typeof call.args === "string"
                ? call.args
                : JSON.stringify(call.args),
          }));
          return {
            content: response.content || "",
            role: "assistant",
            toolCalls: mappedToolCalls,
          };
        } else {
          // Direct object response for tool args
          return {
            content: "",
            role: "assistant",
            toolCalls: [
              {
                name: tools?.[0]?.function.name || "unknown_tool",
                arguments: JSON.stringify(response),
              },
            ],
          };
        }
      } else if (
        response &&
        response.tool_calls &&
        Array.isArray(response.tool_calls)
      ) {
        // Standard tool call response (no structured output used/failed)
        const mappedToolCalls = response.tool_calls.map((call: any) => ({
          name: call.name || "unknown_tool",
          arguments:
            typeof call.args === "string"
              ? call.args
              : JSON.stringify(call.args),
        }));
        return {
          content: response.content || "",
          role: "assistant",
          toolCalls: mappedToolCalls,
        };
      } else if (response && typeof response.content === "string") {
        // Standard text response
        return response.content;
      } else {
        // Fallback for unexpected formats
        return JSON.stringify(response);
      }
    } catch (error) {
      throw error;
    }
  }

  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const langchainMessages = convertToLangchainMessages(messages);
    try {
      const response = await this.llmInstance.invoke(langchainMessages);
      if (response && typeof response.content === "string") {
        return {
          content: response.content,
          role: (response as BaseMessage).lc_id ? "assistant" : "assistant",
        };
      } else {
        console.warn(
          `Unexpected response format from Langchain instance (${this.modelName}) for generateChat:`,
          response,
        );
        return {
          content: JSON.stringify(response),
          role: "assistant",
        };
      }
    } catch (error) {
      console.error(
        `Error invoking Langchain instance (${this.modelName}) for generateChat:`,
        error,
      );
      throw error;
    }
  }
}
