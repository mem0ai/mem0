import asyncio
import logging
import os
import sys
import warnings

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s", force=True)

for logger_name in (
    "asyncio",
    "httpcore",
    "httpx",
    "mcp",
    "mem0",
    "openmemory",
    "qdrant_client",
    "spacy",
    "uvicorn.access",
):
    logging.getLogger(logger_name).setLevel(logging.WARNING)

for noisy_logger in (
    "mem0.memory.spacy_models",
    "mem0.utils.spacy_models",
):
    logging.getLogger(noisy_logger).setLevel(logging.ERROR)

import uvicorn


def selector_loop_factory():
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
    else:
        loop = asyncio.new_event_loop()

    def ignore_client_disconnects(loop, context):
        if isinstance(context.get("exception"), ConnectionResetError):
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(ignore_client_disconnects)
    return loop


def main():
    host = os.getenv("OPENMEMORY_API_HOST", "127.0.0.1")
    port = int(os.getenv("OPENMEMORY_API_PORT", "8765"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        access_log=False,
        log_level="warning",
        loop="run_openmemory:selector_loop_factory",
    )


if __name__ == "__main__":
    main()
