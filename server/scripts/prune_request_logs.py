"""Delete request_logs rows older than REQUEST_LOG_RETENTION_DAYS (default 30).

Run inside the `mem0` container, or wire into cron / a systemd timer on the host.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from db import SessionLocal
from models import RequestLog


def main() -> int:
    raw = os.environ.get("REQUEST_LOG_RETENTION_DAYS", "").strip() or "30"
    try:
        retention_days = int(raw)
    except ValueError:
        sys.stderr.write("REQUEST_LOG_RETENTION_DAYS must be an integer.\n")
        return 1
    if retention_days < 1:
        sys.stderr.write("REQUEST_LOG_RETENTION_DAYS must be >= 1.\n")
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    with SessionLocal() as session:
        result = session.execute(delete(RequestLog).where(RequestLog.created_at < cutoff))
        session.commit()
        sys.stdout.write(f"Deleted {result.rowcount or 0} request_logs rows older than {cutoff.isoformat()}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
