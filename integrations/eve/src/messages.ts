import type { MemoryMessage } from "./store.js";

export interface ConversationMessage {
  readonly role: string;
  readonly content: unknown;
}

function textFromPart(part: unknown): string {
  if (typeof part === "string") {
    return part;
  }
  if (part && typeof part === "object") {
    const record = part as { type?: unknown; text?: unknown };
    // Typed parts must be explicit text. A `reasoning` part also carries a
    // `text` field, so accepting any object with `text` would leak the model's
    // private reasoning into long-term memory. Untyped `{ text }` (no `type`
    // key) stays supported for callers that pass a bare text object.
    if ("type" in record && record.type !== "text") {
      return "";
    }
    return typeof record.text === "string" ? record.text : "";
  }
  return "";
}

export function extractText(content: unknown): string {
  if (typeof content === "string") {
    return content.trim();
  }
  if (content && typeof content === "object" && !Array.isArray(content)) {
    return textFromPart(content).trim();
  }
  if (!Array.isArray(content)) {
    return "";
  }

  return content.map(textFromPart).join("\n").trim();
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

  // Pair this turn's users with the assistant reply produced *in this turn*
  // only. The current turn begins at the last user message in the settled
  // history; any assistant text after it belongs to this turn. Walking the
  // whole history instead would attach an older answer to the new user input
  // when this turn is tool-only (no assistant text of its own).
  let lastUserIndex = -1;
  for (let index = input.messages.length - 1; index >= 0; index -= 1) {
    if (input.messages[index]?.role === "user") {
      lastUserIndex = index;
      break;
    }
  }

  // Collect every assistant text segment produced in this turn, in order, so a
  // text -> tool-call -> text answer is captured whole rather than losing the
  // pre-tool content.
  const assistantSegments: string[] = [];
  if (lastUserIndex >= 0) {
    for (
      let index = lastUserIndex + 1;
      index < input.messages.length;
      index += 1
    ) {
      const message = input.messages[index];
      if (message?.role !== "assistant") {
        continue;
      }
      const text = extractText(message.content);
      if (text.length > 0) {
        assistantSegments.push(text);
      }
    }
  }

  const assistantText = assistantSegments.join("\n");
  return assistantText
    ? [...users, { role: "assistant", content: assistantText }]
    : users;
}
