"""mem0 init — interactive setup wizard."""

from __future__ import annotations

import os
import re
import sys

import httpx
import typer
from rich.console import Console
from rich.prompt import Prompt

from mem0_cli.branding import (
    BRAND_COLOR,
    DIM_COLOR,
    print_banner,
    print_error,
    print_info,
    print_success,
)
from mem0_cli.config import (
    CONFIG_FILE,
    DEFAULT_BASE_URL,
    Mem0Config,
    load_config,
    save_config,
)

console = Console()
err_console = Console(stderr=True)


def _prompt_secret(label: str) -> str:
    """Prompt for a secret value, echoing '*' for each character typed."""
    sys.stdout.write(label)
    sys.stdout.flush()

    chars: list[str] = []

    if sys.platform == "win32":
        import msvcrt

        while True:
            ch = msvcrt.getwch()
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                break
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch in ("\x08", "\x7f"):  # backspace
                if chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
            else:
                chars.append(ch)
                sys.stdout.write("*")
                sys.stdout.flush()
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\r", "\n"):
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    break
                if ch == "\x03":
                    raise KeyboardInterrupt
                if ch in ("\x7f", "\x08"):  # backspace/delete
                    if chars:
                        chars.pop()
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                elif ch == "\x15":  # Ctrl+U — clear line
                    sys.stdout.write("\b \b" * len(chars))
                    sys.stdout.flush()
                    chars = []
                elif ch >= " ":  # ignore other control characters
                    chars.append(ch)
                    sys.stdout.write("*")
                    sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return "".join(chars)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(email: str) -> None:
    """Exit with an error if *email* doesn't look like a valid address."""
    if not _EMAIL_RE.match(email):
        print_error(err_console, f"Invalid email address: {email!r}")
        raise typer.Exit(1)


def _ping_key(api_key: str, base_url: str, timeout: float = 5.0) -> bool:
    """Validate api_key against /v1/ping/.

    Returns False ONLY on a definitive "invalid key" signal (HTTP 401 / 403).
    Network errors, timeouts, and 5xx responses return True so we prefer
    reusing an existing key over silently minting a new shadow on a transient
    blip (which would also clobber config + plugin-sync targets).
    """
    try:
        resp = httpx.get(
            f"{base_url.rstrip('/')}/v1/ping/",
            headers={"Authorization": f"Token {api_key}"},
            timeout=timeout,
        )
    except httpx.HTTPError:
        return True  # unknown — prefer reuse
    return resp.status_code not in (401, 403)


def _email_login(
    email: str,
    code: str | None,
    base_url: str,
) -> dict:
    """Run the email verification code login flow.

    Returns the parsed JSON response from the verify endpoint.
    The caller expects at minimum an ``api_key`` field.
    """
    url = base_url.rstrip("/")
    _source_headers = {
        "X-Mem0-Source": "cli",
        "X-Mem0-Client-Language": "python",
    }

    with httpx.Client(timeout=30.0) as client:
        # If code is already provided, skip sending — user already has a code
        if not code:
            # Step 1: Request verification code
            resp = client.post(
                f"{url}/api/v1/auth/email_code/",
                json={"email": email},
                headers=_source_headers,
            )
            if resp.status_code == 429:
                print_error(err_console, "Too many attempts. Try again in a few minutes.")
                raise typer.Exit(1)
            if resp.status_code != 200:
                try:
                    detail = resp.json().get("error", resp.text)
                except Exception:
                    detail = resp.text
                print_error(err_console, f"Failed to send code: {detail}")
                raise typer.Exit(1)

            print_success(console, "Verification code sent! Check your email.")

            # Step 2: Get code from user
            if not sys.stdin.isatty():
                print_error(
                    err_console,
                    "No --code provided and terminal is non-interactive.",
                    hint="Run: mem0 init --email <email> --code <code>",
                )
                raise typer.Exit(1)
            console.print()
            code = Prompt.ask(f"  [{BRAND_COLOR}]Verification Code[/]")
            if not code:
                print_error(err_console, "Code is required.")
                raise typer.Exit(1)

        # Step 3: Verify code
        resp = client.post(
            f"{url}/api/v1/auth/email_code/verify/",
            json={"email": email, "code": code.strip()},
            headers=_source_headers,
        )
        if resp.status_code == 429:
            print_error(err_console, "Too many attempts. Try again in a few minutes.")
            raise typer.Exit(1)
        if resp.status_code != 200:
            try:
                detail = resp.json().get("error", resp.text)
            except Exception:
                detail = resp.text
            print_error(err_console, f"Verification failed: {detail}")
            raise typer.Exit(1)

        return resp.json()


def run_init(
    *,
    api_key: str | None = None,
    user_id: str | None = None,
    email: str | None = None,
    code: str | None = None,
    force: bool = False,
    source: str | None = None,
    agent: bool = False,
    agent_caller: str | None = None,
) -> None:
    """Interactive setup wizard for mem0 CLI.

    When both *api_key* and *user_id* are supplied, all prompts are skipped
    (non-interactive mode).  When running in a non-TTY without the required
    flags, an error message is printed.

    Agent Mode dispatch (no email/api-key flags):
      - If existing config has an active API key → reuse (existing_key path).
      - Else if any positive agent signal (--agent, --json global, agent env
        var, or `agent` flag) → POST /api/v1/auth/agent_mode/ and write config.
      - Else fall through to the interactive wizard.

    Claim dispatch:
      - If `--email` is set AND existing config has `agent_mode=true`, run the
        claim device-flow against the existing key instead of minting a new
        email-based key.
    """
    from mem0_cli.agent_detect import detect_agent_caller
    from mem0_cli.commands.agent_mode_cmd import bootstrap_via_backend, claim_via_otp
    from mem0_cli.state import is_agent_mode as _global_agent_mode
    from mem0_cli.telemetry import capture_event

    def _fire_init(mode: str, *, claimed: bool = False) -> None:
        """Fire cli.init telemetry with M1-M6 properties."""
        props: dict = {"command": "init", "mode": mode}
        if agent_caller:
            # Self-declared via --agent-caller; not sniffed from env vars.
            props["agent_caller"] = agent_caller
        if source:
            props["signup_source"] = source
        if claimed:
            props["claimed_agent_mode"] = True
        capture_event("cli.init", props)

    config = Mem0Config()

    base_url = os.environ.get("MEM0_BASE_URL", config.platform.base_url or DEFAULT_BASE_URL)
    config.platform.base_url = base_url

    if code and not email:
        print_error(err_console, "--code requires --email.")
        raise typer.Exit(1)

    # ── Email + existing agent-mode config → claim flow ─────────────────
    if email and CONFIG_FILE.exists():
        existing = load_config()
        if existing.platform.agent_mode and existing.platform.api_key:
            email = email.strip().lower()
            _validate_email(email)
            print_info(console, f"Claiming Agent Mode account to {email}...")
            claim_via_otp(existing, email=email, code=code)
            _fire_init("email", claimed=True)
            return

    # ── Agent Mode path runs BEFORE the existing-config guard ──────────
    # Rules 1/2 REUSE a valid existing key (not overwrite), so we must
    # short-circuit before the guard prompts. Rule 3 mints only when there
    # is no valid key to reuse — in that case overwriting is correct.
    _agent_ctx = agent or _global_agent_mode() or (detect_agent_caller() is not None)
    if not api_key and not email and _agent_ctx:
        from mem0_cli.output import format_json_envelope
        from mem0_cli.state import is_agent_mode as _is_json_mode

        def _emit_reuse(source: str) -> None:
            if _is_json_mode():
                format_json_envelope(
                    console,
                    command="init",
                    data={
                        "api_key_saved": False,
                        "api_key_source": source,
                        "agent_mode": False,
                        "message": "Existing Mem0 API key found and reused. No Agent Mode key was created.",
                    },
                )
            else:
                msg = (
                    "Existing MEM0_API_KEY is valid; reusing it. No new Agent Mode key was minted."
                    if source == "env"
                    else "Existing API key in config is valid; reusing it. No new Agent Mode key was minted."
                )
                print_success(console, msg)

        def _maybe_identify(key: str) -> None:
            """Best-effort PATCH agent_caller when --agent-caller is supplied on a
            reused key. Silent no-op on any failure — reuse must not break.
            """
            if not agent_caller:
                return
            try:
                resp = httpx.patch(
                    f"{base_url.rstrip('/')}/api/v1/auth/agent_mode/caller/",
                    headers={
                        "Authorization": f"Token {key}",
                        "Content-Type": "application/json",
                    },
                    json={"agent_caller": agent_caller},
                    timeout=10.0,
                )
                # Also reflect in local config so introspection matches backend.
                if resp.status_code == 200 and CONFIG_FILE.exists():
                    try:
                        cfg = load_config()
                        cfg.platform.agent_caller = resp.json().get("agent_caller", agent_caller)
                        save_config(cfg)
                    except Exception:
                        pass
            except httpx.HTTPError:
                pass

        # Rule 1: env MEM0_API_KEY valid → reuse, no new key.
        _env_key = (os.environ.get("MEM0_API_KEY") or "").strip()
        if _env_key and _ping_key(_env_key, base_url):
            _maybe_identify(_env_key)
            _emit_reuse("env")
            _fire_init("existing_key")
            return
        # Rule 2: existing config api_key valid → reuse.
        if CONFIG_FILE.exists():
            _existing = load_config()
            if _existing.platform.api_key and _ping_key(_existing.platform.api_key, base_url):
                _maybe_identify(_existing.platform.api_key)
                _emit_reuse("config")
                _fire_init("existing_key")
                return
        # Rule 3: mint a fresh shadow (no valid key to reuse).
        # agent_caller is the agent's self-declared identity from --agent-caller
        # (Proof Editor-style). Env-var auto-detect is still used above to
        # decide we're in an agent context, but never to fill identity.
        bootstrap_via_backend(config, source=source, agent_caller=agent_caller)
        _fire_init("agent")
        return

    # Warn if an existing config with an API key would be overwritten
    if not force and CONFIG_FILE.exists():
        existing = load_config()
        if existing.platform.api_key:
            from mem0_cli.config import redact_key

            console.print(
                f"\n  [{BRAND_COLOR}]Existing configuration found[/] "
                f"[{DIM_COLOR}](API key: {redact_key(existing.platform.api_key)})[/]"
            )
            if sys.stdin.isatty():
                confirm = typer.confirm("  Overwrite existing config? This cannot be undone.")
                if not confirm:
                    print_info(console, "Cancelled. Use --force to skip this check.")
                    raise typer.Exit(0)
            else:
                print_error(
                    err_console,
                    "Existing config would be overwritten.",
                    hint="Use --force to overwrite.",
                )
                raise typer.Exit(1)

    # ── Email login flow ──────────────────────────────────────────────
    if email:
        if api_key:
            print_error(err_console, "Cannot use both --api-key and --email.")
            raise typer.Exit(1)

        email = email.strip().lower()
        _validate_email(email)

        print_banner(console)
        console.print()
        print_info(console, f"Logging in as {email}...\n")

        result = _email_login(email, code, base_url)

        api_key_val = result.get("api_key")
        if not api_key_val:
            print_error(err_console, "Auth succeeded but no API key was returned. Contact support.")
            raise typer.Exit(1)
        config.platform.api_key = api_key_val
        config.platform.base_url = base_url
        config.platform.user_email = email
        config.platform.created_via = "email"
        config.defaults.user_id = (
            user_id or os.environ.get("USER") or os.environ.get("USERNAME") or "mem0-cli"
        )

        save_config(config)

        console.print()
        print_success(console, "Authenticated! Configuration saved to ~/.mem0/config.json")
        console.print()
        console.print(f"  [{DIM_COLOR}]Get started:[/]")
        console.print(f'  [{DIM_COLOR}]  mem0 add "I prefer dark mode"[/]')
        console.print(f'  [{DIM_COLOR}]  mem0 search "preferences"[/]')
        console.print()
        return

    # ── API key flow (existing) ───────────────────────────────────────
    # (Agent Mode branch runs earlier — see above, before the existing-config
    # guard, so Rules 1/2 can REUSE a valid key without prompting overwrite.)

    # Non-TTY: resolve defaults so partial flags work in pipelines / CI
    if not sys.stdin.isatty():
        if not api_key:
            print_error(
                err_console,
                "Non-interactive terminal detected and --api-key is required.",
                hint="Run: mem0 init --api-key <key>, --email <addr>, or --agent for unattended Agent Mode bootstrap.",
            )
            raise typer.Exit(1)
        user_id = user_id or os.environ.get("USER") or os.environ.get("USERNAME") or "mem0-cli"

    # Fully non-interactive when both flags provided
    if api_key and user_id:
        config.platform.api_key = api_key
        config.platform.created_via = "api_key"
        config.defaults.user_id = user_id
        _validate_platform(config)
        save_config(config)
        print_success(console, "Configuration saved to ~/.mem0/config.json")
        return

    print_banner(console)
    console.print()
    print_info(console, "Welcome! Let's set up your mem0 CLI.\n")

    # If no flags at all, ask user how they want to authenticate
    if not api_key:
        console.print(f"  [{BRAND_COLOR}]How would you like to authenticate?[/]")
        console.print(f"  [{DIM_COLOR}]1.[/] Login with email [{DIM_COLOR}](recommended)[/]")
        console.print(f"  [{DIM_COLOR}]2.[/] Enter API key manually")
        console.print()
        choice = Prompt.ask(f"  [{BRAND_COLOR}]Choose[/]", choices=["1", "2"], default="1")

        if choice == "1":
            console.print()
            email_addr = Prompt.ask(f"  [{BRAND_COLOR}]Email[/]")
            if not email_addr:
                print_error(err_console, "Email is required.")
                raise typer.Exit(1)

            email_addr = email_addr.strip().lower()
            _validate_email(email_addr)
            print_info(console, f"Logging in as {email_addr}...\n")

            result = _email_login(email_addr, None, base_url)

            api_key_val = result.get("api_key")
            if not api_key_val:
                print_error(
                    err_console, "Auth succeeded but no API key was returned. Contact support."
                )
                raise typer.Exit(1)
            config.platform.api_key = api_key_val
            config.platform.base_url = base_url
            config.platform.user_email = email_addr
            config.platform.created_via = "email"
            config.defaults.user_id = (
                user_id or os.environ.get("USER") or os.environ.get("USERNAME") or "mem0-cli"
            )

            save_config(config)

            console.print()
            print_success(console, "Authenticated! Configuration saved to ~/.mem0/config.json")
            console.print()
            console.print(f"  [{DIM_COLOR}]Get started:[/]")
            console.print(f'  [{DIM_COLOR}]  mem0 add "I prefer dark mode"[/]')
            console.print(f'  [{DIM_COLOR}]  mem0 search "preferences"[/]')
            console.print()
            return

    # API key flow
    if api_key:
        config.platform.api_key = api_key
        config.platform.created_via = "api_key"
    else:
        _setup_platform(config)

    if user_id:
        config.defaults.user_id = user_id
    else:
        _setup_defaults(config)

    _validate_platform(config)

    save_config(config)
    console.print()
    print_success(console, "Configuration saved to ~/.mem0/config.json")
    console.print()
    console.print(f"  [{DIM_COLOR}]Get started:[/]")
    if config.defaults.user_id:
        console.print(f'  [{DIM_COLOR}]  mem0 add "I prefer dark mode"[/]')
        console.print(f'  [{DIM_COLOR}]  mem0 search "preferences"[/]')
    else:
        console.print(f'  [{DIM_COLOR}]  mem0 add "I prefer dark mode" --user-id alice[/]')
        console.print(f'  [{DIM_COLOR}]  mem0 search "preferences" --user-id alice[/]')
    console.print()


def _setup_platform(config: Mem0Config) -> None:
    """Platform setup flow."""
    console.print()
    console.print(
        f"  [{DIM_COLOR}]Get your API key at https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=cli-python[/]"
    )
    console.print()

    console.print(f"  [{BRAND_COLOR}]API Key[/]: ", end="")
    api_key = _prompt_secret("")
    if not api_key:
        print_error(err_console, "API key is required.")
        raise typer.Exit(1)

    config.platform.api_key = api_key
    config.platform.created_via = "api_key"


def _setup_defaults(config: Mem0Config) -> None:
    """Collect default entity IDs."""
    console.print()
    print_info(console, "Set default entity IDs (press Enter to skip).\n")

    _default_user = os.environ.get("USER") or os.environ.get("USERNAME") or "mem0-cli"
    user_id = Prompt.ask(
        f"  [{BRAND_COLOR}]Default User ID[/] [{DIM_COLOR}](recommended)[/]",
        default=_default_user,
    )
    if user_id:
        config.defaults.user_id = user_id


def _validate_platform(config: Mem0Config) -> None:
    """Validate platform connection after all inputs are collected."""
    console.print()
    print_info(console, "Validating connection...")
    try:
        from mem0_cli.backend.platform import PlatformBackend

        backend = PlatformBackend(config.platform)
        status = backend.status(
            user_id=config.defaults.user_id or None,
            agent_id=config.defaults.agent_id or None,
        )
        if status.get("connected"):
            print_success(console, "Connected to mem0 Platform!")
            # Cache user_email from ping response for telemetry distinct_id
            try:
                ping_data = backend.ping()
                user_email = ping_data.get("user_email") if isinstance(ping_data, dict) else None
                if user_email:
                    config.platform.user_email = user_email
            except Exception:
                pass
        else:
            print_error(
                err_console,
                f"Could not connect: {status.get('error', 'Unknown error')}",
                hint="Visit https://app.mem0.ai/dashboard/api-keys?utm_source=oss&utm_medium=cli-python to get a new key, then run mem0 init again.",
            )
    except Exception as e:
        print_error(err_console, f"Connection test failed: {e}")
