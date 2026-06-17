"""Standalone entrypoint for the write worker process.

Usage::

    python -m app.workers.write_worker

Runs the queue consumer as an independent process (ADR-003), sharing the same
``DATABASE_URL`` as the API. Handles SIGINT/SIGTERM for graceful shutdown.
"""

import asyncio
import logging
import signal

from app.workers.write_worker import worker_from_env

logger = logging.getLogger(__name__)


async def _run() -> None:
    worker = worker_from_env()
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _request_stop() -> None:
        logger.info("shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _request_stop())

    worker.start()
    await stop_event.wait()
    await worker.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
