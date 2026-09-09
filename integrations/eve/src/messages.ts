import type { MemoryMessage } from "./store.js";

export interface ConversationMessage {
  readonly role: string;
  readonly content: unknown;
}

export function extractText(content: unknown): string {
  if (typeof content === "string") {
    return content.trim();
  }
  if (!Array.isArray(content)) {
    return "";
  }

  return content
    .map((part) => {
      if (typeof part === "string") {
        return part;
      }
      if (part && typeof part === "object" && "text" in part) {
        const text = (part as { text: unknown }).text;
        return typeof text === "string" ? text : "";
      }
      return "";
    })
    .join("\n")
    .trim();
}

export function lastUserText(messages: readonly ConversationMessage[]): string {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.role !== "user") {
      continue;
    }
    const text = extractText(message.content);
    if (text.length > 0) {
      return text;
    }
  }
  return "";
}

export function conversationMessages(
  messages: readonly ConversationMessage[],
): MemoryMessage[] {
  const result: MemoryMessage[] = [];
  for (const message of messages) {
    if (message.role !== "user" && message.role !== "assistant") {
      continue;
    }
    const text = extractText(message.content);
    if (text.length === 0) {
      continue;
    }
    result.push({ role: message.role, content: text });
  }
  return result;
}

export function completedTurnMessages(input: {
  readonly messages: readonly ConversationMessage[];
  readonly turnInput: readonly ConversationMessage[];
}): MemoryMessage[] {
  const users = conversationMessages(input.turnInput).filter(
    (message) => message.role === "user",
  );
  if (users.length === 0) {
    return [];
  }

  const history = conversationMessages(input.messages);
  const lastAssistant = [...history]
    .reverse()
    .find((message) => message.role === "assistant");

  return lastAssistant ? [...users, lastAssistant] : users;
}
