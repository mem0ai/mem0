"""
Automatos Shared Log Relay — Lightweight Observability for All Services
=======================================================================

Self-contained logging handler that ships structured JSON logs to the
Automatos log-relay service (→ Loki → Grafana). Zero external dependencies
— uses only Python stdlib.

Drop into any service:

    from automatos_logging import setup_logging
    setup_logging(service="my-service")

    import logging
    logger = logging.getLogger(__name__)
    logger.info("It works", extra={"workspace_id": "abc"})

Env vars:
    LOG_RELAY_URL       - Default: http://log-relay.railway.internal:8080/push
    LOG_RELAY_ENABLED   - Default: true
    SERVICE_NAME        - Fallback service name
    ENVIRONMENT         - Default: from RAILWAY_ENVIRONMENT or "development"
    LOG_LEVEL           - Default: INFO
    LOG_RELAY_BATCH_SIZE    - Default: 50
    LOG_RELAY_FLUSH_INTERVAL - Default: 2.0 (seconds)
"""

import hashlib
import json
import logging
import os
import queue
import sys
import threading
import time
import traceback
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration (all from env — no config.py dependency)
# ---------------------------------------------------------------------------

LOG_RELAY_URL = os.environ.get(
    "LOG_RELAY_URL", "http://log-relay.railway.internal:8080/push"
)
LOG_RELAY_ENABLED = os.environ.get("LOG_RELAY_ENABLED", "true").lower() == "true"
SERVICE_NAME = os.environ.get("SERVICE_NAME", "unknown")
ENVIRONMENT = os.environ.get(
    "ENVIRONMENT", os.environ.get("RAILWAY_ENVIRONMENT", "development")
)
BATCH_SIZE = int(os.environ.get("LOG_RELAY_BATCH_SIZE", "50"))
FLUSH_INTERVAL = float(os.environ.get("LOG_RELAY_FLUSH_INTERVAL", "2.0"))


# ---------------------------------------------------------------------------
# Error Fingerprinting
# ---------------------------------------------------------------------------

def _error_fingerprint(exc_type: str, filename: str, func_name: str) -> str:
    """Stable fingerprint: same exception in same function = same hash."""
    raw = f"{exc_type}:{filename}:{func_name}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _stack_hash(tb_text: str) -> str:
    """Hash of normalized traceback frames for deduplication."""
    lines = []
    for line in tb_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("File "):
            parts = stripped.split(",")
            if len(parts) >= 3:
                lines.append(f"{parts[0].strip()},{parts[2].strip()}")
            else:
                lines.append(stripped)
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:12]


def _extract_error(record: logging.LogRecord) -> Optional[dict]:
    """Extract structured error info from a log record with exception."""
    if not record.exc_info or record.exc_info[0] is None:
        return None

    exc_type, exc_value, exc_tb = record.exc_info
    type_name = exc_type.__name__ if exc_type else "Unknown"
    message = str(exc_value) if exc_value else ""

    tb_text = ""
    if exc_tb:
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    filename = record.pathname or ""
    func_name = record.funcName or ""
    if exc_tb:
        tb_frame = exc_tb
        while tb_frame.tb_next:
            tb_frame = tb_frame.tb_next
        filename = tb_frame.tb_frame.f_code.co_filename
        func_name = tb_frame.tb_frame.f_code.co_name

    return {
        "type": type_name,
        "message": message[:500],
        "fingerprint": _error_fingerprint(type_name, filename, func_name),
        "stack_hash": _stack_hash(tb_text) if tb_text else "",
        "traceback": tb_text[:5000] if tb_text else "",
    }


# ---------------------------------------------------------------------------
# Extra fields we capture from log records
# ---------------------------------------------------------------------------

_KNOWN_EXTRA = frozenset({
    "request_id", "correlation_id", "workspace_id", "user_id",
    "agent_id", "workflow_id", "run_id", "tenant_id",
    "method", "path", "task_id", "trace_id", "duration_ms",
    "tokens_in", "tokens_out", "cost", "model", "job_id",
})

# Cache standard LogRecord attrs to detect custom extras
_STANDARD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
)


# ---------------------------------------------------------------------------
# Log Relay Handler
# ---------------------------------------------------------------------------

class LogRelayHandler(logging.Handler):
    """Async batched handler that ships structured logs to log-relay → Loki.

    Uses a background daemon thread with a queue — never blocks the caller.
    Gracefully degrades if log-relay is unreachable.
    """

    def __init__(
        self,
        url: str = LOG_RELAY_URL,
        service: str = SERVICE_NAME,
        environment: str = ENVIRONMENT,
        batch_size: int = BATCH_SIZE,
        flush_interval: float = FLUSH_INTERVAL,
    ):
        super().__init__()
        self.url = url
        self.service = service
        self.environment = environment
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._queue: queue.Queue = queue.Queue(maxsize=10_000)
        self._shutdown = threading.Event()
        self._thread = threading.Thread(
            target=self._flush_loop, name="log-relay-flusher", daemon=True
        )
        self._thread.start()
        self._consecutive_failures = 0

    def emit(self, record: logging.LogRecord):
        try:
            self._queue.put_nowait(self._format_entry(record))
        except queue.Full:
            pass  # Drop silently — never block the app

    def _format_entry(self, record: logging.LogRecord) -> dict:
        context = {
            "module": record.module,
            "function": record.funcName,
            "lineno": record.lineno,
            "logger": record.name,
        }

        # Capture known extra fields + any custom extras
        for key, val in record.__dict__.items():
            if key in _KNOWN_EXTRA:
                context[key] = str(val)
            elif key not in _STANDARD_ATTRS and not key.startswith("_"):
                context[key] = str(val)

        error = _extract_error(record)

        entry = {
            "service": self.service,
            "level": record.levelname.lower(),
            "message": self.format(record) if self.formatter else record.getMessage(),
            "timestamp": record.created,
            "context": context,
        }
        if error:
            entry["error"] = error

        # Metrics context
        metrics = {}
        for k in ("duration_ms", "tokens_in", "tokens_out", "cost"):
            val = getattr(record, k, None)
            if val is not None:
                metrics[k] = val
        if metrics:
            entry["metrics"] = metrics

        return entry

    def _flush_loop(self):
        while not self._shutdown.is_set():
            batch = self._drain()
            if batch:
                self._send(batch)
            self._shutdown.wait(timeout=self.flush_interval)
        # Final flush
        batch = self._drain()
        if batch:
            self._send(batch)

    def _drain(self) -> list:
        batch = []
        while len(batch) < self.batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _send(self, batch: list):
        from urllib.request import Request, urlopen
        from urllib.error import URLError

        payload = json.dumps(batch).encode("utf-8")
        req = Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=5) as resp:
                if resp.status < 400:
                    self._consecutive_failures = 0
                    return
        except (URLError, OSError, TimeoutError):
            pass

        self._consecutive_failures += 1
        if self._consecutive_failures <= 3:
            print(
                f"[log-relay] Failed to send {len(batch)} entries to {self.url} "
                f"(attempt {self._consecutive_failures})",
                file=sys.stderr,
            )

    def close(self):
        self._shutdown.set()
        self._thread.join(timeout=5)
        super().close()


# ---------------------------------------------------------------------------
# Setup Function
# ---------------------------------------------------------------------------

def setup_logging(
    service: str,
    level: Optional[int] = None,
    relay_url: Optional[str] = None,
    environment: Optional[str] = None,
    enable_relay: Optional[bool] = None,
) -> logging.Logger:
    """Configure logging with console + log-relay output.

    Args:
        service: Service name (e.g. "workspace-worker", "mem0-server")
        level: Log level (default from LOG_LEVEL env or INFO)
        relay_url: Override LOG_RELAY_URL
        environment: Override ENVIRONMENT
        enable_relay: Override LOG_RELAY_ENABLED

    Returns:
        Root logger
    """
    if level is None:
        level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Console handler (always)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setLevel(level)
        console.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        ))
        root.addHandler(console)

    # Log-relay handler (ships to Loki)
    should_enable = enable_relay if enable_relay is not None else LOG_RELAY_ENABLED
    if should_enable:
        relay = LogRelayHandler(
            url=relay_url or LOG_RELAY_URL,
            service=service,
            environment=environment or ENVIRONMENT,
        )
        relay.setLevel(level)
        root.addHandler(relay)
        # Log that we're connected (goes to console only since relay just started)
        logging.getLogger(service).info(
            "Log relay enabled → %s", relay_url or LOG_RELAY_URL
        )

    return root
