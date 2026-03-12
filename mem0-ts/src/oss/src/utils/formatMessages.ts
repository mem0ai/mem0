import type { Message } from "../types";

/**
 * Formats messages with role labels preserved, mapping roles to real names
 * when provided. Without roleNames, defaults to "user"/"assistant" prefixes
 * (still better than stripping roles entirely).
 */
export const formatMessagesWithRoles = (
  messages: Message[],
  roleNames?: { user?: string; assistant?: string },
): string => {
  const nameMap: Record<string, string> = {
    user: roleNames?.user ?? "user",
    assistant: roleNames?.assistant ?? "assistant",
    system: "system",
  };
  return messages
    .filter((m) => typeof m.content === "string")
    .map((m) => `${nameMap[m.role] ?? m.role}: ${m.content}`)
    .join("\n");
};
