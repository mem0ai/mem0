"""Unit tests for the dependency-free retry helper (``mem0.utils.retry``).

These tests inject ``sleep`` and ``rng`` so backoff/jitter timing is
deterministic and no real waiting happens. The callable under test is a real
flaky function (not a mock) so we exercise the actual control flow rather than
mock bookkeeping.
"""

from unittest.mock import Mock

import pytest

from mem0.exceptions import LLMError, RateLimitError
from mem0.utils.retry import retry_call


class _Transient(Exception):
    """Stand-in for a retryable provider error (429/5xx/network/timeout)."""


class _Fatal(Exception):
    """Stand-in for a non-retryable error (auth/validation)."""


def _flaky(failures, exc=_Transient, result="ok"):
    """Return a callable that raises ``exc`` the first ``failures`` calls, then returns ``result``."""

    state = {"calls": 0}

    def _call():
        state["calls"] += 1
        if state["calls"] <= failures:
            raise exc("transient failure")
        return result

    _call.state = state
    return _call


def test_returns_result_when_func_succeeds_first_try():
    sleep = Mock()
    func = _flaky(failures=0)

    result = retry_call(func, max_retries=3, retry_on=(_Transient,), sleep=sleep)

    assert result == "ok"
    assert func.state["calls"] == 1
    sleep.assert_not_called()


def test_retries_transient_error_then_succeeds():
    sleep = Mock()
    func = _flaky(failures=2)

    result = retry_call(func, max_retries=3, retry_on=(_Transient,), sleep=sleep)

    assert result == "ok"
    assert func.state["calls"] == 3  # 1 initial + 2 retries
    assert sleep.call_count == 2


def test_gives_up_after_max_retries_and_reraises():
    sleep = Mock()
    func = _flaky(failures=99)  # always fails

    with pytest.raises(_Transient):
        retry_call(func, max_retries=2, retry_on=(_Transient,), sleep=sleep)

    assert func.state["calls"] == 3  # 1 initial + 2 retries
    assert sleep.call_count == 2


def test_does_not_retry_non_retryable_error():
    sleep = Mock()
    func = _flaky(failures=99, exc=_Fatal)

    with pytest.raises(_Fatal):
        retry_call(func, max_retries=3, retry_on=(_Transient,), sleep=sleep)

    assert func.state["calls"] == 1
    sleep.assert_not_called()


def test_exponential_backoff_delays_without_jitter():
    sleep = Mock()
    func = _flaky(failures=99)

    with pytest.raises(_Transient):
        retry_call(
            func, max_retries=3, retry_on=(_Transient,), base_delay=1.0, max_delay=100.0, jitter=False, sleep=sleep
        )

    # 3 retries → delays 1, 2, 4 (base_delay * 2**i)
    assert [c.args[0] for c in sleep.call_args_list] == [1.0, 2.0, 4.0]


def test_backoff_is_capped_at_max_delay():
    sleep = Mock()
    func = _flaky(failures=99)

    with pytest.raises(_Transient):
        retry_call(
            func, max_retries=4, retry_on=(_Transient,), base_delay=10.0, max_delay=15.0, jitter=False, sleep=sleep
        )

    # 10, then capped at 15 for all subsequent retries
    assert [c.args[0] for c in sleep.call_args_list] == [10.0, 15.0, 15.0, 15.0]


def test_full_jitter_scales_backoff_by_rng():
    sleep = Mock()
    func = _flaky(failures=1)

    retry_call(func, max_retries=3, retry_on=(_Transient,), base_delay=4.0, jitter=True, sleep=sleep, rng=lambda: 0.5)

    # single retry: backoff = 4.0 * 2**0 = 4.0; full jitter → 4.0 * 0.5 = 2.0
    assert sleep.call_args_list[0].args[0] == 2.0


def test_honors_retry_after_over_backoff():
    sleep = Mock()
    func = _flaky(failures=1)

    retry_call(
        func,
        max_retries=3,
        retry_on=(_Transient,),
        base_delay=1.0,
        jitter=True,
        sleep=sleep,
        rng=lambda: 0.5,
        retry_after=lambda exc: 7.0,
    )

    # server-directed Retry-After takes precedence over computed backoff/jitter
    assert sleep.call_args_list[0].args[0] == 7.0


@pytest.mark.parametrize("bad_delay", [-5.0, float("inf"), float("-inf"), float("nan")])
def test_invalid_retry_after_is_ignored_and_falls_back_to_backoff(bad_delay):
    sleep = Mock()
    func = _flaky(failures=1)

    retry_call(
        func,
        max_retries=3,
        retry_on=(_Transient,),
        base_delay=1.0,
        jitter=False,
        sleep=sleep,
        retry_after=lambda exc: bad_delay,
    )

    # invalid server delays (negative / non-finite) are ignored so time.sleep never
    # sees a bad value; the computed backoff is used instead.
    assert sleep.call_args_list[0].args[0] == 1.0


def test_retry_after_is_capped_at_max_delay():
    sleep = Mock()
    func = _flaky(failures=1)

    retry_call(
        func,
        max_retries=3,
        retry_on=(_Transient,),
        base_delay=1.0,
        max_delay=20.0,
        jitter=False,
        sleep=sleep,
        retry_after=lambda exc: 3600.0,
    )

    # an oversized server-directed delay is capped to max_delay to avoid unbounded sleeps
    assert sleep.call_args_list[0].args[0] == 20.0


def test_translates_final_error_via_on_giveup():
    sleep = Mock()
    func = _flaky(failures=99)

    def translate(exc):
        return RateLimitError(message=str(exc), error_code="TEST_429", debug_info={"orig": type(exc).__name__})

    with pytest.raises(RateLimitError):
        retry_call(func, max_retries=1, retry_on=(_Transient,), sleep=sleep, on_giveup=translate)

    assert func.state["calls"] == 2  # 1 initial + 1 retry


def test_on_giveup_not_called_on_success():
    sleep = Mock()
    func = _flaky(failures=1)
    translate = Mock(side_effect=lambda exc: LLMError(message="unexpected"))

    result = retry_call(func, max_retries=3, retry_on=(_Transient,), sleep=sleep, on_giveup=translate)

    assert result == "ok"
    translate.assert_not_called()


def test_no_overflow_with_very_large_max_retries():
    # base_delay * 2**attempt overflows float around attempt ~1024; the exponent
    # must be capped so a large max_retries surfaces the real provider error, not
    # OverflowError. sleep is a no-op Mock so this stays fast.
    sleep = Mock()
    func = _flaky(failures=10**9)  # always fails

    with pytest.raises(_Transient):
        retry_call(
            func, max_retries=1100, retry_on=(_Transient,), base_delay=1.0, max_delay=20.0, jitter=False, sleep=sleep
        )

    assert sleep.call_count == 1100
    assert all(call.args[0] <= 20.0 for call in sleep.call_args_list)


@pytest.mark.parametrize("bad", [float("inf"), float("nan"), -1, "3"])
def test_invalid_max_retries_raises(bad):
    # A non-finite / negative / non-numeric max_retries makes `attempt >= max_retries`
    # unreliable (inf → unbounded retry loop / hang); reject it up front.
    with pytest.raises(ValueError):
        retry_call(lambda: "unused", max_retries=bad, retry_on=(_Transient,), sleep=Mock())


def test_negative_delay_config_is_clamped_to_zero():
    # Negative base_delay/max_delay must never reach time.sleep() as a negative value
    # (which would raise and mask the provider error); the wait is floored at 0.
    sleep = Mock()
    func = _flaky(failures=2)

    retry_call(func, max_retries=3, retry_on=(_Transient,), base_delay=-5.0, max_delay=-1.0, jitter=False, sleep=sleep)

    assert all(call.args[0] >= 0.0 for call in sleep.call_args_list)
