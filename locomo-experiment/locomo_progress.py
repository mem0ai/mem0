import argparse
import json
import time
from locomo_providers import PROVIDERS

QUESTION_COUNT = 70
JUDGES_PER_QUESTION = 10


def duration(seconds):
    seconds = max(0, round(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def main():
    parser = argparse.ArgumentParser(description="Monitor the 70-question LOCOMO evaluation.")
    parser.add_argument("--provider", choices=tuple(PROVIDERS), default="zhizengzeng")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    parser.add_argument("--interval", type=float, default=5)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    run = PROVIDERS[args.provider].run
    state = run / "state.json"
    sample = run / "sample-70-seed-42.json"
    summary = run / "summary-70-seed-42.json"

    start = time.monotonic()
    baseline = None
    try:
        while True:
            data = json.loads(state.read_text(encoding="utf-8"))
            selected = json.loads(sample.read_text(encoding="utf-8"))["question_indices"]
            if len(selected) != QUESTION_COUNT:
                raise ValueError(f"Expected {QUESTION_COUNT} sampled questions, got {len(selected)}")
            results = [data["questions"][str(i)] for i in selected if str(i) in data["questions"]]
            answers = len(results)
            judgments = sum(min(len(item["judgments"]), JUDGES_PER_QUESTION) for item in results)
            complete = sum(len(item["judgments"]) >= JUDGES_PER_QUESTION for item in results)
            # One answer requires two searches and one completion.
            units = answers * 3 + judgments
            total = QUESTION_COUNT * (3 + JUDGES_PER_QUESTION)
            if baseline is None:
                baseline = units
            elapsed = time.monotonic() - start
            rate = (units - baseline) / elapsed if elapsed > 0 else 0
            eta = duration((total - units) / rate) if rate > 0 and units < total else "--:--:--"
            filled = min(30, int(units * 30 / total))
            bar = "#" * filled + "-" * (30 - filled)
            usage = data["usage"]
            cost = (
                usage["chat_input"] * 0.15 + usage["chat_output"] * 0.60 + usage["embedding_input"] * 0.02
            ) * 7.56 / 1_000_000
            print(
                f"\r[{bar}] {units / total:6.1%} | 完成 {complete}/70 题 | "
                f"回答 {answers}/70 | 裁判 {judgments}/700 | "
                f"本次监控 {duration(elapsed)} | 剩余约 {eta} | 估算 ¥{cost:.2f}",
                end="\n" if args.once or summary.exists() else "",
                flush=True,
            )
            if args.once or summary.exists():
                return
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n已退出进度监视；不会停止评测。")


if __name__ == "__main__":
    main()
