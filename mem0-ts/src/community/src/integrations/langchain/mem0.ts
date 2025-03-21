import { MemoryClient } from "mem0ai";
import type { Memory, MemoryOptions, SearchOptions } from "mem0ai";

import {
  InputValues,
  OutputValues,
  MemoryVariables,
  getInputValue,
  getOutputValue,
} from "@langchain/core/memory";
import {
  AIMessage,
  BaseMessage,
  ChatMessage,
  getBufferString,
  HumanMessage,
  SystemMessage,
} from "@langchain/core/messages";
import {
  BaseChatMemory,
  BaseChatMemoryInput,
} from "@langchain/community/memory/chat_memory";

/**
 * Extracts and formats memory content into a system prompt
 * @param memory Array of Memory objects from mem0ai
 * @returns Formatted system prompt string
 */
export const mem0MemoryContextToSystemPrompt = (memory: Memory[]): string => {
  if (!memory || !Array.isArray(memory)) {
    return "";
  }

  return memory
    .filter((m) => m?.memory)
    .map((m) => m.memory)
    .join("\n");
};

/**
 * Condenses memory content into a single HumanMessage with context
 * @param memory Array of Memory objects from mem0ai
 * @returns HumanMessage containing formatted memory context
 */
export const condenseMem0MemoryIntoHumanMessage = (
  memory: Memory[],
): HumanMessage => {
  const basePrompt =
    "These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The MEMORIES of the USER are: \n\n";
  const systemPrompt = mem0MemoryContextToSystemPrompt(memory);

  return new HumanMessage(`${basePrompt}\n${systemPrompt}`);
};

/**
 * Converts Mem0 memories to a list of BaseMessages
 * @param memories Array of Memory objects from mem0ai
 * @returns Array of BaseMessage objects
 */
export const mem0MemoryToMessages = (memories: Memory[]): BaseMessage[] => {
  if (!memories || !Array.isArray(memories)) {
    return [];
  }

  const messages: BaseMessage[] = [];

  // Add memories as system message if present
  const memoryContent = memories
    .filter((m) => m?.memory)
    .map((m) => m.memory)
    .join("\n");

  if (memoryContent) {
    messages.push(new SystemMessage(memoryContent));
  }

  // Add conversation messages
  memories.forEach((memory) => {
    if (memory.messages) {
      memory.messages.forEach((msg) => {
        const content =
          typeof msg.content === "string"
            ? msg.content
            : JSON.stringify(msg.content);
        if (msg.role === "user") {
          messages.push(new HumanMessage(content));
        } else if (msg.role === "assistant") {
          messages.push(new AIMessage(content));
        } else if (content) {
          messages.push(new ChatMessage(content, msg.role));
        }
      });
    }
  });

  return messages;
};

/**
 * Interface defining the structure of the input data for the Mem0Client
 */
export interface ClientOptions {
  apiKey: string;
  host?: string;
  organizationName?: string;
  projectName?: string;
  organizationId?: string;
  projectId?: string;
}

/**
 * Interface defining the structure of the input data for the Mem0Memory
 * class. It includes properties like memoryKey, sessionId, and apiKey.
 */
export interface Mem0MemoryInput extends BaseChatMemoryInput {
  sessionId: string;
  apiKey: string;
  humanPrefix?: string;
  aiPrefix?: string;
  memoryOptions?: MemoryOptions | SearchOptions;
  mem0Options?: ClientOptions;
  separateMessages?: boolean;
}

/**
 * Class used to manage the memory of a chat session using the Mem0 service.
 * It handles loading and saving chat history, and provides methods to format
 * the memory content for use in chat models.
 *
 * @example
 * ```typescript
 * const memory = new Mem0Memory({
 *   sessionId: "user123" // or use user_id inside of memoryOptions (recommended),
 *   apiKey: "your-api-key",
 *   memoryOptions: {
 *     user_id: "user123",
 *     run_id: "run123"
 *   },
 * });
 *
 * // Use with a chat model
 * const model = new ChatOpenAI({
 *   modelName: "gpt-3.5-turbo",
 *   temperature: 0,
 * });
 *
 * const chain = new ConversationChain({ llm: model, memory });
 * ```
 */
export class Mem0Memory extends BaseChatMemory implements Mem0MemoryInput {
  memoryKey = "history";

  apiKey: string;

  sessionId: string;

  humanPrefix = "Human";

  aiPrefix = "AI";

  mem0Client: InstanceType<typeof MemoryClient>;

  memoryOptions: MemoryOptions | SearchOptions;

  mem0Options: ClientOptions;

  // Whether to return separate messages for chat history with a SystemMessage containing (facts and summary) or return a single HumanMessage with the entire memory context.
  // Defaults to false (return a single HumanMessage) in order to allow more flexibility with different models.
  separateMessages?: boolean;

  constructor(fields: Mem0MemoryInput) {
    if (!fields.apiKey) {
      throw new Error("apiKey is required for Mem0Memory");
    }
    if (!fields.sessionId) {
      throw new Error("sessionId is required for Mem0Memory");
    }

    super({
      returnMessages: fields?.returnMessages ?? false,
      inputKey: fields?.inputKey,
      outputKey: fields?.outputKey,
    });

    this.apiKey = fields.apiKey;
    this.sessionId = fields.sessionId;
    this.humanPrefix = fields.humanPrefix ?? this.humanPrefix;
    this.aiPrefix = fields.aiPrefix ?? this.aiPrefix;
    this.memoryOptions = fields.memoryOptions ?? {};
    this.mem0Options = fields.mem0Options ?? {
      apiKey: this.apiKey,
    };
    this.separateMessages = fields.separateMessages ?? false;
    try {
      this.mem0Client = new MemoryClient({
        ...this.mem0Options,
        apiKey: this.apiKey,
      });
    } catch (error) {
      console.error("Failed to initialize Mem0Client:", error);
      throw new Error(
        "Failed to initialize Mem0Client. Please check your configuration.",
      );
    }
  }

  get memoryKeys(): string[] {
    return [this.memoryKey];
  }

  /**
   * Retrieves memories from the Mem0 service and formats them for use
   * @param values Input values containing optional search query
   * @returns Promise resolving to formatted memory variables
   */
  async loadMemoryVariables(values: InputValues): Promise<MemoryVariables> {
    const searchType = values.input ? "search" : "get_all";
    let memories: Memory[] = [];

    try {
      if (searchType === "get_all") {
        memories = await this.mem0Client.getAll({
          user_id: this.sessionId,
          ...this.memoryOptions,
        });
      } else {
        memories = await this.mem0Client.search(values.input, {
          user_id: this.sessionId,
          ...this.memoryOptions,
        });
      }
    } catch (error) {
      console.error("Error loading memories:", error);
      return this.returnMessages
        ? { [this.memoryKey]: [] }
        : { [this.memoryKey]: "" };
    }

    if (this.returnMessages) {
      return {
        [this.memoryKey]: this.separateMessages
          ? mem0MemoryToMessages(memories)
          : [condenseMem0MemoryIntoHumanMessage(memories)],
      };
    }

    return {
      [this.memoryKey]: this.separateMessages
        ? getBufferString(
            mem0MemoryToMessages(memories),
            this.humanPrefix,
            this.aiPrefix,
          )
        : (condenseMem0MemoryIntoHumanMessage(memories).content ?? ""),
    };
  }

  /**
   * Saves the current conversation context to the Mem0 service
   * @param inputValues Input messages to be saved
   * @param outputValues Output messages to be saved
   * @returns Promise resolving when the context has been saved
   */
  async saveContext(
    inputValues: InputValues,
    outputValues: OutputValues,
  ): Promise<void> {
    const input = getInputValue(inputValues, this.inputKey);
    const output = getOutputValue(outputValues, this.outputKey);

    if (!input || !output) {
      console.warn("Missing input or output values, skipping memory save");
      return;
    }

    try {
      const messages = [
        {
          role: "user",
          content: `${input}`,
        },
        {
          role: "assistant",
          content: `${output}`,
        },
      ];

      await this.mem0Client.add(messages, {
        user_id: this.sessionId,
        ...this.memoryOptions,
      });
    } catch (error) {
      console.error("Error saving memory context:", error);
      // Continue execution even if memory save fails
    }

    await super.saveContext(inputValues, outputValues);
  }

  /**
   * Clears all memories for the current session
   * @returns Promise resolving when memories have been cleared
   */
  async clear(): Promise<void> {
    try {
      // Note: Implement clear functionality if Mem0Client provides it
      // await this.mem0Client.clear(this.sessionId);
    } catch (error) {
      console.error("Error clearing memories:", error);
    }

    await super.clear();
  }
}
