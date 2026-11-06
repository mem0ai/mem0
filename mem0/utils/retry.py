"""Dependency-free retry helper for provider call paths.

``retry_call`` wraps a zero-argument callable with bounded exponential backoff
and full jitter. It is intentionally free of third-party dependencies (no
``tenacity``/``backoff``) so it can live in the core SDK without adding to the
dependency surface.

Design notes:
    * Only exceptions listed in ``retry_on`` are retried; anything else
      propagates immediately (so auth/validation errors are never retried).
    * A server-directed ``Retry-After`` value (via the ``retry_after`` hook)
      takes precedence over the computed backoff.
    * When all retries are exhausted, ``on_giveup`` (if provided) may translate
      the final exception — e.g. into a typed :mod:`mem0.exceptions` error.

Example:
    from mem0.exceptions import RateLimitError
    from mem0.utils.retry import retry_call

    response = retry_call(
        lambda: client.chat.completions.create(**params),
        max_retries=2,
        retry_on=(TransientProviderError,),
        on_giveup=lambda exc: RateLimitError(message=str(exc), error_code="LLM_429"),
    )
"""

import math
import random
import time
from typing import Callable, Optional, Sequence, Type, TypeVar

T = TypeVar("T")


def retry_call(
    func: Callable[[], T],
    *,
    max_retries: int = 2,
    retry_on: Sequence[Type[BaseException]] = (Exception,),
    base_delay: float = 0.5,
    max_delay: float = 20.0,
    jitter: bool = True,
    sleep: Optional[Callable[[float], None]] = None,
    rng: Optional[Callable[[], float]] = None,
    retry_after: Optional[Callable[[BaseException], Optional[float]]] = None,
    on_giveup: Optional[Callable[[BaseException], BaseException]] = None,
) -> T:
    """Call ``func`` with retries on transient failures.

    Args:
        func: Zero-argument callable to invoke.
        max_retries: Maximum number of retries after the first attempt
            (total attempts = ``max_retries + 1``).
        retry_on: Exception types that are considered transient and retried.
            Any exception not matching these propagates immediately.
        base_delay: Base delay (seconds) for exponential backoff.
        max_delay: Upper bound (seconds) on any single backoff wait.
        jitter: When True, apply full jitter (multiply backoff by a random
            factor in ``[0, 1)``) to avoid thundering-herd retries.
        sleep: Sleep function, injectable for testing.
        rng: Zero-argument random generator returning a float in ``[0, 1)``,
            injectable for testing.
        retry_after: Optional hook mapping the caught exception to a
            server-directed delay (seconds). When it returns a value, that
            delay is used instead of the computed backoff.
        on_giveup: Optional hook mapping the final exception to a replacement
            exception raised when all retries are exhausted.

    Returns:
        The return value of ``func`` on the first successful attempt.

    Raises:
        BaseException: The last exception raised by ``func`` (or the exception
            returned by ``on_giveup``) once retries are exhausted, and any
            non-retryable exception immediately.
    """
    if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
        raise ValueError(f"max_retries must be a non-negative int, got {max_retries!r}")
    retry_on = tuple(retry_on)
    _sleep = sleep if sleep is not None else time.sleep
    _rng = rng if rng is not None else random.random
    attempt = 0
    while True:
        try:
            return func()
        except retry_on as exc:
            if attempt >= max_retries:
                if on_giveup is not None:
                    raise on_giveup(exc) from exc
                raise
            _sleep(_compute_delay(exc, attempt, base_delay, max_delay, jitter, _rng, retry_after))
            attempt += 1


def _compute_delay(
    exc: BaseException,
    attempt: int,
    base_delay: float,
    max_delay: float,
    jitter: bool,
    rng: Callable[[], float],
    retry_after: Optional[Callable[[BaseException], Optional[float]]],
) -> float:
    """Compute the wait (seconds) before the next retry."""
    if retry_after is not None:
        server_delay = retry_after(exc)
        # Only trust a finite, non-negative server delay; otherwise fall back to
        # the computed backoff (a negative value would crash time.sleep and a
        # non-finite one would sleep unbounded / crash). Cap it to max_delay so a
        # large Retry-After can't drive an unbounded wait.
        if server_delay is not None and math.isfinite(server_delay) and server_delay >= 0:
            return max(0.0, min(server_delay, max_delay))
    # Cap the exponent so a very large ``attempt`` can't overflow float
    # (``2**attempt`` exceeds float max near attempt ~1024); the cap sits far
    # above any realistic ``max_delay``, so the min() still governs the result.
    backoff = min(max_delay, base_delay * (2 ** min(attempt, 32)))
    if jitter:
        backoff = backoff * rng()
    # Floor at 0 so a misconfigured negative base_delay/max_delay never reaches
    # time.sleep() as a negative value.
    return max(0.0, backoff)
