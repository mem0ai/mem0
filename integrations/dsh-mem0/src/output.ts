/**
 * Hard cap on tool output before it reaches the model context.
 *
 * Same guard the sibling plugins apply (200 lines / 50KB, see
 * integrations/pi-agent-plugin/src/memory/tools.ts): a large recall or a wide
 * result set can otherwise flood the context window in a single tool call.
 */

export const MAX_OUTPUT_LINES = 200;
export const MAX_OUTPUT_BYTES = 50_000;

export function truncateOutput(text: string): string {
  const lines = text.split("\n");
  if (lines.length <= MAX_OUTPUT_LINES && text.length <= MAX_OUTPUT_BYTES) {
    return text;
  }

  const kept = lines.slice(0, MAX_OUTPUT_LINES);
  let result = kept.join("\n");
  const byteCapped = result.length > MAX_OUTPUT_BYTES;
  if (byteCapped) {
    result = result.slice(0, MAX_OUTPUT_BYTES);
  }

  // Distinguish the two reasons: dropping whole lines vs. cutting mid-line at
  // the byte cap. Saying "showing N of N lines" while the text was cut mid-line
  // is misleading.
  const dropped = lines.length - kept.length;
  let reason: string | undefined;
  if (dropped > 0) {
    reason = `showing ${kept.length} of ${lines.length} lines`;
  } else if (byteCapped) {
    reason = `cut at ${Math.floor(MAX_OUTPUT_BYTES / 1000)}KB`;
  }
  if (reason) {
    result += `\n\n[Output truncated: ${reason}]`;
  }
  return result;
}
