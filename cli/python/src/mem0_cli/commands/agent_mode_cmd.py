"""Agent Mode commands — bootstrap (unattended signup) and claim (human upgrade)."""

from __future__ import annotations

import secrets
import time
import webbrowser
from datetime import datetime, timezone
from typing import Any

import httpx
import typer
from rich.console import Console

from mem0_cli.branding import (
    DIM_COLOR,
    print_error,
    print_info,
    print_success,
)
from mem0_cli.config import Mem0Config, save_config

console = Console()
err_console = Console(stderr=True)

# Claim polling: 2-second interval, 10-minute timeout matches the backend's
# CLILoginRequest expires_at (15 minutes — we give up before the token does).
_POLL_INTERVAL_SECS = 2
_POLL_TIMEOUT_SECS = 600

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
    console.print(f"  [{DIM_COLOR}]To claim this account later: {envelope.get('claim_command', 'mem0 init --email <your-email>')}[/]")


def claim_via_device_flow(config: Mem0Config, *, email: str) -> None:
    """Run the claim flow against an existing agent-mode config.

    Reuses the existing CLI device flow (initiate_cli_login → frontend OTP →
    associate_cli_token → get_api_key_from_cli_token poll). The raw API key
    never leaves the device — backend confirms claim, CLI updates only
    `platform.agent_mode` and `platform.claimed_at`.
    """
    base_url = (config.platform.base_url or "https://api.mem0.ai").rstrip("/")
    if not config.platform.api_key or not config.platform.agent_mode:
        print_error(
            err_console,
            "This command requires an active Agent Mode config. Run `mem0 init` first.",
        )
        raise typer.Exit(1)

    cli_token = secrets.token_urlsafe(32)
    raw_key = config.platform.api_key

    with httpx.Client(timeout=30.0) as client:
        try:
            init_resp = client.post(
                f"{base_url}/api/v1/accounts/cli_login/",
                json={"token": cli_token, "claim_for_apikey": raw_key},
                headers=_SOURCE_HEADERS,
            )
        except httpx.HTTPError as exc:
            print_error(err_console, f"Could not initiate claim: {exc}")
            raise typer.Exit(1) from exc

        if init_resp.status_code != 200:
            try:
                detail = init_resp.json().get("error", init_resp.text)
            except Exception:
                detail = init_resp.text
            print_error(err_console, f"Could not initiate claim: {detail}")
            raise typer.Exit(1)

        login_url = init_resp.json().get("login_url", "")
        print_info(console, "Open in your browser to claim:")
        console.print(f"  [{DIM_COLOR}]{login_url}[/]")
        try:
            webbrowser.open(login_url)
        except Exception:
            pass  # Printing the URL is sufficient

        # Poll for completion
        deadline = time.monotonic() + _POLL_TIMEOUT_SECS
        while time.monotonic() < deadline:
            time.sleep(_POLL_INTERVAL_SECS)
            try:
                poll = client.post(
                    f"{base_url}/api/v1/accounts/get_api_key_from_cli_token/",
                    json={"token": cli_token},
                    headers=_SOURCE_HEADERS,
                )
            except httpx.HTTPError:
                continue  # transient — keep polling

            if poll.status_code != 200:
                # 400 "Token expired" / "Invalid token" → bail
                try:
                    err = poll.json().get("error", "")
                except Exception:
                    err = poll.text
                if "expired" in err.lower():
                    print_error(err_console, "Claim link expired. Run `mem0 init --email <addr>` again.")
                    raise typer.Exit(1)
                continue

            body = poll.json()
            if body.get("claimed"):
                config.platform.agent_mode = False
                config.platform.claimed_at = body.get("claimed_at") or _utcnow_iso()
                config.platform.user_email = email
                config.platform.created_via = "email"
                save_config(config)
                print_success(console, f"Agent claimed to {email}. Your API key is unchanged.")
                return

    print_error(err_console, "Claim timed out. Run `mem0 init --email <addr>` again.")
    raise typer.Exit(1)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
