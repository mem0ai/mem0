from __future__ import annotations

import json
import os
import subprocess
import threading
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "oss-to-platform-migrate.sh"


class MigrationHTTPServer:
    def __init__(
        self,
        *,
        ping_emails: dict[str, str] | None = None,
        verify_api_key: str = "verified-key",
        verify_status: int = 200,
        qdrant_api_key: str = "qdrant-key",
        qdrant_collection: str = "mem0",
        qdrant_pages: list[dict[str, Any]] | None = None,
    ) -> None:
        self.ping_emails = ping_emails or {}
        self.verify_api_key = verify_api_key
        self.verify_status = verify_status
        self.qdrant_api_key = qdrant_api_key
        self.qdrant_collection = qdrant_collection
        self.qdrant_pages = qdrant_pages or [{"points": [], "next_page_offset": None}]
        self.requests: list[dict[str, Any]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> "MigrationHTTPServer":
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b""
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _record(self, body: dict[str, Any] | None = None) -> None:
                owner.requests.append(
                    {
                        "method": self.command,
                        "path": self.path,
                        "headers": dict(self.headers),
                        "body": body or {},
                    }
                )

            def do_GET(self) -> None:
                self._record()
                if self.path == "/v1/ping/":
                    auth = self.headers.get("Authorization", "")
                    token = auth.removeprefix("Token ")
                    email = owner.ping_emails.get(token)
                    if email:
                        self._send_json(200, {"user_email": email})
                    else:
                        self._send_json(401, {"detail": "Invalid token"})
                    return
                if self.path == f"/collections/{owner.qdrant_collection}":
                    if self.headers.get("api-key") != owner.qdrant_api_key:
                        self._send_json(401, {"status": {"error": "unauthorized"}})
                    else:
                        self._send_json(200, {"result": {"status": "green"}, "status": "ok"})
                    return
                self._send_json(404, {"detail": "Not found"})

            def do_POST(self) -> None:
                body = self._read_json()
                self._record(body)
                if self.path == "/posthog":
                    self._send_json(200, {"ok": True})
                    return
                if self.path == "/api/v1/auth/email_code/":
                    self._send_json(200, {"sent": True})
                    return
                if self.path == "/api/v1/auth/email_code/verify/":
                    if owner.verify_status != 200:
                        self._send_json(owner.verify_status, {"error": "bad verification code"})
                    else:
                        self._send_json(200, {"api_key": owner.verify_api_key})
                    return
                if self.path == f"/collections/{owner.qdrant_collection}/points/scroll":
                    if self.headers.get("api-key") != owner.qdrant_api_key:
                        self._send_json(401, {"status": {"error": "unauthorized"}})
                        return
                    offset = body.get("offset")
                    page_index = int(offset) if offset is not None else 0
                    page = owner.qdrant_pages[page_index]
                    self._send_json(
                        200,
                        {
                            "result": {
                                "points": page["points"],
                                "next_page_offset": page.get("next_page_offset"),
                            },
                            "status": "ok",
                        },
                    )
                    return
                self._send_json(404, {"detail": "Not found"})

        return Handler


def alias_marker(anon_id: str, email: str) -> str:
    return sha256(f"{anon_id}\0{email}".encode("utf-8")).hexdigest()


def write_config(mem0_dir: Path, data: dict[str, Any]) -> None:
    mem0_dir.mkdir(parents=True, exist_ok=True)
    (mem0_dir / "config.json").write_text(json.dumps(data), encoding="utf-8")


def read_config(mem0_dir: Path) -> dict[str, Any]:
    return json.loads((mem0_dir / "config.json").read_text(encoding="utf-8"))


def run_migration_script(
    tmp_path: Path,
    server: MigrationHTTPServer,
    *args: str,
    config: dict[str, Any] | None = None,
    raw_config: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    mem0_dir = tmp_path / "mem0"
    if config is not None:
        write_config(mem0_dir, config)
    if raw_config is not None:
        mem0_dir.mkdir(parents=True, exist_ok=True)
        (mem0_dir / "config.json").write_text(raw_config, encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "MEM0_DIR": str(mem0_dir),
            "MEM0_MIGRATE_TELEMETRY_URL": f"{server.url}/posthog",
        }
    )
    env.pop("MEM0_API_KEY", None)
    env.pop("MEM0_BASE_URL", None)

    result = subprocess.run(
        ["bash", str(SCRIPT), "--auth-only", "--base-url", server.url, *args],
        capture_output=True,
        text=True,
        env=env,
        start_new_session=True,
        timeout=20,
        check=False,
    )
    return result, mem0_dir


def run_export_script(
    tmp_path: Path,
    server: MigrationHTTPServer,
    *args: str,
    config: dict[str, Any] | None = None,
    qdrant_api_key: str = "qdrant-key",
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    mem0_dir = tmp_path / "mem0"
    output_path = tmp_path / "export.json"
    if config is not None:
        write_config(mem0_dir, config)

    env = os.environ.copy()
    env.update(
        {
            "MEM0_DIR": str(mem0_dir),
            "MEM0_MIGRATE_TELEMETRY_URL": f"{server.url}/posthog",
            "QDRANT_API_KEY": qdrant_api_key,
        }
    )
    env.pop("MEM0_API_KEY", None)
    env.pop("MEM0_BASE_URL", None)

    result = subprocess.run(
        [
            "bash",
            str(SCRIPT),
            "--export-only",
            "--qdrant-url",
            server.url,
            "--qdrant-collection",
            server.qdrant_collection,
            "--output",
            str(output_path),
            *args,
        ],
        capture_output=True,
        text=True,
        env=env,
        start_new_session=True,
        timeout=20,
        check=False,
    )
    return result, mem0_dir, output_path


def posthog_events(server: MigrationHTTPServer) -> list[dict[str, Any]]:
    return [request["body"] for request in server.requests if request["path"] == "/posthog"]


def test_existing_api_key_authenticates_and_stitches_ids(tmp_path: Path) -> None:
    config = {
        "user_id": "oss-123",
        "platform": {"api_key": "stored-key", "base_url": "https://api.mem0.ai"},
        "telemetry": {"anonymous_id": "cli-456"},
    }

    with MigrationHTTPServer(ping_emails={"stored-key": "bob@example.com"}) as server:
        result, mem0_dir = run_migration_script(tmp_path, server, "--yes", config=config)

    assert result.returncode == 0, result.stderr
    assert "Authenticated as bob@example.com" in result.stdout
    assert not any(request["path"] == "/api/v1/auth/email_code/verify/" for request in server.requests)

    updated = read_config(mem0_dir)
    assert updated["platform"] == config["platform"]
    assert alias_marker("oss-123", "bob@example.com") in updated["telemetry"]["aliased_pairs"]
    assert alias_marker("cli-456", "bob@example.com") in updated["telemetry"]["aliased_pairs"]

    events = posthog_events(server)
    event_names = [event["event"] for event in events]
    assert "oss.migrate.started" in event_names
    assert "oss.migrate.authenticated" in event_names
    assert event_names.count("$identify") == 2

    authenticated = next(event for event in events if event["event"] == "oss.migrate.authenticated")
    assert authenticated["distinct_id"] == "bob@example.com"
    assert authenticated["properties"]["local_anonymous_id"] == "oss-123"
    assert authenticated["properties"]["authenticated_email"] == "bob@example.com"


def test_email_code_authenticates_without_persisting_credentials(tmp_path: Path) -> None:
    with MigrationHTTPServer(ping_emails={"verified-key": "alice@example.com"}) as server:
        result, mem0_dir = run_migration_script(
            tmp_path,
            server,
            "--email",
            "Alice@Example.COM",
            "--code",
            "123456",
        )

    assert result.returncode == 0, result.stderr
    assert "Authenticated as alice@example.com" in result.stdout

    verify_request = next(request for request in server.requests if request["path"] == "/api/v1/auth/email_code/verify/")
    assert verify_request["body"] == {"email": "alice@example.com", "code": "123456"}
    assert not any(request["path"] == "/api/v1/auth/email_code/" for request in server.requests)

    updated = read_config(mem0_dir)
    assert "api_key" not in updated.get("platform", {})
    assert "user_email" not in updated.get("platform", {})
    assert updated["user_id"]
    assert alias_marker(updated["user_id"], "alice@example.com") in updated["telemetry"]["aliased_pairs"]

    events = posthog_events(server)
    assert [event["event"] for event in events].count("$identify") == 1
    authenticated = next(event for event in events if event["event"] == "oss.migrate.authenticated")
    assert authenticated["properties"]["auth_method"] == "email_code"


def test_invalid_stored_key_falls_back_to_email_code(tmp_path: Path) -> None:
    config = {
        "user_id": "oss-fallback",
        "platform": {"api_key": "bad-key", "base_url": "https://api.mem0.ai"},
    }

    with MigrationHTTPServer(ping_emails={"verified-key": "new@example.com"}) as server:
        result, mem0_dir = run_migration_script(
            tmp_path,
            server,
            "--email",
            "new@example.com",
            "--code",
            "123456",
            config=config,
        )

    assert result.returncode == 0, result.stderr
    assert "Stored Mem0 Platform API key is invalid or expired" in result.stdout
    assert "Authenticated as new@example.com" in result.stdout

    ping_tokens = [
        request["headers"]["Authorization"].removeprefix("Token ")
        for request in server.requests
        if request["path"] == "/v1/ping/"
    ]
    assert ping_tokens == ["bad-key", "verified-key"]

    updated = read_config(mem0_dir)
    assert updated["platform"] == config["platform"]
    assert alias_marker("oss-fallback", "new@example.com") in updated["telemetry"]["aliased_pairs"]


def test_email_code_failure_reports_failed_telemetry(tmp_path: Path) -> None:
    with MigrationHTTPServer(verify_status=400) as server:
        result, mem0_dir = run_migration_script(
            tmp_path,
            server,
            "--email",
            "fail@example.com",
            "--code",
            "bad",
        )

    assert result.returncode == 1
    assert "Verification failed: bad verification code" in result.stderr

    updated = read_config(mem0_dir)
    assert "telemetry" not in updated or "aliased_pairs" not in updated["telemetry"]

    events = posthog_events(server)
    event_names = [event["event"] for event in events]
    assert "oss.migrate.started" in event_names
    assert "oss.migrate.failed" in event_names
    assert "$identify" not in event_names
    failed = next(event for event in events if event["event"] == "oss.migrate.failed")
    assert "Verification failed" in failed["properties"]["error"]


def test_malformed_config_does_not_crash_and_authenticates(tmp_path: Path) -> None:
    with MigrationHTTPServer(ping_emails={"verified-key": "malformed@example.com"}) as server:
        result, mem0_dir = run_migration_script(
            tmp_path,
            server,
            "--email",
            "malformed@example.com",
            "--code",
            "123456",
            raw_config="{not valid json",
        )

    assert result.returncode == 0, result.stderr
    assert "Authenticated as malformed@example.com" in result.stdout

    updated = read_config(mem0_dir)
    assert updated["user_id"]
    assert alias_marker(updated["user_id"], "malformed@example.com") in updated["telemetry"]["aliased_pairs"]


def test_weird_telemetry_shape_does_not_crash(tmp_path: Path) -> None:
    config = {"user_id": "oss-weird-telemetry", "telemetry": "not-an-object"}

    with MigrationHTTPServer(ping_emails={"verified-key": "weird@example.com"}) as server:
        result, mem0_dir = run_migration_script(
            tmp_path,
            server,
            "--email",
            "weird@example.com",
            "--code",
            "123456",
            config=config,
        )

    assert result.returncode == 0, result.stderr
    updated = read_config(mem0_dir)
    assert isinstance(updated["telemetry"], dict)
    assert alias_marker("oss-weird-telemetry", "weird@example.com") in updated["telemetry"]["aliased_pairs"]


def test_missing_python3_prints_clear_shell_error(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PATH"] = str(tmp_path)

    result = subprocess.run(
        ["/bin/bash", str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
        check=False,
    )

    assert result.returncode == 1
    assert "python3 is required to run the Mem0 migration" in result.stderr


def test_curl_piped_help_works() -> None:
    result = subprocess.run(
        ["bash", "-c", f"curl -fsSL file://{SCRIPT} | bash -s -- --help"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Migrate Python OSS hosted-Qdrant memories" in result.stdout


def test_export_qdrant_memories_to_json_without_vectors_or_api_key(tmp_path: Path) -> None:
    pages = [
        {
            "points": [
                {
                    "id": "point-1",
                    "vector": [0.1, 0.2],
                    "payload": {
                        "data": "User likes dark mode",
                        "hash": "hash-1",
                        "created_at": "2026-05-01T00:00:00Z",
                        "updated_at": "2026-05-01T00:00:00Z",
                        "user_id": "alice",
                        "agent_id": "agent-1",
                        "run_id": "run-1",
                        "actor_id": "actor-1",
                        "role": "user",
                        "topic": "preferences",
                        "text_lemmatized": "user like dark mode",
                    },
                }
            ],
            "next_page_offset": 1,
        },
        {
            "points": [
                {
                    "id": "point-2",
                    "vector": [0.3, 0.4],
                    "payload": {
                        "data": "User prefers concise answers",
                        "hash": "hash-2",
                        "user_id": "alice",
                        "metadata_note": "extra",
                    },
                }
            ],
            "next_page_offset": None,
        },
    ]

    with MigrationHTTPServer(qdrant_pages=pages) as server:
        result, _mem0_dir, output_path = run_export_script(
            tmp_path,
            server,
            "--user-id",
            "alice",
            "--qdrant-page-size",
            "1",
            config={"user_id": "oss-export-user"},
        )

    assert result.returncode == 0, result.stderr
    assert "Exported 2 memories" in result.stdout

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["kind"] == "mem0_oss_qdrant_export"
    assert artifact["source"]["sdk"] == "python"
    assert artifact["source"]["vector_store"] == "qdrant"
    assert artifact["source"]["storage"] == "hosted"
    assert artifact["source"]["filters"]["user_id"] == "alice"
    assert artifact["record_count"] == 2
    assert artifact["local_anonymous_id"] == "oss-export-user"

    first = artifact["records"][0]
    assert first["id"] == "point-1"
    assert first["memory"] == "User likes dark mode"
    assert first["hash"] == "hash-1"
    assert first["user_id"] == "alice"
    assert first["agent_id"] == "agent-1"
    assert first["run_id"] == "run-1"
    assert first["actor_id"] == "actor-1"
    assert first["role"] == "user"
    assert first["metadata"] == {"topic": "preferences"}
    assert all("vector" not in record for record in artifact["records"])
    assert "qdrant-key" not in output_path.read_text(encoding="utf-8")

    scroll_requests = [request for request in server.requests if request["path"].endswith("/points/scroll")]
    assert len(scroll_requests) == 2
    assert scroll_requests[0]["body"]["with_vector"] is False
    assert scroll_requests[0]["body"]["filter"] == {"must": [{"key": "user_id", "match": {"value": "alice"}}]}
    assert scroll_requests[1]["body"]["offset"] == 1


def test_export_requires_scope_or_all(tmp_path: Path) -> None:
    with MigrationHTTPServer() as server:
        result, _mem0_dir, output_path = run_export_script(tmp_path, server)

    assert result.returncode == 1
    assert "Export requires --user-id, --agent-id, --run-id, or --all" in result.stderr
    assert not output_path.exists()
    assert not any(request["path"].endswith("/points/scroll") for request in server.requests)


def test_export_all_uses_no_qdrant_filter(tmp_path: Path) -> None:
    with MigrationHTTPServer(qdrant_pages=[{"points": [], "next_page_offset": None}]) as server:
        result, _mem0_dir, output_path = run_export_script(tmp_path, server, "--all")

    assert result.returncode == 0, result.stderr
    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact["record_count"] == 0
    assert artifact["records"] == []

    scroll_request = next(request for request in server.requests if request["path"].endswith("/points/scroll"))
    assert "filter" not in scroll_request["body"]


def test_export_invalid_qdrant_credentials_fail_clearly(tmp_path: Path) -> None:
    with MigrationHTTPServer(qdrant_api_key="correct-key") as server:
        result, _mem0_dir, output_path = run_export_script(
            tmp_path,
            server,
            "--user-id",
            "alice",
            qdrant_api_key="wrong-key",
        )

    assert result.returncode == 1
    assert "Qdrant authentication failed" in result.stderr
    assert not output_path.exists()
