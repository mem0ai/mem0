#!/usr/bin/env bash
set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
  printf '%s\n' "Error: python3 is required to run the Mem0 migration. Install Python 3, then rerun this command." >&2
  exit 1
fi

exec python3 - "$@" <<'PY'
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import stat
import sys
import uuid
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.mem0.ai"
POSTHOG_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX"
POSTHOG_CAPTURE_URL = "https://us.i.posthog.com/i/v0/e/"
SCRIPT_VERSION = "oss-to-platform-auth-v1"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class MigrationError(Exception):
    pass


class AuthError(MigrationError):
    pass


class HTTPStatusError(MigrationError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def print_info(message: str) -> None:
    print(message)


def print_error(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)


def mem0_dir() -> Path:
    configured = os.environ.get("MEM0_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".mem0"


def config_path() -> Path:
    return mem0_dir() / "config.json"


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_config(path: Path, config: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, stat.S_IRWXU)
    path.write_text(json.dumps(config, indent=4) + "\n", encoding="utf-8")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def ensure_oss_anon_id(path: Path, config: Dict[str, Any]) -> str:
    existing = config.get("user_id")
    if isinstance(existing, str) and existing:
        return existing

    generated = str(uuid.uuid4())
    config["user_id"] = generated
    try:
        write_config(path, config)
    except Exception:
        # Keep the run usable even on read-only home directories. Telemetry can
        # still use the transient ID for this run.
        pass
    return generated


def read_anon_ids(config: Dict[str, Any], fallback_oss_id: str) -> Dict[str, Any]:
    telemetry = config.get("telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {}
    aliased_pairs = telemetry.get("aliased_pairs")
    if not isinstance(aliased_pairs, list):
        aliased_pairs = []
    return {
        "oss": config.get("user_id") if isinstance(config.get("user_id"), str) else fallback_oss_id,
        "cli": telemetry.get("anonymous_id") if isinstance(telemetry.get("anonymous_id"), str) else None,
        "aliased_pairs": [item for item in aliased_pairs if isinstance(item, str)],
    }


def primary_anon_id(anon_ids: Dict[str, Any]) -> str:
    return anon_ids.get("oss") or anon_ids.get("cli") or "anonymous_user"


def unique_anon_ids(anon_ids: Dict[str, Any]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for anon_id in (anon_ids.get("oss"), anon_ids.get("cli")):
        if not anon_id or anon_id in seen:
            continue
        seen.add(anon_id)
        result.append(anon_id)
    return result


def alias_pair_marker(anon_id: str, email: str) -> str:
    return sha256(f"{anon_id}\0{email}".encode("utf-8")).hexdigest()


def is_aliased(config: Dict[str, Any], anon_id: str, email: str) -> bool:
    telemetry = config.get("telemetry")
    if not isinstance(telemetry, dict):
        return False
    aliased_pairs = telemetry.get("aliased_pairs")
    if not isinstance(aliased_pairs, list):
        return False
    return alias_pair_marker(anon_id, email) in aliased_pairs


def mark_aliased(path: Path, config: Dict[str, Any], anon_id: str, email: str) -> None:
    telemetry = config.get("telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {}
    aliased_pairs = telemetry.get("aliased_pairs")
    if not isinstance(aliased_pairs, list):
        aliased_pairs = []
    marker = alias_pair_marker(anon_id, email)
    if marker not in aliased_pairs:
        aliased_pairs.append(marker)
    telemetry["aliased_pairs"] = aliased_pairs
    config["telemetry"] = telemetry
    write_config(path, config)


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise MigrationError(f"Invalid email address: {email!r}")
    return normalized


def parse_error_body(raw: bytes, fallback: str) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return fallback
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            for key in ("error", "detail", "message"):
                value = parsed.get(key)
                if value:
                    return str(value)
    except Exception:
        pass
    return text


def request_json(
    method: str,
    url: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except HTTPError as exc:
        detail = parse_error_body(exc.read(), exc.reason or f"HTTP {exc.code}")
        raise HTTPStatusError(exc.code, detail) from exc
    except URLError as exc:
        raise MigrationError(f"Network request failed for {url}: {exc.reason}. Check your connection and rerun the command.") from exc

    if not raw:
        return {}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise MigrationError(f"Expected JSON response from {url}") from exc
    return parsed if isinstance(parsed, dict) else {}


def post_json_best_effort(url: str, payload: Dict[str, Any], timeout: float = 5.0) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            resp.read()
            return 200 <= resp.status < 300
    except Exception:
        return False


def telemetry_url() -> str:
    return os.environ.get("MEM0_MIGRATE_TELEMETRY_URL", POSTHOG_CAPTURE_URL)


def base_event_properties(anon_ids: Dict[str, Any], email: Optional[str] = None) -> Dict[str, Any]:
    properties: Dict[str, Any] = {
        "client_source": "python",
        "client_version": SCRIPT_VERSION,
        "migration_phase": "auth",
        "local_anonymous_id": primary_anon_id(anon_ids),
        "oss_anonymous_id": anon_ids.get("oss"),
        "cli_anonymous_id": anon_ids.get("cli"),
        "python_version": sys.version,
        "os": sys.platform,
        "os_version": platform.version(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "timestamp": utc_now(),
        "$lib": "posthog-python",
    }
    if email:
        properties["authenticated_email"] = email
    return properties


def capture_migration_event(
    event_name: str,
    anon_ids: Dict[str, Any],
    *,
    email: Optional[str] = None,
    additional: Optional[Dict[str, Any]] = None,
) -> bool:
    distinct_id = email or primary_anon_id(anon_ids)
    properties = base_event_properties(anon_ids, email)
    if additional:
        properties.update(additional)
    payload = {
        "api_key": POSTHOG_API_KEY,
        "distinct_id": distinct_id,
        "event": event_name,
        "properties": properties,
    }
    return post_json_best_effort(telemetry_url(), payload)


def capture_identify(anon_id: str, email: str) -> bool:
    if not anon_id or not email or anon_id == email:
        return False
    payload = {
        "api_key": POSTHOG_API_KEY,
        "distinct_id": email,
        "event": "$identify",
        "properties": {
            "$anon_distinct_id": anon_id,
            "client_source": "python",
            "client_version": SCRIPT_VERSION,
            "$lib": "posthog-python",
        },
    }
    return post_json_best_effort(telemetry_url(), payload)


def stitch_identities(config_path_value: Path, config: Dict[str, Any], anon_ids: Dict[str, Any], email: str) -> None:
    for anon_id in unique_anon_ids(anon_ids):
        if anon_id == email or is_aliased(config, anon_id, email):
            continue
        if capture_identify(anon_id, email):
            try:
                mark_aliased(config_path_value, config, anon_id, email)
            except Exception:
                pass


def auth_headers(language: str = "python") -> Dict[str, str]:
    return {
        "X-Mem0-Source": "migration",
        "X-Mem0-Client-Language": language,
        "X-Mem0-Client-Version": SCRIPT_VERSION,
    }


def api_base_url(args: argparse.Namespace, config: Dict[str, Any]) -> str:
    platform_config = config.get("platform") if isinstance(config.get("platform"), dict) else {}
    value = args.base_url or os.environ.get("MEM0_BASE_URL") or platform_config.get("base_url") or DEFAULT_BASE_URL
    return str(value).rstrip("/")


def configured_api_key(args: argparse.Namespace, config: Dict[str, Any]) -> Tuple[Optional[str], str]:
    if args.api_key:
        return args.api_key, "flag"
    env_key = os.environ.get("MEM0_API_KEY")
    if env_key:
        return env_key, "env"
    platform_config = config.get("platform") if isinstance(config.get("platform"), dict) else {}
    file_key = platform_config.get("api_key")
    if isinstance(file_key, str) and file_key:
        return file_key, "config"
    return None, ""


def validate_api_key(api_key: str, base_url: str) -> str:
    try:
        result = request_json(
            "GET",
            f"{base_url}/v1/ping/",
            headers={"Authorization": f"Token {api_key}"},
            timeout=5.0,
        )
    except HTTPStatusError as exc:
        if exc.status_code == 401:
            raise AuthError("Invalid or expired API key.") from exc
        raise

    email = result.get("user_email")
    if not isinstance(email, str) or not email:
        raise MigrationError("Platform authenticated the API key but did not return an account email.")
    return normalize_email(email)


def prompt_line(prompt: str) -> str:
    try:
        with open("/dev/tty", "r", encoding="utf-8") as tty_in, open("/dev/tty", "w", encoding="utf-8") as tty_out:
            tty_out.write(prompt)
            tty_out.flush()
            line = tty_in.readline()
    except OSError as exc:
        raise MigrationError(
            "No interactive terminal is available. Re-run with --email and --code, or use --yes with a valid API key."
        ) from exc

    if line == "":
        raise MigrationError("No input received from terminal.")
    return line.strip()


def ensure_interactive_terminal() -> None:
    try:
        with open("/dev/tty", "r", encoding="utf-8"), open("/dev/tty", "w", encoding="utf-8"):
            return
    except OSError as exc:
        raise MigrationError(
            "No interactive terminal is available. Re-run with --email and --code, or use --yes with a valid API key."
        ) from exc


def prompt_yes_no(prompt: str, *, default: bool = True) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = prompt_line(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def request_email_code(email: str, base_url: str) -> None:
    try:
        request_json(
            "POST",
            f"{base_url}/api/v1/auth/email_code/",
            payload={"email": email},
            headers=auth_headers(),
        )
    except HTTPStatusError as exc:
        if exc.status_code == 429:
            raise MigrationError("Too many attempts. Try again in a few minutes.") from exc
        raise MigrationError(f"Failed to send verification code: {exc.detail}") from exc


def verify_email_code(email: str, code: str, base_url: str) -> str:
    try:
        result = request_json(
            "POST",
            f"{base_url}/api/v1/auth/email_code/verify/",
            payload={"email": email, "code": code.strip()},
            headers=auth_headers(),
        )
    except HTTPStatusError as exc:
        if exc.status_code == 429:
            raise MigrationError("Too many attempts. Try again in a few minutes.") from exc
        raise MigrationError(f"Verification failed: {exc.detail}") from exc

    api_key = result.get("api_key")
    if not isinstance(api_key, str) or not api_key:
        raise MigrationError("Auth succeeded but no API key was returned. Contact support.")
    return api_key


def email_code_auth(args: argparse.Namespace, base_url: str) -> Tuple[str, str, str]:
    email = normalize_email(args.email) if args.email else normalize_email(prompt_line("Email: "))
    code = args.code

    if not code:
        ensure_interactive_terminal()
        request_email_code(email, base_url)
        print_info("Verification code sent. Check your email.")
        code = prompt_line("Verification code: ")
        if not code:
            raise MigrationError("Verification code is required.")

    api_key = verify_email_code(email, code, base_url)
    resolved_email = validate_api_key(api_key, base_url)
    return api_key, resolved_email, "email_code"


def existing_session_auth(args: argparse.Namespace, api_key: str, key_source: str, base_url: str) -> Optional[Tuple[str, str, str]]:
    try:
        email = validate_api_key(api_key, base_url)
    except AuthError:
        if key_source in ("flag", "env"):
            raise
        print_info("Stored Mem0 Platform API key is invalid or expired. Continuing with email login.")
        return None
    except MigrationError:
        if key_source in ("flag", "env"):
            raise
        print_info("Could not validate stored Mem0 Platform session. Continuing with email login.")
        return None

    if args.email:
        return None

    if not args.yes:
        print_info("")
        print_info("Found an existing Mem0 Platform session.")
        print_info("")
        print_info(f"Account: {email}")
        print_info("This migration will copy your local OSS memories into this Platform account.")
        print_info("")
        if not prompt_yes_no(f"Continue with {email}?", default=True):
            return None

    return api_key, email, "existing_api_key"


def resolve_auth(args: argparse.Namespace, config: Dict[str, Any], base_url: str) -> Tuple[str, str, str]:
    if args.api_key and args.email:
        raise MigrationError("Cannot use both --api-key and --email.")
    if args.code and not args.email:
        raise MigrationError("--code requires --email.")

    api_key, key_source = configured_api_key(args, config)
    if api_key:
        result = existing_session_auth(args, api_key, key_source, base_url)
        if result:
            return result

    return email_code_auth(args, base_url)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="oss-to-platform-migrate.sh",
        description="Authenticate a local Mem0 OSS migration to a Mem0 Platform account.",
    )
    parser.add_argument("--auth-only", action="store_true", help="Run only auth/account resolution.")
    parser.add_argument("--email", help="Email address for email-code authentication.")
    parser.add_argument("--code", help="Verification code for non-interactive email-code authentication.")
    parser.add_argument("--api-key", help="Platform API key to use for this run only.")
    parser.add_argument("--base-url", help=f"Mem0 Platform API base URL. Defaults to {DEFAULT_BASE_URL}.")
    parser.add_argument("--yes", action="store_true", help="Accept an existing valid Platform session without prompting.")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    path = config_path()
    config = load_config(path)
    oss_anon_id = ensure_oss_anon_id(path, config)
    anon_ids = read_anon_ids(config, oss_anon_id)
    base_url = api_base_url(args, config)

    print_info("Mem0 OSS to Platform migration")
    print_info("Auth phase")
    print_info("Supported environments: macOS, Linux, and Windows via WSL/Git Bash with bash and python3.")
    print_info("No memories are imported during this auth step.")
    print_info("")

    capture_migration_event("oss.migrate.started", anon_ids, additional={"base_url": base_url})

    try:
        _api_key, email, auth_method = resolve_auth(args, config, base_url)
        capture_migration_event(
            "oss.migrate.authenticated",
            anon_ids,
            email=email,
            additional={"auth_method": auth_method, "base_url": base_url},
        )
        stitch_identities(path, config, anon_ids, email)
    except MigrationError as exc:
        capture_migration_event(
            "oss.migrate.failed",
            anon_ids,
            additional={"error": str(exc), "base_url": base_url, "phase": "auth"},
        )
        print_error(str(exc))
        return 1

    print_info(f"Authenticated as {email}")
    if args.auth_only:
        print_info("Auth-only mode complete. Export and import were not run.")
    else:
        print_info("Auth complete. Export and import will be added in the next migration phase.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
PY
