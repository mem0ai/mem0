/**
 * Per-agent memory isolation helpers.
 *
 * Multi-agent setups write/read from separate userId namespaces
 * automatically via sessionKey routing.
 */

/**
 * Parse an agent ID from a session key following the pattern `agent:<agentId>:<uuid>`.
 * Returns undefined for non-agent sessions, the "main" sentinel, or malformed keys.
 */
export function extractAgentId(sessionKey: string | undefined): string | undefined {
  if (!sessionKey) return undefined;
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
export function effectiveUserId(baseUserId: string, sessionKey?: string): string {
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
