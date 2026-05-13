"""Agent Mode commands — bootstrap (unattended signup) and claim (OTP-based human upgrade)."""

from __future__ import annotations

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


def bootstrap_via_backend(
    config: Mem0Config,
    *,
    source: str | None = None,
) -> None:
    """POST /api/v1/auth/agent_mode/ and mutate config in place.

    Returns nothing — the caller saves the config and prints follow-up messages.
    Raises typer.Exit(1) on failure.
    """
    base_url = (config.platform.base_url or "https://api.mem0.ai").rstrip("/")
    body: dict[str, Any] = {}
    if source:
        body["source"] = source

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
        try:
            detail = resp.json().get("error", resp.text)
        except Exception:
            detail = resp.text
        print_error(err_console, f"Bootstrap failed: {detail}")
        raise typer.Exit(1)

    envelope = resp.json()
    config.platform.api_key = envelope["api_key"]
    config.platform.base_url = base_url
    config.platform.agent_mode = True
    config.platform.created_via = "agent_mode"
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
            body = verify.json()
            detail = body.get("error", verify.text)
            code_str = body.get("code", "")
        except Exception:
            detail = verify.text
            code_str = ""
        print_error(err_console, f"Claim failed: {detail}")
        if code_str == "email_already_claimed":
            console.print(
                f"  [{DIM_COLOR}]Tip: this email already has a Mem0 account. Sign in there and run `mem0 link <key>` to attach this agent.[/]"
            )
        raise typer.Exit(1)

    body = verify.json()
    if not body.get("claimed"):
        print_error(err_console, f"Unexpected verify response: {body}")
        raise typer.Exit(1)

    config.platform.agent_mode = False
    config.platform.claimed_at = body.get("claimed_at") or _utcnow_iso()
    config.platform.user_email = email
    config.platform.created_via = "email"
    save_config(config)
    print_success(console, f"Agent claimed to {email}. Your API key is unchanged.")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
