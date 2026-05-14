"""Agent Mode commands — bootstrap (unattended signup) and claim (OTP-based human upgrade)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
import typer
from rich.console import Console
from rich.prompt import Prompt

from mem0_cli.branding import (
    BRAND_COLOR,
    DIM_COLOR,
    print_error,
    print_success,
)
from mem0_cli.config import Mem0Config, save_config

console = Console()
err_console = Console(stderr=True)

_SOURCE_HEADERS = {
    "X-Mem0-Source": "cli",
    "X-Mem0-Client-Language": "python",
}


def _validate_envelope(envelope: Any) -> None:
    """Defend against partial/malformed backend responses.

    A backend regression that returns ``{"api_key": null}`` would otherwise be
    silently persisted, producing confusing downstream errors far from the
    source. Fail fast with a clear message if the required fields are missing.
    """
    if not isinstance(envelope, dict):
        print_error(err_console, "Bootstrap response was not a JSON object.")
        raise typer.Exit(1)
    for field in ("api_key", "default_user_id"):
        value = envelope.get(field)
        if not isinstance(value, str) or not value:
            print_error(
                err_console,
                f"Bootstrap response missing required field {field!r} — please update the CLI.",
            )
            raise typer.Exit(1)


def bootstrap_via_backend(
    config: Mem0Config,
    *,
    source: str | None = None,
    agent_caller: str | None = None,
) -> None:
    """POST /api/v1/auth/agent_mode/ and mutate config in place.

    Args:
        config: Mem0Config mutated in place with the new platform values.
        source: ``--source`` flag passthrough (analytics tag, free-form).
        agent_caller: Self-declared agent identity passed via ``--agent-caller``
            (e.g. ``claude-code``, ``cursor``). May be None when the caller
            omitted the flag; the agent can backfill later via
            ``mem0 identify <name>``. Sent to the backend in the request body
            and saved into ``platform.agent_caller`` for local introspection.

    Raises typer.Exit(1) on failure.
    """
    base_url = (config.platform.base_url or "https://api.mem0.ai").rstrip("/")
    body: dict[str, Any] = {}
    if source:
        body["source"] = source
    if agent_caller:
        body["agent_caller"] = agent_caller

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{base_url}/api/v1/auth/agent_mode/",
                headers={**_SOURCE_HEADERS, "Content-Type": "application/json"},
                json=body,
            )
    except httpx.HTTPError as exc:
        print_error(err_console, f"Network error contacting Mem0: {exc}")
        raise typer.Exit(1) from exc

    if resp.status_code == 429:
        print_error(err_console, "Rate-limited. Try again in a few minutes.")
        raise typer.Exit(1)
    if resp.status_code == 503:
        print_error(err_console, "Agent Mode is temporarily disabled. Try again later.")
        raise typer.Exit(1)
    if resp.status_code != 200:
        detail = resp.text
        try:
            err_body = resp.json()
            detail = err_body.get("error") or err_body.get("detail") or resp.text
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass
        # Backend's @ratelimit decorator raises PermissionDenied, which DRF
        # translates to a generic 403 "You do not have permission to perform
        # this action." That's opaque — surface as the rate-limit it actually is.
        if resp.status_code == 403 and "permission" in str(detail).lower():
            print_error(
                err_console,
                "Daily Agent Mode signup limit reached for this network (5/day). Try again from a different IP or after midnight UTC.",
            )
            raise typer.Exit(1)
        print_error(err_console, f"Bootstrap failed: {detail}")
        raise typer.Exit(1)

    envelope = resp.json()
    _validate_envelope(envelope)
    config.platform.api_key = envelope["api_key"]
    config.platform.base_url = base_url
    config.platform.agent_mode = True
    config.platform.created_via = "agent_mode"
    config.platform.agent_caller = agent_caller or ""
    config.platform.claimed_at = ""
    config.platform.default_user_id = envelope["default_user_id"]
    # Adopt the slug-derived user_id as the default scope for memory ops.
    config.defaults.user_id = envelope["default_user_id"]
    save_config(config)

    print_success(console, f"Agent Mode active. Default user_id: {envelope['default_user_id']}")
    notice = envelope.get("mem0_notice")
    if notice:
        console.print(f"\n[yellow]🔔 {notice}[/yellow]\n")
    else:
        # Fallback if the backend hasn't deployed the unified notice yet.
        claim_cmd = envelope.get("claim_command", "mem0 init --email <your-email>")
        console.print(f"  [{DIM_COLOR}]To claim this account later: {claim_cmd}[/]")

    if not agent_caller:
        console.print(
            f"  [{DIM_COLOR}]If you are an AI agent, identify yourself: "
            f"`mem0 identify <your-name>` (e.g. claude-code, cursor).[/]"
        )


def claim_via_otp(config: Mem0Config, *, email: str, code: str | None = None) -> None:
    """Claim an existing Agent Mode account via OTP — no browser, no polling.

    Reuses the standard email-code flow (`/api/v1/auth/email_code/` then
    `/.../verify/`) and adds the local agent-mode API key in the verify body
    as `agent_mode_api_key`. Backend's `verify_email_code` runs the
    upgrade-in-place transaction inline and returns claim result.

    On success: flips `platform.agent_mode=false`, sets `claimed_at`, stamps
    `user_email`. The api_key value itself never changes.
    """
    base_url = (config.platform.base_url or "https://api.mem0.ai").rstrip("/")
    if not config.platform.api_key or not config.platform.agent_mode:
        print_error(
            err_console,
            "This command requires an active Agent Mode config. Run `mem0 init` first.",
        )
        raise typer.Exit(1)

    raw_key = config.platform.api_key

    with httpx.Client(timeout=30.0) as client:
        # Step 1: request OTP (unless --code provided)
        if not code:
            send = client.post(
                f"{base_url}/api/v1/auth/email_code/",
                headers={**_SOURCE_HEADERS, "Content-Type": "application/json"},
                json={"email": email},
            )
            if send.status_code == 429:
                print_error(err_console, "Too many attempts. Try again in a few minutes.")
                raise typer.Exit(1)
            if send.status_code != 200:
                try:
                    detail = send.json().get("error", send.text)
                except Exception:
                    detail = send.text
                print_error(err_console, f"Failed to send code: {detail}")
                raise typer.Exit(1)

            print_success(console, f"Verification code sent to {email}. Check your inbox.")

            if not sys.stdin.isatty():
                print_error(
                    err_console,
                    "No --code provided and terminal is non-interactive.",
                    hint=f"Re-run: mem0 init --email {email} --code <code>",
                )
                raise typer.Exit(1)

            console.print()
            code = Prompt.ask(f"  [{BRAND_COLOR}]Verification Code[/]")
            if not code:
                print_error(err_console, "Code is required.")
                raise typer.Exit(1)

        # Step 2: verify + claim in one shot
        verify = client.post(
            f"{base_url}/api/v1/auth/email_code/verify/",
            headers={**_SOURCE_HEADERS, "Content-Type": "application/json"},
            json={
                "email": email,
                "code": code.strip(),
                "agent_mode_api_key": raw_key,
            },
        )

    if verify.status_code != 200:
        try:
            err_body = verify.json()
            detail = err_body.get("error", verify.text)
            code_str = err_body.get("code", "")
        except (json.JSONDecodeError, ValueError, AttributeError):
            detail = verify.text
            code_str = ""
        print_error(err_console, f"Claim failed: {detail}")
        if code_str == "email_already_claimed":
            console.print(
                f"  [{DIM_COLOR}]Tip: this email already has a Mem0 account. Sign in there and run `mem0 link <key>` to attach this agent.[/]"
            )
        raise typer.Exit(1)

    claim_body = verify.json()
    if not claim_body.get("claimed"):
        print_error(err_console, f"Unexpected verify response: {claim_body}")
        raise typer.Exit(1)

    config.platform.agent_mode = False
    config.platform.claimed_at = claim_body.get("claimed_at") or _utcnow_iso()
    config.platform.user_email = email
    config.platform.created_via = "email"
    save_config(config)
    print_success(console, f"Agent claimed to {email}. Your API key is unchanged.")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
