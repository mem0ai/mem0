from __future__ import annotations

import argparse
import sys
import time

from app.config import get_settings
from app.database import init_database
from app.workers.runner import WorkerRunner


def run_once() -> int:
    settings = get_settings()
    if settings.auto_create_tables:
        init_database()
    return WorkerRunner.run_pending_jobs()


def initialize_database_with_retry(*, poll_seconds: float, max_attempts: int | None = None) -> None:
    attempts = 0
    while True:
        try:
            init_database()
            return
        except Exception as exc:  # noqa: BLE001
            attempts += 1
            if max_attempts is not None and attempts >= max_attempts:
                raise
            print(
                f"memory-worker: database unavailable during startup ({exc}); retrying in {poll_seconds:.1f}s",
                file=sys.stderr,
            )
            time.sleep(poll_seconds)


def run_forever(*, poll_seconds: float | None = None, max_cycles: int | None = None) -> int:
    settings = get_settings()
    interval = poll_seconds if poll_seconds is not None else settings.worker_poll_seconds
    if settings.auto_create_tables:
        initialize_database_with_retry(poll_seconds=interval)

    total_processed = 0
    cycles = 0
    while True:
        total_processed += WorkerRunner.run_pending_jobs()
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            return total_processed
        time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Agent Memory Runtime worker.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process pending jobs once and exit.",
    )
    args = parser.parse_args(argv)

    if args.once:
        run_once()
        return 0

    run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
