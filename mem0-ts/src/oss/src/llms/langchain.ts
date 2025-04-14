import { BaseLanguageModel } from "@langchain/core/language_models/base";
import {
  AIMessage,
  HumanMessage,
  SystemMessage,
  BaseMessage,
} from "@langchain/core/messages";
import { LLM, LLMResponse } from "./base";
import { LLMConfig, Message } from "../types/index"; // Corrected import path

// Helper to convert mem0 messages to Langchain messages
const convertToLangchainMessages = (messages: Message[]): BaseMessage[] => {
  return messages.map((msg) => {
    // Langchain messages expect string content. Stringify complex content for now.
    const content =
      typeof msg.content === "string"
        ? msg.content
        : JSON.stringify(msg.content);
    switch (msg.role?.toLowerCase()) {
      case "system":
        return new SystemMessage(content);
      case "user":
      case "human": // Allow 'human' role as well
        return new HumanMessage(content);
      case "assistant":
      case "ai": // Allow 'ai' role
        return new AIMessage(content);
      // TODO: Add support for ToolMessage if needed
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
  private modelName: string; // Store model name if available

  constructor(config: LLMConfig) {
    // Check if config.model is provided and is an object (the instance)
    if (!config.model || typeof config.model !== "object") {
      throw new Error(
        "Langchain provider requires an initialized Langchain instance passed via the 'model' field in the LLM config.",
      );
    }
    // Basic check for an invoke method to ensure it's likely a Langchain model
    if (typeof (config.model as any).invoke !== "function") {
      throw new Error(
        "Provided Langchain 'instance' in the 'model' field does not appear to be a valid Langchain language model (missing invoke method).",
      );
    }
    this.llmInstance = config.model as BaseLanguageModel;
    // Attempt to get a model name identifier if available, otherwise use a placeholder
    // If config.model is the instance, we might try to access an identifier on it, or use a default
    this.modelName =
      (this.llmInstance as any).modelId ||
      (this.llmInstance as any).model ||
      "langchain-model";
  }

  async generateResponse(
    messages: Message[],
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<string | LLMResponse> {
    const langchainMessages = convertToLangchainMessages(messages);
    let runnable = this.llmInstance;
    const invokeOptions: Record<string, any> = {};

    // --- Handle responseFormat (Experimental) ---
    // Langchain's approach varies. Some models accept 'response_format' in options,
    // others require .withStructuredOutput(). This is a basic attempt.
    if (responseFormat?.type === "json_object") {
      // Try adding to options (works for some models like OpenAI via Langchain)
      invokeOptions.response_format = { type: "json_object" };
      // Note: For guaranteed JSON, .withStructuredOutput(schema) is often needed.
      console.warn(
        "Requesting JSON format with LangchainLLM. Success depends on the specific model's capabilities and how it's wrapped. Consider using `.withStructuredOutput` on the Langchain instance if this fails.",
      );
    }

    // --- Handle tools (Experimental) ---
    // Langchain typically uses .bindTools() or equivalent attached to the model instance.
    if (tools && tools.length > 0) {
      if (typeof (runnable as any).bindTools === "function") {
        // This assumes the 'tools' format is compatible with Langchain's bindTools
        try {
          runnable = (runnable as any).bindTools(tools);
        } catch (e) {
          console.error(
            "Failed to bind tools to Langchain instance. Ensure 'tools' format is compatible.",
            e,
          );
          // Decide whether to proceed without tools or throw
          // Proceeding without tools for now
        }
      } else {
        console.warn(
          "The provided Langchain instance does not have a standard `.bindTools()` method. Tool calling may not function as expected.",
        );
      }
    }

    try {
      // Use invoke with converted messages and any derived options
      const response = await runnable.invoke(langchainMessages, invokeOptions);

      // Process Langchain response (typically a BaseMessage: AIMessage, etc.)
      if (response && typeof response.content === "string") {
        const responseContent = response.content;
        // Check for tool calls (structure depends on model/Langchain version)
        // Common patterns: response.tool_calls or response.additional_kwargs?.tool_calls
        const toolCallsData =
          (response as any).tool_calls ||
          (response as any).additional_kwargs?.tool_calls;

        if (
          toolCallsData &&
          Array.isArray(toolCallsData) &&
          toolCallsData.length > 0
        ) {
          // Map Langchain tool calls to mem0 LLMResponse format
          const mappedToolCalls = toolCallsData.map((call: any) => ({
            name: call.name || call.id || "unknown_tool", // Adapt as needed
            // Langchain tool 'args' can be object or string
            arguments:
              typeof call.args === "string"
                ? call.args
                : JSON.stringify(call.args),
          }));

          return {
            content: responseContent, // May be empty if only tool calls exist
            role: "assistant", // Langchain messages have 'type', map to role
            toolCalls: mappedToolCalls,
          };
        } else {
          // No tool calls detected, return plain content
          return responseContent;
        }
      } else {
        // Handle cases where response or response.content isn't as expected
        console.warn(
          "Unexpected response format from Langchain instance:",
          response,
        );
        // Fallback: stringify the whole response object
        return JSON.stringify(response);
      }
    } catch (error) {
      console.error(
        `Error invoking Langchain instance (${this.modelName}):`,
        error,
      );
      throw error; // Re-throw the error after logging
    }
  }

  // generateChat is often simpler, focusing on conversational exchange
  async generateChat(messages: Message[]): Promise<LLMResponse> {
    const langchainMessages = convertToLangchainMessages(messages);
    try {
      // Invoke the core LLM instance without specific format/tool options
      const response = await this.llmInstance.invoke(langchainMessages);

      if (response && typeof response.content === "string") {
        return {
          content: response.content,
          // Determine role from Langchain message type if possible, default to assistant
          role: (response as BaseMessage).lc_id ? "assistant" : "assistant",
        };
      } else {
        console.warn(
          `Unexpected response format from Langchain instance (${this.modelName}) for generateChat:`,
          response,
        );
        return {
          content: JSON.stringify(response), // Fallback
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
