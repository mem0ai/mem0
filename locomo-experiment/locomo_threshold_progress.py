import argparse
import json
import time
from locomo_providers import PROVIDERS

parser = argparse.ArgumentParser(description="Monitor the LOCOMO threshold experiment.")
parser.add_argument("--experiment", choices=("threshold05",), default="threshold05")
parser.add_argument("--provider", choices=tuple(PROVIDERS), default="zhizengzeng")
args = parser.parse_args()
RUN = PROVIDERS[args.provider].run / "threshold05-ablation"
started = time.monotonic()
baseline = None


def display_time(seconds):
    hours, seconds = divmod(round(max(seconds, 0)), 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


try:
    while True:
        state = json.loads((RUN / "state.json").read_text())
        results = list(state["questions"].values())
        completed = sum(len(item["judgments"]) == 10 for item in results)
        judged = sum(len(item["judgments"]) for item in results)
        progress = len(results) + judged
        if baseline is None:
            baseline = progress
        elapsed = time.monotonic() - started
        rate = (progress - baseline) / elapsed if elapsed else 0
        eta = display_time((770 - progress) / rate) if rate > 0 else "--:--:--"
        filled = min(30, int(progress * 30 / 770))
        total_cost = sum(
            (u["input_tokens"] * .15 + u["output_tokens"] * .60 + u["embedding_tokens"] * .02) * 7.56 / 1e6
            for u in state["usage_by_phase"].values()
        )
        print(
            f"\r[{'#' * filled}{'-' * (30 - filled)}] {progress / 770:6.1%} "
            f"| 完成 {completed}/70 题 | 裁判 {judged}/700 | 剩余约 {eta} | 估算 ¥{total_cost:.2f}",
            end="\n" if (RUN / "summary.json").exists() else "", flush=True,
        )
        if (RUN / "summary.json").exists():
            break
        time.sleep(5)
except KeyboardInterrupt:
    print("\n已退出监视，不影响评测。")
