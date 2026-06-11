import asyncio
import json
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict

from mem0.memory import telemetry as telemetry_module
from mem0.memory.setup import _load_config, _write_config


FLAG_KEY = "mem0-oss-notices"
NOTICE_ID = "first_run"
NOTICE_EVENT = "mem0.notice_displayed"
DISPLAYED_VARIANT = "displayed"
HOLDOUT_VARIANT = "holdout"
STATE_SECTION = "notice_state"
STATE_KEY = "first_run"

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
