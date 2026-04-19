from __future__ import annotations

from app.regression_compare import compare_reports


def test_compare_reports_detects_quality_improvement() -> None:
    before = {
        "failed": 1,
        "pass_rate": 0.9,
        "metrics": {
            "required_hit_rate": 0.92,
            "forbidden_leak_rate": 0.1,
            "mean_scenario_score": 0.91,
        },
    }
    after = {
        "failed": 0,
        "pass_rate": 1.0,
        "metrics": {
            "required_hit_rate": 0.98,
            "forbidden_leak_rate": 0.0,
            "mean_scenario_score": 0.99,
        },
    }

    report = compare_reports(before, after)

    assert report["verdict"] == "pass"
    assert report["summary"]["regressed"] == 0
    assert report["summary"]["critical_regressions"] == []


def test_compare_reports_detects_critical_regression() -> None:
    before = {
        "failed": 0,
        "pass_rate": 1.0,
        "metrics": {
            "required_hit_rate": 1.0,
            "forbidden_leak_rate": 0.0,
        },
    }
    after = {
        "failed": 1,
        "pass_rate": 0.8,
        "metrics": {
            "required_hit_rate": 0.8,
            "forbidden_leak_rate": 0.2,
        },
    }

    report = compare_reports(before, after)

    assert report["verdict"] == "fail"
    assert "failed" in report["summary"]["critical_regressions"]
    assert "pass_rate" in report["summary"]["critical_regressions"]
    assert "metrics.required_hit_rate" in report["summary"]["critical_regressions"]
    assert "metrics.forbidden_leak_rate" in report["summary"]["critical_regressions"]


def test_compare_reports_skips_unknown_metrics() -> None:
    before = {
        "metrics": {
            "custom_signal": 0.5,
            "false_accepts": 1,
        }
    }
    after = {
        "metrics": {
            "custom_signal": 0.7,
            "false_accepts": 0,
        }
    }

    report = compare_reports(before, after)
    comparisons = {item["metric"]: item for item in report["comparisons"]}

    assert comparisons["metrics.custom_signal"]["status"] == "skipped"
    assert comparisons["metrics.false_accepts"]["status"] == "improved"
    assert report["verdict"] == "pass"
