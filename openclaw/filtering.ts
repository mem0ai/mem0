/**
 * Pre-extraction message filtering: noise detection, content stripping,
 * generic assistant detection, truncation, and deduplication.
 */

import type { MemoryItem } from "./types.ts";

// ============================================================================
// Noise Detection
// ============================================================================

/** Patterns that indicate an entire message is noise and should be dropped. */
const NOISE_MESSAGE_PATTERNS: RegExp[] = [
  /^(HEARTBEAT_OK|NO_REPLY)$/i,
  /^Current time:.*\d{4}/,
  /^Pre-compaction memory flush/i,
  /^(ok|yes|no|sir|sure|thanks|done|good|nice|cool|got it|it's on|continue)$/i,
  /^System: \[.*\] (Slack message edited|Gateway restart|Exec (failed|completed))/,
  /^System: \[.*\] ⚠️ Post-Compaction Audit:/,
];

/** Patterns for session-specific technical content that should not be stored as memories. */
const SESSION_SPECIFIC_PATTERNS: RegExp[] = [
  // Tool availability discussions
  /tools?\s+(are|is)\s+(not\s+)?(exposed|available|accessible)/i,
  /plugin\s+(does not|doesn't)\s+expose/i,
  /I\s+(do not|don't)\s+(currently\s+)?see\s+.*tools?\s+exposed/i,
  /memory_(search|get|add|update|delete|list)\s+(tool|is|are)/i,
  // Session-specific capability statements
  /in\s+this\s+session/i,
  /my\s+(live\s+)?callable\s+tool\s+registry/i,
  /tools?\s+I\s+(have|currently have)\s+access\s+to/i,
  // Plugin/capability status statements
  /openclaw-mem0\s+plugin/i,
  /memory\s+wiki.*capability/i,
  /workspace\s+memory\s+files/i,
];

/** Content fragments that should be stripped from otherwise-valid messages. */
const NOISE_CONTENT_PATTERNS: Array<{ pattern: RegExp; replacement: string }> =
  [
    {
      pattern:
        /Conversation info \(untrusted metadata\):\s*```json\s*\{[\s\S]*?\}\s*```/g,
      replacement: "",
    },
    {
      // OpenClaw TUI sends "Sender (untrusted metadata)" with a JSON block
      // containing label, id, name, username — strip to prevent storing as memory
      pattern:
        /Sender\s*\(untrusted metadata\):\s*```json[\s\S]*?```\s*/gi,
      replacement: "",
    },
    { pattern: /\[media attached:.*?\]/g, replacement: "" },
    {
      pattern:
        /To send an image back, prefer the message tool[\s\S]*?Keep caption in the text body\./g,
      replacement: "",
    },
    {
      pattern:
        /System: \[\d{4}-\d{2}-\d{2}.*?\] ⚠️ Post-Compaction Audit:[\s\S]*?after memory compaction\./g,
      replacement: "",
    },
    {
      pattern:
        /Replied message \(untrusted, for context\):\s*```json[\s\S]*?```/g,
      replacement: "",
    },
  ];

const MAX_MESSAGE_LENGTH = 2000;

/**
 * Patterns indicating an assistant message is a generic acknowledgment with
 * no extractable facts. These are produced when the agent receives a
 * transcript dump or forwarded message and responds with a boilerplate reply.
 */
const GENERIC_ASSISTANT_PATTERNS: RegExp[] = [
  /^(I see you'?ve shared|Thanks for sharing|Got it[.!]?\s*(I see|Let me|How can)|I understand[.!]?\s*(How can|Is there|Would you))/i,
  /^(How can I help|Is there anything|Would you like me to|Let me know (if|how|what))/i,
  /^(I('?ll| will) (help|assist|look into|review|take a look))/i,
  /^(Sure[.!]?\s*(How|What|Is)|Understood[.!]?\s*(How|What|Is))/i,
  /^(That('?s| is) (noted|understood|clear))/i,
];

// ============================================================================
// Public Functions
// ============================================================================

/**
 * Check whether a message's content is entirely noise (cron heartbeats,
 * single-word acknowledgments, system routing metadata, etc.).
 */
export function isNoiseMessage(content: string): boolean {
  const trimmed = content.trim();
  if (!trimmed) return true;
  return NOISE_MESSAGE_PATTERNS.some((p) => p.test(trimmed));
}

/**
 * Check whether a message contains session-specific technical content
 * that should not be stored (tool availability discussions, plugin
 * capability statements, etc.). These are facts about the current session
 * that have no value in future sessions.
 */
export function isSessionSpecificContent(content: string): boolean {
  const trimmed = content.trim();
  if (!trimmed) return false;
  // Check if multiple session-specific patterns match (more confident filtering)
  const matches = SESSION_SPECIFIC_PATTERNS.filter((p) => p.test(trimmed));
  return matches.length >= 2;
}

/**
 * Check whether an assistant message is a generic acknowledgment with no
 * extractable facts (e.g. "I see you've shared an update. How can I help?").
 * Only applies to short assistant messages — longer responses likely contain
 * substantive content even if they start with a generic opener.
 */
export function isGenericAssistantMessage(content: string): boolean {
  const trimmed = content.trim();
  // Only flag short messages — longer ones likely have substance after the opener
  if (trimmed.length > 300) return false;
  return GENERIC_ASSISTANT_PATTERNS.some((p) => p.test(trimmed));
}

/**
 * Remove embedded noise fragments (routing metadata, media boilerplate,
 * compaction audit blocks) from a message while preserving the useful content.
 */
export function stripNoiseFromContent(content: string): string {
  let cleaned = content;
  for (const { pattern, replacement } of NOISE_CONTENT_PATTERNS) {
    cleaned = cleaned.replace(pattern, replacement);
  }
  // Collapse excessive whitespace left behind after stripping
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n").trim();
  return cleaned;
}

/**
 * Truncate a message to `MAX_MESSAGE_LENGTH` characters, preserving the
 * opening (which typically contains the summary/conclusion) and appending
 * a truncation marker so the extraction model knows content was cut.
 */
function truncateMessage(content: string): string {
  if (content.length <= MAX_MESSAGE_LENGTH) return content;
  return content.slice(0, MAX_MESSAGE_LENGTH) + "\n[...truncated]";
}

/**
 * Full pre-extraction pipeline: drop noise messages, strip noise fragments,
 * filter session-specific content, and truncate remaining messages.
 */
export function filterMessagesForExtraction(
  messages: Array<{ role: string; content: string }>,
): Array<{ role: string; content: string }> {
  const filtered: Array<{ role: string; content: string }> = [];
  for (const msg of messages) {
    if (isNoiseMessage(msg.content)) continue;
    // Drop generic assistant acknowledgments that contain no facts
    if (msg.role === "assistant" && isGenericAssistantMessage(msg.content))
      continue;
    // Drop session-specific technical content (tool availability, plugin capabilities)
    if (isSessionSpecificContent(msg.content)) continue;
    const cleaned = stripNoiseFromContent(msg.content);
    if (!cleaned) continue;
    filtered.push({ role: msg.role, content: truncateMessage(cleaned) });
  }
  return filtered;
}
