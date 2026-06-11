import asyncio
import json
import re
import sys
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from mem0.memory import telemetry as telemetry_module
from mem0.memory.setup import _load_config, _write_config


FLAG_KEY = "mem0-oss-notices"
NOTICE_ID = "first_run"
TEMPORAL_FEATURE_NOTICE_ID = "temporal_stub"
TEMPORAL_USAGE_NOTICE_ID = "temporal_usage"
PERFORMANCE_SLOW_QUERY_NOTICE_ID = "performance_slow_query"
NOTICE_EVENT = "mem0.notice_displayed"
DISPLAYED_VARIANT = "displayed"
HOLDOUT_VARIANT = "holdout"
STATE_SECTION = "notice_state"
STATE_KEY = "first_run"
TEMPORAL_USAGE_STATE_KEY = "temporal_usage"
TEMPORAL_USAGE_CAP = 10
TEMPORAL_USAGE_WINDOW = timedelta(days=7)
PERFORMANCE_SLOW_QUERY_STATE_KEY = "performance_slow_query"
PERFORMANCE_SLOW_QUERY_CAP = 10
PERFORMANCE_SLOW_QUERY_WINDOW = timedelta(days=7)
PERFORMANCE_SLOW_QUERY_THRESHOLD_SECONDS = 2.0
TEMPORAL_FEATURE_ERROR_MESSAGES = {
    "timestamp": "The timestamp parameter is not supported by the OSS Memory SDK.",
    "reference_date": "The reference_date parameter is not supported by the OSS Memory SDK.",
}

_ISO_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
)
_RELATIVE_TIME_RE = re.compile(
    r"\b("
    r"today|yesterday|tomorrow|"
    r"last\s+(?:night|week|month|year)|"
    r"this\s+(?:week|month|year)|"
    r"next\s+(?:week|month|year)|"
    r"(?:past|last)\s+\d+\s+(?:day|days|week|weeks|month|months|year|years)|"
    r"(?:since|before|after|until)\s+(?:today|yesterday|tomorrow|\d{4}-\d{2}-\d{2}|last\s+(?:week|month|year))"
    r")\b",
    re.IGNORECASE,
)
_RANGE_OPERATORS = {"gt", "gte", "lt", "lte"}

_state_lock = threading.Lock()
_first_run_claimed_in_process = False


def display_first_run_notice(memory_instance, sync_type: str, trigger_function: str) -> None:
    """Best-effort first-run notice check. Never raises or writes unless displayed."""
    if not telemetry_module.MEM0_TELEMETRY:
        return

    if not _claim_first_run_notice(trigger_function):
        return

    variant = None
    try:
        telemetry = telemetry_module._get_oss_telemetry()
        if telemetry is None or telemetry.posthog is None or not telemetry.user_id:
            return

        flags = telemetry.posthog.evaluate_flags(telemetry.user_id, flag_keys=[FLAG_KEY])
        variant = flags.get_flag(FLAG_KEY)
        _update_first_run_variant(variant)

        if variant in (None, False):
            return

        payload = _coerce_mapping(flags.get_flag_payload(FLAG_KEY))
        notices = payload.get("notices", {})
        notice_config = _coerce_mapping(notices.get(NOTICE_ID) if isinstance(notices, dict) else {})
        notice_config_found = bool(notice_config)

        copy = notice_config.get("copy")
        enabled = notice_config.get("enabled", True) if notice_config_found else False
        notice_type = notice_config.get("notice_type", "log_line")

        disabled_reason = None
        bypass_reason = None
        if not notice_config_found:
            bypass_reason = "missing_notice_config"
        elif not enabled:
            disabled_reason = "payload_disabled"
            bypass_reason = disabled_reason
        elif not copy:
            bypass_reason = "missing_copy"
        elif variant != DISPLAYED_VARIANT:
            bypass_reason = "holdout" if variant == HOLDOUT_VARIANT else "not_displayed"

        displayed = variant == DISPLAYED_VARIANT and enabled and bool(copy)

        telemetry.capture_event(
            NOTICE_EVENT,
            {
                "notice_id": NOTICE_ID,
                "notice_type": notice_type,
                "flag_key": FLAG_KEY,
                "variant": variant,
                "displayed": displayed,
                "payload": copy,
                "bypass_reason": bypass_reason,
                "disabled_reason": disabled_reason,
                "notice_config_found": notice_config_found,
                "sync_type": sync_type,
                "trigger_function": trigger_function,
            },
            flags=flags,
        )

        if displayed:
            print(copy, file=sys.stderr)
    except Exception:
        if variant is not None:
            _update_first_run_variant(variant)


async def display_first_run_notice_async(memory_instance, sync_type: str, trigger_function: str) -> None:
    await asyncio.to_thread(display_first_run_notice, memory_instance, sync_type, trigger_function)


def display_temporal_usage_notice(
    memory_instance,
    sync_type: str,
    trigger_function: str,
    trigger_source: str,
    trigger_reason: str,
) -> None:
    """Best-effort temporal usage notice. Never raises or writes unless displayed."""
    if not telemetry_module.MEM0_TELEMETRY:
        return

    if _temporal_usage_at_capacity():
        return

    try:
        telemetry = telemetry_module._get_oss_telemetry()
        if telemetry is None or telemetry.posthog is None or not telemetry.user_id:
            return

        flags = telemetry.posthog.evaluate_flags(telemetry.user_id, flag_keys=[FLAG_KEY])
        variant = flags.get_flag(FLAG_KEY)
        if variant in (None, False):
            return

        payload = _coerce_mapping(flags.get_flag_payload(FLAG_KEY))
        notices = payload.get("notices", {})
        notice_config = _coerce_mapping(
            notices.get(TEMPORAL_USAGE_NOTICE_ID) if isinstance(notices, dict) else {}
        )
        notice_config_found = bool(notice_config)

        copy = notice_config.get("copy")
        enabled = notice_config.get("enabled", True) if notice_config_found else False
        notice_type = notice_config.get("notice_type", "log_line")

        disabled_reason = None
        bypass_reason = None
        if not notice_config_found:
            bypass_reason = "missing_notice_config"
        elif not enabled:
            disabled_reason = "payload_disabled"
            bypass_reason = disabled_reason
        elif not copy:
            bypass_reason = "missing_copy"
        elif variant != DISPLAYED_VARIANT:
            bypass_reason = "holdout" if variant == HOLDOUT_VARIANT else "not_displayed"

        displayed = variant == DISPLAYED_VARIANT and enabled and bool(copy)

        if not _record_temporal_usage_opportunity(
            variant=variant,
            sync_type=sync_type,
            trigger_function=trigger_function,
            trigger_source=trigger_source,
            trigger_reason=trigger_reason,
        ):
            return

        telemetry.capture_event(
            NOTICE_EVENT,
            {
                "notice_id": TEMPORAL_USAGE_NOTICE_ID,
                "notice_type": notice_type,
                "flag_key": FLAG_KEY,
                "variant": variant,
                "displayed": displayed,
                "payload": copy,
                "bypass_reason": bypass_reason,
                "disabled_reason": disabled_reason,
                "notice_config_found": notice_config_found,
                "sync_type": sync_type,
                "trigger_function": trigger_function,
                "trigger_source": trigger_source,
                "trigger_reason": trigger_reason,
            },
            flags=flags,
        )

        if displayed:
            print(copy, file=sys.stderr)
    except Exception:
        return


async def display_temporal_usage_notice_async(
    memory_instance,
    sync_type: str,
    trigger_function: str,
    trigger_source: str,
    trigger_reason: str,
) -> None:
    await asyncio.to_thread(
        display_temporal_usage_notice,
        memory_instance,
        sync_type,
        trigger_function,
        trigger_source,
        trigger_reason,
    )


def display_performance_slow_query_notice(
    memory_instance,
    sync_type: str,
    trigger_function: str,
    elapsed_seconds: float,
    top_k: int,
    result_count: int,
) -> None:
    """Best-effort slow-query notice. Never raises or writes unless displayed."""
    if not telemetry_module.MEM0_TELEMETRY:
        return

    if _performance_slow_query_at_capacity():
        return

    try:
        telemetry = telemetry_module._get_oss_telemetry()
        if telemetry is None or telemetry.posthog is None or not telemetry.user_id:
            return

        flags = telemetry.posthog.evaluate_flags(telemetry.user_id, flag_keys=[FLAG_KEY])
        variant = flags.get_flag(FLAG_KEY)
        if variant in (None, False):
            return

        payload = _coerce_mapping(flags.get_flag_payload(FLAG_KEY))
        notices = payload.get("notices", {})
        notice_config = _coerce_mapping(
            notices.get(PERFORMANCE_SLOW_QUERY_NOTICE_ID) if isinstance(notices, dict) else {}
        )
        notice_config_found = bool(notice_config)

        copy = notice_config.get("copy")
        enabled = notice_config.get("enabled", True) if notice_config_found else False
        notice_type = notice_config.get("notice_type", "log_line")

        disabled_reason = None
        bypass_reason = None
        if not notice_config_found:
            bypass_reason = "missing_notice_config"
        elif not enabled:
            disabled_reason = "payload_disabled"
            bypass_reason = disabled_reason
        elif not copy:
            bypass_reason = "missing_copy"
        elif variant != DISPLAYED_VARIANT:
            bypass_reason = "holdout" if variant == HOLDOUT_VARIANT else "not_displayed"

        displayed = variant == DISPLAYED_VARIANT and enabled and bool(copy)
        trigger_reason = "slow_query"

        if not _record_performance_slow_query_opportunity(
            variant=variant,
            sync_type=sync_type,
            trigger_function=trigger_function,
            trigger_reason=trigger_reason,
        ):
            return

        telemetry.capture_event(
            NOTICE_EVENT,
            {
                "notice_id": PERFORMANCE_SLOW_QUERY_NOTICE_ID,
                "notice_type": notice_type,
                "flag_key": FLAG_KEY,
                "variant": variant,
                "displayed": displayed,
                "payload": copy,
                "bypass_reason": bypass_reason,
                "disabled_reason": disabled_reason,
                "notice_config_found": notice_config_found,
                "sync_type": sync_type,
                "trigger_function": trigger_function,
                "trigger_reason": trigger_reason,
                "elapsed_ms": round(elapsed_seconds * 1000),
                "threshold_ms": round(PERFORMANCE_SLOW_QUERY_THRESHOLD_SECONDS * 1000),
                "top_k": top_k,
                "result_count": result_count,
            },
            flags=flags,
        )

        if displayed:
            print(copy, file=sys.stderr)
    except Exception:
        return


async def display_performance_slow_query_notice_async(
    memory_instance,
    sync_type: str,
    trigger_function: str,
    elapsed_seconds: float,
    top_k: int,
    result_count: int,
) -> None:
    await asyncio.to_thread(
        display_performance_slow_query_notice,
        memory_instance,
        sync_type,
        trigger_function,
        elapsed_seconds,
        top_k,
        result_count,
    )


def get_temporal_feature_error_message(sync_type: str, trigger_function: str, trigger_parameter: str) -> str:
    """Return the temporal feature error copy and capture event when available."""
    plain_error = TEMPORAL_FEATURE_ERROR_MESSAGES[trigger_parameter]
    if not telemetry_module.MEM0_TELEMETRY:
        return plain_error

    try:
        telemetry = telemetry_module._get_oss_telemetry()
        if telemetry is None or telemetry.posthog is None or not telemetry.user_id:
            return plain_error

        flags = telemetry.posthog.evaluate_flags(telemetry.user_id, flag_keys=[FLAG_KEY])
        variant = flags.get_flag(FLAG_KEY)
        if variant in (None, False):
            return plain_error

        payload = _coerce_mapping(flags.get_flag_payload(FLAG_KEY))
        notices = payload.get("notices", {})
        notice_config = _coerce_mapping(
            notices.get(TEMPORAL_FEATURE_NOTICE_ID) if isinstance(notices, dict) else {}
        )
        notice_config_found = bool(notice_config)

        copy = notice_config.get("copy")
        enabled = notice_config.get("enabled", True) if notice_config_found else False
        notice_type = notice_config.get("notice_type", "error")

        disabled_reason = None
        bypass_reason = None
        if not notice_config_found:
            bypass_reason = "missing_notice_config"
        elif not enabled:
            disabled_reason = "payload_disabled"
            bypass_reason = disabled_reason
        elif not copy:
            bypass_reason = "missing_copy"
        elif variant not in (DISPLAYED_VARIANT, HOLDOUT_VARIANT):
            bypass_reason = "not_displayed"

        displayed = variant in (DISPLAYED_VARIANT, HOLDOUT_VARIANT) and enabled and bool(copy)

        telemetry.capture_event(
            NOTICE_EVENT,
            {
                "notice_id": TEMPORAL_FEATURE_NOTICE_ID,
                "notice_type": notice_type,
                "flag_key": FLAG_KEY,
                "variant": variant,
                "displayed": displayed,
                "payload": copy,
                "bypass_reason": bypass_reason,
                "disabled_reason": disabled_reason,
                "notice_config_found": notice_config_found,
                "sync_type": sync_type,
                "trigger_function": trigger_function,
                "trigger_parameter": trigger_parameter,
            },
            flags=flags,
        )

        if displayed:
            return copy
    except Exception:
        return plain_error

    return plain_error


async def get_temporal_feature_error_message_async(
    sync_type: str,
    trigger_function: str,
    trigger_parameter: str,
) -> str:
    return await asyncio.to_thread(
        get_temporal_feature_error_message,
        sync_type,
        trigger_function,
        trigger_parameter,
    )


def detect_temporal_usage_from_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Tuple[str, str]]:
    if not isinstance(metadata, dict):
        return None

    for key, value in _walk_mapping(metadata):
        temporal_key = _is_temporal_key(key)
        if temporal_key and _looks_temporal_value(value, allow_epoch=True):
            return ("metadata", "date_like_metadata")
        if _looks_temporal_value(value, allow_epoch=False):
            return ("metadata", "date_like_metadata")
    return None


def detect_temporal_usage_from_search(
    query: Any,
    filters: Optional[Dict[str, Any]],
) -> Optional[Tuple[str, str]]:
    if isinstance(query, str):
        if _RELATIVE_TIME_RE.search(query):
            return ("query", "relative_phrase")
        if _ISO_DATE_RE.search(query):
            return ("query", "date_like_query")

    if _has_temporal_filter(filters):
        return ("filter", "date_range_filter")
    return None


def _claim_first_run_notice(trigger_function: str) -> bool:
    global _first_run_claimed_in_process

    with _state_lock:
        if _first_run_claimed_in_process:
            return False

        config = _load_config()
        state = config.get(STATE_SECTION)
        if isinstance(state, dict):
            first_run = state.get(STATE_KEY)
            if isinstance(first_run, dict) and first_run.get("consumed"):
                _first_run_claimed_in_process = True
                return False

        if not isinstance(state, dict):
            state = {}

        state[STATE_KEY] = {
            "consumed": True,
            "consumed_at": datetime.now(timezone.utc).isoformat(),
            "trigger_function": trigger_function,
            "variant": None,
        }
        config[STATE_SECTION] = state
        _write_config(config)
        _first_run_claimed_in_process = True
        return True


def _update_first_run_variant(variant) -> None:
    try:
        with _state_lock:
            config = _load_config()
            state = config.get(STATE_SECTION)
            if not isinstance(state, dict):
                state = {}
            first_run = state.get(STATE_KEY)
            if not isinstance(first_run, dict):
                first_run = {"consumed": True}
            first_run["variant"] = variant
            state[STATE_KEY] = first_run
            config[STATE_SECTION] = state
            _write_config(config)
    except Exception:
        return


def _temporal_usage_at_capacity() -> bool:
    try:
        with _state_lock:
            config = _load_config()
            entries = _recent_temporal_usage_entries(config, datetime.now(timezone.utc))
            return len(entries) >= TEMPORAL_USAGE_CAP
    except Exception:
        return True


def _performance_slow_query_at_capacity() -> bool:
    try:
        with _state_lock:
            config = _load_config()
            entries = _recent_performance_slow_query_entries(config, datetime.now(timezone.utc))
            return len(entries) >= PERFORMANCE_SLOW_QUERY_CAP
    except Exception:
        return True


def _record_temporal_usage_opportunity(
    *,
    variant: str,
    sync_type: str,
    trigger_function: str,
    trigger_source: str,
    trigger_reason: str,
) -> bool:
    try:
        with _state_lock:
            now = datetime.now(timezone.utc)
            config = _load_config()
            entries = _recent_temporal_usage_entries(config, now)
            if len(entries) >= TEMPORAL_USAGE_CAP:
                return False

            entries.append(
                {
                    "evaluated_at": now.isoformat(),
                    "variant": variant,
                    "sync_type": sync_type,
                    "trigger_function": trigger_function,
                    "trigger_source": trigger_source,
                    "trigger_reason": trigger_reason,
                }
            )

            state = config.get(STATE_SECTION)
            if not isinstance(state, dict):
                state = {}
            temporal_state = state.get(TEMPORAL_USAGE_STATE_KEY)
            if not isinstance(temporal_state, dict):
                temporal_state = {}
            temporal_state["events"] = entries
            state[TEMPORAL_USAGE_STATE_KEY] = temporal_state
            config[STATE_SECTION] = state
            _write_config(config)
            return True
    except Exception:
        return False


def _record_performance_slow_query_opportunity(
    *,
    variant: str,
    sync_type: str,
    trigger_function: str,
    trigger_reason: str,
) -> bool:
    try:
        with _state_lock:
            now = datetime.now(timezone.utc)
            config = _load_config()
            entries = _recent_performance_slow_query_entries(config, now)
            if len(entries) >= PERFORMANCE_SLOW_QUERY_CAP:
                return False

            entries.append(
                {
                    "evaluated_at": now.isoformat(),
                    "variant": variant,
                    "sync_type": sync_type,
                    "trigger_function": trigger_function,
                    "trigger_reason": trigger_reason,
                }
            )

            state = config.get(STATE_SECTION)
            if not isinstance(state, dict):
                state = {}
            performance_state = state.get(PERFORMANCE_SLOW_QUERY_STATE_KEY)
            if not isinstance(performance_state, dict):
                performance_state = {}
            performance_state["events"] = entries
            state[PERFORMANCE_SLOW_QUERY_STATE_KEY] = performance_state
            config[STATE_SECTION] = state
            _write_config(config)
            return True
    except Exception:
        return False


def _recent_temporal_usage_entries(config: Dict[str, Any], now: datetime):
    state = config.get(STATE_SECTION)
    if not isinstance(state, dict):
        return []

    temporal_state = state.get(TEMPORAL_USAGE_STATE_KEY)
    if not isinstance(temporal_state, dict):
        return []

    entries = temporal_state.get("events")
    if not isinstance(entries, list):
        return []

    cutoff = now - TEMPORAL_USAGE_WINDOW
    recent = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        evaluated_at = _parse_datetime(entry.get("evaluated_at"))
        if evaluated_at is not None and evaluated_at >= cutoff:
            recent.append(entry)
    return recent


def _recent_performance_slow_query_entries(config: Dict[str, Any], now: datetime):
    state = config.get(STATE_SECTION)
    if not isinstance(state, dict):
        return []

    performance_state = state.get(PERFORMANCE_SLOW_QUERY_STATE_KEY)
    if not isinstance(performance_state, dict):
        return []

    entries = performance_state.get("events")
    if not isinstance(entries, list):
        return []

    cutoff = now - PERFORMANCE_SLOW_QUERY_WINDOW
    recent = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        evaluated_at = _parse_datetime(entry.get("evaluated_at"))
        if evaluated_at is not None and evaluated_at >= cutoff:
            recent.append(entry)
    return recent


def _parse_datetime(value: Any):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _coerce_mapping(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _walk_mapping(value: Any, parent_key: str = ""):
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            yield key_text, child
            yield from _walk_mapping(child, key_text)
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            yield from _walk_mapping(child, parent_key)


def _is_temporal_key(key: Any) -> bool:
    key_text = str(key).lower()
    exact_keys = {
        "date",
        "time",
        "timestamp",
        "datetime",
        "event_date",
        "reference_date",
        "created_at",
        "updated_at",
        "started_at",
        "ended_at",
        "expires_at",
    }
    return (
        key_text in exact_keys
        or key_text.endswith("_date")
        or key_text.endswith("_time")
        or key_text.endswith("_at")
        or "timestamp" in key_text
    )


def _looks_temporal_value(value: Any, allow_epoch: bool) -> bool:
    if isinstance(value, datetime):
        return True
    if isinstance(value, date):
        return True
    if isinstance(value, str):
        return bool(_ISO_DATE_RE.search(value) or _RELATIVE_TIME_RE.search(value))
    if allow_epoch and isinstance(value, (int, float)) and not isinstance(value, bool):
        return 946684800 <= value <= 4102444800 or 946684800000 <= value <= 4102444800000
    return False


def _has_temporal_filter(filters: Any) -> bool:
    if not isinstance(filters, dict):
        return False

    for key, value in filters.items():
        if key in {"AND", "OR", "NOT", "$and", "$or", "$not"}:
            if isinstance(value, list) and any(_has_temporal_filter(item) for item in value):
                return True
            if isinstance(value, dict) and _has_temporal_filter(value):
                return True
            continue

        temporal_key = _is_temporal_key(key)
        if isinstance(value, dict):
            range_values = [item for op, item in value.items() if op in _RANGE_OPERATORS]
            if range_values and (
                temporal_key
                or any(_looks_temporal_value(item, allow_epoch=temporal_key) for item in range_values)
            ):
                return True
            if _has_temporal_filter(value):
                return True
        elif temporal_key and _looks_temporal_value(value, allow_epoch=True):
            return True

    return False
