/** Structured operational logger for Mem0 TypeScript SDK.

Provides leveled logging with contextual metadata (operation, user_id,
agent_id, run_id, phase, timing) for the entire memory pipeline.

Usage:
  import { logger } from '@mem0ai/oss/utils/logger';
  logger.info("operation_start", { operation: "add", user_id: "u1" });
*/

export interface LoggerMeta {
  operation?: string;
  phase?: string;
  user_id?: string;
  agent_id?: string;
  run_id?: string;
  memory_id?: string;
  op_id?: string;
  elapsed_ms?: number;
  count?: number;
  [key: string]: unknown;
}

export interface Logger {
  info: (message: string, meta?: LoggerMeta) => void;
  error: (message: string, meta?: LoggerMeta) => void;
  debug: (message: string, meta?: LoggerMeta) => void;
  warn: (message: string, meta?: LoggerMeta) => void;
}

let _meta: LoggerMeta = {};

export function setMeta(...partials: LoggerMeta[]): void {
  _meta = { ..._meta, ...Object.assign({}, ...partials) };
}

export function clearMeta(): void {
  _meta = {};
}

function _format(message: string, meta?: LoggerMeta): string {
  const all = { ..._meta, ...meta };
  const parts = [message];
  for (const [k, v] of Object.entries(all)) {
    if (v !== undefined && v !== null) {
      parts.push(`${k}=${JSON.stringify(v)}`);
    }
  }
  return parts.join(" | ");
}

export const logger: Logger = {
  info: (message: string, meta?: LoggerMeta) =>
    console.log(`[INFO] ${_format(message, meta)}`),
  error: (message: string, meta?: LoggerMeta) =>
    console.error(`[ERROR] ${_format(message, meta)}`),
  debug: (message: string, meta?: LoggerMeta) =>
    console.debug(`[DEBUG] ${_format(message, meta)}`),
  warn: (message: string, meta?: LoggerMeta) =>
    console.warn(`[WARN] ${_format(message, meta)}`),
};
