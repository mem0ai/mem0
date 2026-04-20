from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def summarize_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    scenarios = scorecard.get("scenario_results", [])
    if not scenarios:
        return {
            "total_scenarios": 0,
            "metrics": {
                "required_hit_rate": 0.0,
                "leak_free_rate": 0.0,
                "continuity_success_rate": 0.0,
                "avg_usefulness": 0.0,
                "avg_compactness": 0.0,
                "overall_score": 0.0,
            },
            "verdict": "fail",
        }

    total = len(scenarios)
    required_hit_rate = sum(float(item.get("required_hit", 0.0)) for item in scenarios) / total
    leak_free_rate = sum(1.0 - float(item.get("irrelevant_leak", 0.0)) for item in scenarios) / total
    continuity_success_rate = sum(float(item.get("continuity_success", 0.0)) for item in scenarios) / total
    avg_usefulness = sum(float(item.get("usefulness", 0.0)) for item in scenarios) / total
    avg_compactness = sum(float(item.get("compactness", 0.0)) for item in scenarios) / total

    overall_score = (
        (required_hit_rate * 0.35)
        + (leak_free_rate * 0.25)
        + (continuity_success_rate * 0.20)
        + ((avg_usefulness / 5.0) * 0.10)
        + ((avg_compactness / 5.0) * 0.10)
    )

    if (
        required_hit_rate >= 0.8
        and leak_free_rate >= 0.8
        and continuity_success_rate >= 0.75
        and overall_score >= 0.8
    ):
        verdict = "pass"
    elif overall_score >= 0.6:
        verdict = "attention"
    else:
        verdict = "fail"

    return {
        "total_scenarios": total,
        "metrics": {
            "required_hit_rate": round(required_hit_rate, 4),
            "leak_free_rate": round(leak_free_rate, 4),
            "continuity_success_rate": round(continuity_success_rate, 4),
            "avg_usefulness": round(avg_usefulness, 4),
            "avg_compactness": round(avg_compactness, 4),
            "overall_score": round(overall_score, 4),
        },
        "verdict": verdict,
    }


def load_scorecard(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize a live pilot scorecard.")
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)

    summary = summarize_scorecard(load_scorecard(args.input))
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["verdict"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
