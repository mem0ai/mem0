"""Tests for structured logging context (task_07)."""

import logging

from app.utils.logging_context import (
    StructuredContextFilter,
    job_id_var,
    request_id_var,
)


class TestStructuredContext:
    def test_filter_injects_request_and_job_ids(self):
        filt = StructuredContextFilter()
        request_id_var.set("req-abc")
        job_id_var.set("job-xyz")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        assert filt.filter(record) is True
        assert record.request_id == "req-abc"
        assert record.job_id == "job-xyz"
        request_id_var.set("")
        job_id_var.set("")

    def test_filter_defaults_when_unset(self):
        filt = StructuredContextFilter()
        request_id_var.set("")
        job_id_var.set("")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        filt.filter(record)
        assert record.request_id == "-"
        assert record.job_id == "-"
