/**
 * Per-agent memory isolation helpers.
 *
 * Multi-agent setups write/read from separate userId namespaces
 * automatically via sessionKey routing.
 */

// ============================================================================
// Trigger filtering — skip non-interactive sessions
// ============================================================================

/**
 * Triggers that should NOT run autocapture/autorecall.
 * These are system-initiated sessions (cron jobs, heartbeats, automation
 * pipelines) whose prompts would pollute the user's memory store.
 */
const SKIP_TRIGGERS = new Set(["cron", "heartbeat", "automation", "schedule"]);

/**
 * Returns true if the session trigger is non-interactive and memory
 * hooks should be skipped entirely.
 *
 * Also detects cron-style session keys (e.g. "agent:main:cron:<id>")
 * as a fallback when the trigger field is not set.
 */
export function isNonInteractiveTrigger(
  trigger: string | undefined,
  sessionKey: string | undefined,
): boolean {
  if (trigger && SKIP_TRIGGERS.has(trigger.toLowerCase())) return true;

  // Fallback: detect cron/heartbeat from the session key pattern
  if (sessionKey) {
    if (/:cron:/i.test(sessionKey) || /:heartbeat:/i.test(sessionKey))
      return true;
  }

  return false;
}

/**
 * Returns true if the session key indicates a subagent (ephemeral) session.
 * Subagent UUIDs are random per-spawn, so their namespaces are always empty
 * on recall and orphaned after capture.
 */
export function isSubagentSession(sessionKey: string | undefined): boolean {
  if (!sessionKey) return false;
  return /:subagent:/i.test(sessionKey);
}

/**
 * Parse an agent ID from a session key.
 *
 * OpenClaw session key formats:
 *   - Main agent:  "agent:main:main"
 *   - Subagent:    "agent:main:subagent:<uuid>"
 *   - Named agent: "agent:<agentId>:<session>"
 *
 * Returns the subagent UUID for subagent sessions, the agentId for
 * non-"main" named agents, or undefined for the main agent session.
 */
export function extractAgentId(
  sessionKey: string | undefined,
): string | undefined {
  if (!sessionKey) return undefined;

  // Check for subagent pattern: "agent:<parent>:subagent:<uuid>"
  const subagentMatch = sessionKey.match(/:subagent:([^:]+)$/);
  if (subagentMatch?.[1]) return `subagent-${subagentMatch[1]}`;

  // Check for named agent pattern: "agent:<agentId>:<session>"
  const match = sessionKey.match(/^agent:([^:]+):/);
  const agentId = match?.[1];
  // "main" is the primary session — fall back to configured userId
  if (!agentId || agentId === "main") return undefined;
  return agentId;
}

/**
 * Derive the effective user_id from a session key, namespacing per-agent.
 * Falls back to baseUserId when the session is not agent-scoped.
 */
export function effectiveUserId(
  baseUserId: string,
  sessionKey?: string,
): string {
  const agentId = extractAgentId(sessionKey);
  return agentId ? `${baseUserId}:agent:${agentId}` : baseUserId;
}

/** Build a user_id for an explicit agentId (e.g. from tool params). */
export function agentUserId(baseUserId: string, agentId: string): string {
  return `${baseUserId}:agent:${agentId}`;
}

/**
 * Resolve user_id with priority: explicit agentId > explicit userId > session-derived > configured.
 */
export function resolveUserId(
  baseUserId: string,
  opts: { agentId?: string; userId?: string },
  currentSessionId?: string,
): string {
  if (opts.agentId) return agentUserId(baseUserId, opts.agentId);
  if (opts.userId) return opts.userId;
  return effectiveUserId(baseUserId, currentSessionId);
}
