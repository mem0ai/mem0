from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


HIGHER_IS_BETTER = {
    "pass_rate",
    "metrics.required_hit_rate",
    "metrics.mean_scenario_score",
    "metrics.action_match_rate",
    "metrics.status_match_rate",
    "metrics.mean_freshness_score",
    "metrics.rejection_rate",
    "metrics.avg_selected_count",
}

LOWER_IS_BETTER = {
    "failed",
    "metrics.forbidden_leak_rate",
    "metrics.destructive_action_rate",
    "metrics.false_accepts",
    "metrics.false_rejects",
}

CRITICAL_METRICS = {
    "failed",
    "pass_rate",
    "metrics.required_hit_rate",
    "metrics.forbidden_leak_rate",
    "metrics.action_match_rate",
    "metrics.status_match_rate",
    "metrics.false_accepts",
    "metrics.false_rejects",
}


def load_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _flatten_metrics(report: dict[str, Any]) -> dict[str, float]:
    flat: dict[str, float] = {}
    for key in ("total", "passed", "failed", "pass_rate"):
        value = report.get(key)
        if isinstance(value, int | float):
            flat[key] = float(value)

    metrics = report.get("metrics", {})
    if isinstance(metrics, dict):
        for key, value in metrics.items():
            if isinstance(value, int | float):
                flat[f"metrics.{key}"] = float(value)
    return flat


def _metric_direction(metric_name: str) -> str | None:
    if metric_name in HIGHER_IS_BETTER:
        return "higher_is_better"
    if metric_name in LOWER_IS_BETTER:
        return "lower_is_better"
    return None


def compare_reports(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    before_metrics = _flatten_metrics(before)
    after_metrics = _flatten_metrics(after)
    metric_names = sorted(set(before_metrics) | set(after_metrics))

    comparisons: list[dict[str, Any]] = []
    improved = 0
    regressed = 0
    unchanged = 0
    skipped = 0
    critical_regressions: list[str] = []

    for metric_name in metric_names:
        before_value = before_metrics.get(metric_name)
        after_value = after_metrics.get(metric_name)
        direction = _metric_direction(metric_name)

        if before_value is None or after_value is None or direction is None:
            status = "skipped"
            delta = None
            skipped += 1
        else:
            delta = round(after_value - before_value, 4)
            if abs(delta) < 1e-9:
                status = "unchanged"
                unchanged += 1
            elif direction == "higher_is_better":
                status = "improved" if delta > 0 else "regressed"
            else:
                status = "improved" if delta < 0 else "regressed"

            if status == "improved":
                improved += 1
            elif status == "regressed":
                regressed += 1
                if metric_name in CRITICAL_METRICS:
                    critical_regressions.append(metric_name)
            elif status == "unchanged":
                unchanged += 1

        comparisons.append(
            {
                "metric": metric_name,
                "before": before_value,
                "after": after_value,
                "delta": delta,
                "direction": direction,
                "status": status,
            }
        )

    verdict = "pass" if not critical_regressions else "fail"
    return {
        "verdict": verdict,
        "summary": {
            "improved": improved,
            "regressed": regressed,
            "unchanged": unchanged,
            "skipped": skipped,
            "critical_regressions": critical_regressions,
        },
        "comparisons": comparisons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two evaluation reports.")
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    args = parser.parse_args(argv)

    report = compare_reports(
        load_report(args.before),
        load_report(args.after),
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
