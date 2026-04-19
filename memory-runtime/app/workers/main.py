from __future__ import annotations

import argparse
import time

from app.config import get_settings
from app.database import init_database
from app.workers.runner import WorkerRunner


def run_once() -> int:
    settings = get_settings()
    if settings.auto_create_tables:
        init_database()
    return WorkerRunner.run_pending_jobs()


def run_forever(*, poll_seconds: float | None = None, max_cycles: int | None = None) -> int:
    settings = get_settings()
    interval = poll_seconds if poll_seconds is not None else settings.worker_poll_seconds
    if settings.auto_create_tables:
        init_database()

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
