import logging

from fastapi import HTTPException


def upstream_error() -> HTTPException:
    """Generic 502 for provider failures; logs the active exception without leaking it to the client."""
    logging.exception("Upstream provider error")
    return HTTPException(status_code=502, detail="Upstream provider error.")
