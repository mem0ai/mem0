import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import {
  POSTHOG_API_KEY,
  captureNoticeEvent,
  isTelemetryEnabled,
} from "./telemetry";
import type { TelemetryInstance } from "./telemetry.types";

export const NOTICE_FLAG_KEY = "mem0-oss-notices";
export const NOTICE_EVENT_NAME = "mem0.notice_displayed";
export const NOTICE_STATE_SECTION = "notice_state";
export const FIRST_RUN_NOTICE_ID = "first_run";
export const NOTICE_CAP_LIMIT = 10;
export const NOTICE_CAP_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;
export const NOTICE_FLAG_TIMEOUT_MS = 500;
export const POSTHOG_FLAGS_URL = "https://us.i.posthog.com/flags?v=2";
const DISPLAYED_VARIANT = "displayed";
const LOG_LINE_NOTICE_TYPE = "log_line";

let firstRunConsumedInProcess = false;
let firstRunClaimInProgress = false;

export interface NoticePayloadConfig {
  enabled?: boolean;
  notice_type?: string;
  copy?: string;
  [key: string]: any;
}

export interface NoticeFlagEvaluation {
  variant: string;
  payload?: Record<string, any>;
  flag?: Record<string, any>;
}

export interface NoticeCapEvent {
  evaluated_at?: string;
  [key: string]: any;
}

interface NoticeDisplayDecision {
  displayed: boolean;
  noticeConfigFound: boolean;
  copy?: string;
  bypassReason?: string;
  disabledReason?: string;
}

export function getMem0Dir(): string {
  return process.env.MEM0_DIR || path.join(os.homedir(), ".mem0");
}

export function getMem0ConfigPath(): string {
  return path.join(getMem0Dir(), "config.json");
}

export function loadMem0Config(): Record<string, any> {
  try {
    const configPath = getMem0ConfigPath();
    if (!fs.existsSync(configPath)) return {};
    const parsed = JSON.parse(fs.readFileSync(configPath, "utf8"));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

export function writeMem0ConfigAtomic(config: Record<string, any>): boolean {
  const configPath = getMem0ConfigPath();
  const dir = path.dirname(configPath);
  const tempPath = path.join(
    dir,
    `.config.${process.pid}.${Date.now()}.${Math.random()
      .toString(36)
      .slice(2)}.tmp`,
  );

  try {
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(tempPath, JSON.stringify(config, null, 4));
    fs.renameSync(tempPath, configPath);
    return true;
  } catch {
    try {
      if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
    } catch {}
    return false;
  }
}

export function getNoticeState(
  config: Record<string, any>,
  noticeId: string,
): Record<string, any> {
  const stateSection =
    config[NOTICE_STATE_SECTION] &&
    typeof config[NOTICE_STATE_SECTION] === "object" &&
    !Array.isArray(config[NOTICE_STATE_SECTION])
      ? config[NOTICE_STATE_SECTION]
      : {};
  const noticeState = stateSection[noticeId];
  return noticeState &&
    typeof noticeState === "object" &&
    !Array.isArray(noticeState)
    ? noticeState
    : {};
}

export function setNoticeState(
  config: Record<string, any>,
  noticeId: string,
  state: Record<string, any>,
): Record<string, any> {
  const stateSection =
    config[NOTICE_STATE_SECTION] &&
    typeof config[NOTICE_STATE_SECTION] === "object" &&
    !Array.isArray(config[NOTICE_STATE_SECTION])
      ? { ...config[NOTICE_STATE_SECTION] }
      : {};
  return {
    ...config,
    [NOTICE_STATE_SECTION]: {
      ...stateSection,
      [noticeId]: state,
    },
  };
}

function parsePayload(payload: unknown): Record<string, any> | undefined {
  try {
    if (typeof payload === "string") {
      const parsed = JSON.parse(payload);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? parsed
        : undefined;
    }
    return payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, any>)
      : undefined;
  } catch {
    return undefined;
  }
}

export function getNoticeConfigFromPayload(
  payload: unknown,
  noticeId: string,
): {
  found: boolean;
  config?: NoticePayloadConfig;
  payload?: Record<string, any>;
} {
  const parsedPayload = parsePayload(payload);
  const notices = parsedPayload?.notices;
  if (!notices || typeof notices !== "object" || Array.isArray(notices)) {
    return { found: false, payload: parsedPayload };
  }

  const noticeConfig = (notices as Record<string, any>)[noticeId];
  if (
    !noticeConfig ||
    typeof noticeConfig !== "object" ||
    Array.isArray(noticeConfig)
  ) {
    return { found: false, payload: parsedPayload };
  }

  return {
    found: true,
    config: noticeConfig as NoticePayloadConfig,
    payload: parsedPayload,
  };
}

export async function evaluateNoticeFlag(
  distinctId: string,
  options: { timeoutMs?: number; fetchImpl?: typeof fetch } = {},
): Promise<NoticeFlagEvaluation | null> {
  if (!isTelemetryEnabled()) return null;

  const timeoutMs = options.timeoutMs ?? NOTICE_FLAG_TIMEOUT_MS;
  const fetchImpl = options.fetchImpl ?? fetch;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetchImpl(POSTHOG_FLAGS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: POSTHOG_API_KEY,
        distinct_id: distinctId,
      }),
      signal: controller.signal,
    });

    if (!response.ok) return null;
    const data: any = await response.json();
    const flag = data?.flags?.[NOTICE_FLAG_KEY];
    if (!flag || flag.enabled === false) return null;

    const variant = typeof flag.variant === "string" ? flag.variant : null;
    if (!variant) return null;

    return {
      variant,
      payload: parsePayload(flag.metadata?.payload),
      flag,
    };
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

function eventsInWindow(
  events: unknown,
  now: Date,
  windowMs: number,
): NoticeCapEvent[] {
  if (!Array.isArray(events)) return [];
  const cutoff = now.getTime() - windowMs;
  return events.filter((event): event is NoticeCapEvent => {
    if (!event || typeof event !== "object" || Array.isArray(event)) {
      return false;
    }
    const evaluatedAt = (event as NoticeCapEvent).evaluated_at;
    if (typeof evaluatedAt !== "string") return false;
    const timestamp = Date.parse(evaluatedAt);
    return Number.isFinite(timestamp) && timestamp >= cutoff;
  });
}

export function hasNoticeCapRoom(
  state: Record<string, any>,
  options: { now?: Date; limit?: number; windowMs?: number } = {},
): boolean {
  const now = options.now ?? new Date();
  const limit = options.limit ?? NOTICE_CAP_LIMIT;
  const windowMs = options.windowMs ?? NOTICE_CAP_WINDOW_MS;
  return eventsInWindow(state.events, now, windowMs).length < limit;
}

export function appendNoticeCapEvent(
  state: Record<string, any>,
  event: NoticeCapEvent,
  options: { now?: Date; limit?: number; windowMs?: number } = {},
): Record<string, any> | null {
  const now = options.now ?? new Date();
  const limit = options.limit ?? NOTICE_CAP_LIMIT;
  const windowMs = options.windowMs ?? NOTICE_CAP_WINDOW_MS;
  const events = eventsInWindow(state.events, now, windowMs);
  if (events.length >= limit) return null;

  return {
    ...state,
    events: [
      ...events,
      {
        evaluated_at: now.toISOString(),
        ...event,
      },
    ],
  };
}

export function recordNoticeOpportunity(
  noticeId: string,
  event: NoticeCapEvent,
  options: { now?: Date; limit?: number; windowMs?: number } = {},
): boolean {
  if (!isTelemetryEnabled()) return false;

  const config = loadMem0Config();
  const state = getNoticeState(config, noticeId);
  const nextState = appendNoticeCapEvent(state, event, options);
  if (!nextState) return false;
  return writeMem0ConfigAtomic(setNoticeState(config, noticeId, nextState));
}

function isFirstRunConsumed(config: Record<string, any>): boolean {
  return getNoticeState(config, FIRST_RUN_NOTICE_ID).consumed === true;
}

function markFirstRunConsumed(
  triggerFunction: string,
  variant: string,
): boolean {
  const config = loadMem0Config();
  const state = getNoticeState(config, FIRST_RUN_NOTICE_ID);
  const nextState = {
    ...state,
    consumed: true,
    consumed_at: new Date().toISOString(),
    trigger_function: triggerFunction,
    variant,
  };
  return writeMem0ConfigAtomic(
    setNoticeState(config, FIRST_RUN_NOTICE_ID, nextState),
  );
}

function getDisplayDecision(
  noticeId: string,
  expectedNoticeType: string,
  variant: string,
  payload: unknown,
): NoticeDisplayDecision {
  const parsed = getNoticeConfigFromPayload(payload, noticeId);
  const copy =
    typeof parsed.config?.copy === "string" ? parsed.config.copy : undefined;

  if (!parsed.found) {
    return {
      displayed: false,
      noticeConfigFound: false,
      bypassReason: "missing_notice_config",
    };
  }

  if (parsed.config?.enabled !== true) {
    return {
      displayed: false,
      noticeConfigFound: true,
      copy,
      bypassReason: "payload_disabled",
      disabledReason: "payload_disabled",
    };
  }

  if (parsed.config.notice_type !== expectedNoticeType) {
    return {
      displayed: false,
      noticeConfigFound: true,
      copy,
      bypassReason: "invalid_notice_type",
    };
  }

  if (!copy || copy.trim() === "") {
    return {
      displayed: false,
      noticeConfigFound: true,
      bypassReason: "missing_copy",
    };
  }

  if (variant !== DISPLAYED_VARIANT) {
    return {
      displayed: false,
      noticeConfigFound: true,
      copy,
      bypassReason: "holdout",
    };
  }

  return {
    displayed: true,
    noticeConfigFound: true,
    copy,
  };
}

export async function displayFirstRunNotice(
  instance: TelemetryInstance,
  triggerFunction: string,
): Promise<void> {
  if (!isTelemetryEnabled()) return;
  if (firstRunConsumedInProcess || firstRunClaimInProgress) return;

  const config = loadMem0Config();
  if (isFirstRunConsumed(config)) {
    firstRunConsumedInProcess = true;
    return;
  }

  firstRunClaimInProgress = true;
  try {
    const flagEvaluation = await evaluateNoticeFlag(instance.telemetryId);
    if (!flagEvaluation) {
      firstRunClaimInProgress = false;
      return;
    }

    const decision = getDisplayDecision(
      FIRST_RUN_NOTICE_ID,
      LOG_LINE_NOTICE_TYPE,
      flagEvaluation.variant,
      flagEvaluation.payload,
    );

    firstRunConsumedInProcess = true;
    markFirstRunConsumed(triggerFunction, flagEvaluation.variant);

    await emitNoticeDisplayed(instance, {
      notice_id: FIRST_RUN_NOTICE_ID,
      notice_type: LOG_LINE_NOTICE_TYPE,
      flag_key: NOTICE_FLAG_KEY,
      variant: flagEvaluation.variant,
      displayed: decision.displayed,
      payload: decision.copy,
      bypass_reason: decision.bypassReason,
      disabled_reason: decision.disabledReason,
      notice_config_found: decision.noticeConfigFound,
      sync_type: "async",
      trigger_function: triggerFunction,
    });

    if (decision.displayed && decision.copy) {
      process.stderr.write(`${decision.copy}\n`);
    }
  } catch {
    if (!firstRunConsumedInProcess) firstRunClaimInProgress = false;
  } finally {
    if (firstRunConsumedInProcess) firstRunClaimInProgress = false;
  }
}

export async function emitNoticeDisplayed(
  instance: TelemetryInstance,
  properties: Record<string, any>,
): Promise<void> {
  if (!isTelemetryEnabled()) return;
  try {
    await captureNoticeEvent(instance, properties);
  } catch {}
}

export const __noticeTestHooks = {
  appendNoticeCapEvent,
  emitNoticeDisplayed,
  evaluateNoticeFlag,
  displayFirstRunNotice,
  getMem0ConfigPath,
  getMem0Dir,
  getNoticeConfigFromPayload,
  getNoticeState,
  hasNoticeCapRoom,
  loadMem0Config,
  recordNoticeOpportunity,
  setNoticeState,
  writeMem0ConfigAtomic,
};
