from __future__ import annotations

from app.pilot_scorecard import summarize_scorecard


def test_summarize_scorecard_returns_pass_for_strong_pilot() -> None:
    summary = summarize_scorecard(
        {
            "scenario_results": [
                {
                    "required_hit": 1,
                    "irrelevant_leak": 0,
                    "continuity_success": 1,
                    "usefulness": 5,
                    "compactness": 4,
                },
                {
                    "required_hit": 1,
                    "irrelevant_leak": 0,
                    "continuity_success": 1,
                    "usefulness": 4,
                    "compactness": 5,
                },
            ]
        }
    )

    assert summary["verdict"] == "pass"
    assert summary["metrics"]["required_hit_rate"] == 1.0


def test_summarize_scorecard_returns_attention_for_mixed_results() -> None:
    summary = summarize_scorecard(
        {
            "scenario_results": [
                {
                    "required_hit": 1,
                    "irrelevant_leak": 0,
                    "continuity_success": 1,
                    "usefulness": 4,
                    "compactness": 4,
                },
                {
                    "required_hit": 0,
                    "irrelevant_leak": 0.5,
                    "continuity_success": 0,
                    "usefulness": 3,
                    "compactness": 3,
                },
            ]
        }
    )

    assert summary["verdict"] == "attention"
    assert summary["metrics"]["overall_score"] >= 0.6


def test_summarize_scorecard_returns_fail_for_empty_input() -> None:
    summary = summarize_scorecard({"scenario_results": []})

    assert summary["verdict"] == "fail"
    assert summary["total_scenarios"] == 0
