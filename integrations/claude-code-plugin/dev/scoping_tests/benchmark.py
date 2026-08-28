#!/usr/bin/env python3
"""Retrieval benchmark for the scope hierarchy: fresh namespaces, scenarios scored out of 100, run with MEM0_API_KEY set."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "tests" / "integration"))

from test_live_scoping import Namespace, _bash, _text  # noqa: E402
import memory_core  # noqa: E402

TOP_K = 5


def seed(ns: Namespace) -> None:
    root, billing, web = ns.root, ns.root / "services" / "billing", ns.root / "apps" / "web"
    ns.session(
        "alice", root, "root-alice",
        "Remember I prefer uv over pip and I want commit messages in conventional commits style. Document that invoices are rounded half-up in api/invoices.py, that CI runs `make ci` on GitHub Actions, and that the whole test suite runs with `make test` from the root.",
        [{"tool": "Edit", "path": "README.md"}, _bash("make test", False, "212 passed")],
        "README documents half-up invoice rounding in api/invoices.py, that CI runs `make ci` on GitHub Actions, and that `make test` at the root runs the whole suite. Noted your preferences: uv over pip, conventional commit messages.",
    )
    ns.session(
        "bob", billing, "billing-bob",
        "The billing worker retries Stripe webhooks five times with exponential backoff. Run the billing tests.",
        [_bash("npm test", True, "npm ERR! missing script: test"), _bash("make billing-test", False, "34 passed")],
        "Documented: Stripe webhooks are retried five times with exponential backoff. `npm test` does not exist here; `make billing-test` runs the billing suite.",
    )
    ns.session(
        "carol", billing, "billing-carol",
        "Billing stores ledger rows in the Postgres schema `ledger` with bigint ids.",
        [{"tool": "Edit", "path": "services/billing/docs/schema.md"}],
        "Documented that billing keeps ledger rows in the Postgres `ledger` schema with bigint ids.",
    )
    ns.session(
        "bob", web, "web-bob",
        "The web app is built with Vite, starts with pnpm --filter web dev, styles come from Tailwind with design tokens in tokens.css, and its tests run with pnpm --filter web test.",
        [_bash("pnpm --filter web dev", False, "VITE ready in 300ms"), _bash("pnpm --filter web test", False, "18 passed")],
        "Confirmed: Vite app started with `pnpm --filter web dev`; styling is Tailwind with design tokens in tokens.css; `pnpm --filter web test` runs the web tests.",
    )
    ns.session(
        "carol", ns.notes_a, "notes-carol",
        "Private notes folder. My journal password hint lives in hints.txt.",
        [{"tool": "Edit", "path": "hints.txt"}],
        "Added the journal password hint to hints.txt.",
    )


def score(ns: Namespace) -> dict:
    billing, web = ns.root / "services" / "billing", ns.root / "apps" / "web"
    billing_app = memory_core.directory_app_id(memory_core.resolve_repo(str(billing)))
    web_app = memory_core.directory_app_id(memory_core.resolve_repo(str(web)))

    def hit(user, cwd, query, keyword, **kwargs):
        found = ns.search(user, cwd, query, top_k=TOP_K, tries=3, **kwargs)
        return keyword in _text(found), found

    personal = [
        hit("alice", ns.root, "which package manager do I prefer", "uv", scope="mine"),
        hit("alice", ns.root, "how do I like commit messages written", "conventional", scope="mine"),
        hit("alice", billing, "my package manager preference", "uv", scope="repo"),
    ]
    project = [
        hit("erin", ns.root, "how are invoices rounded", "half"),
        hit("erin", ns.root, "what does CI run", "make ci"),
        hit("erin", ns.root, "how many times are Stripe webhooks retried", "stripe"),
        hit("erin", ns.root, "how do I start the web app", "vite"),
        hit("erin", ns.root, "where are the design tokens", "tokens"),
        hit("erin", ns.root, "what id type does the ledger schema use", "bigint"),
    ]
    directory_queries = [
        (billing, "how many times are Stripe webhooks retried", "stripe", billing_app),
        (billing, "how do I run the tests here", "billing-test", billing_app),
        (billing, "what id type does the ledger schema use", "bigint", billing_app),
        (web, "how do I run the tests here", "filter web test", web_app),
        (web, "what is the test command for this package", "filter web test", web_app),
        (billing, "what is the test command for this package", "billing-test", billing_app),
        (web, "how do I start the dev server", "vite", web_app),
        (web, "where are the design tokens", "tokens", web_app),
    ]
    directory = {"dir": [], "repo": []}
    noise = {"dir": [0, 0], "repo": [0, 0]}
    for cwd, query, keyword, app in directory_queries:
        for scope in ("dir", "repo"):
            ok, found = hit("erin", cwd, query, keyword, scope=scope)
            directory[scope].append(ok)
            shared = [m for m in found if m.get("agent_id")]
            noise[scope][0] += sum(1 for m in shared if m.get("app_id") != app)
            noise[scope][1] += len(shared)
    leaks = [
        not any(m.get("user_id") == ns.users["alice"] for m in ns.search("bob", ns.root, "package manager preference uv pip", top_k=TOP_K, tries=1)),
        "hint" not in _text(ns.search("dave", ns.notes_b, "where is the journal password hint", top_k=TOP_K, tries=1)),
        all(m.get("user_id") is None for m in ns.search("erin", ns.root, "invoices stripe vite ledger", top_k=TOP_K, tries=1)),
    ]

    def pct(results):
        return round(100 * sum(1 for r in results if (r[0] if isinstance(r, tuple) else r)) / len(results))

    return {
        "namespace": ns.tag,
        "personal": pct(personal),
        "project": pct(project),
        "directory_dir_scope": pct(directory["dir"]),
        "directory_repo_scope": pct(directory["repo"]),
        "directory_noise_dir_scope": noise["dir"],
        "directory_noise_repo_scope": noise["repo"],
        "isolation": pct(leaks),
    }


def worker(index: int, out: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=f"mem0-bench-{index}-") as tmp:
        ns = Namespace(Path(tmp))
        try:
            seed(ns)
            out.write_text(json.dumps(score(ns)))
        finally:
            ns.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespaces", type=int, default=3)
    parser.add_argument("--worker", type=int)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not os.environ.get("MEM0_API_KEY"):
        raise SystemExit("MEM0_API_KEY is required")
    if args.worker is not None:
        worker(args.worker, args.out)
        return 0
    with tempfile.TemporaryDirectory(prefix="mem0-bench-") as tmp:
        outs = [Path(tmp) / f"{i}.json" for i in range(args.namespaces)]
        procs = [
            subprocess.Popen([sys.executable, __file__, "--worker", str(i), "--out", str(out)])
            for i, out in enumerate(outs)
        ]
        failed = [p.wait() for p in procs]
        results = [json.loads(out.read_text()) for out in outs if out.exists()]
    print("| Namespace | Personal | Project (repo) | Directory: dir scope | Directory: repo scope | Off-directory noise dir / repo | Isolation |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        nd, nr = r["directory_noise_dir_scope"], r["directory_noise_repo_scope"]
        print(f"| {r['namespace']} | {r['personal']} | {r['project']} | {r['directory_dir_scope']} | {r['directory_repo_scope']} | {nd[0]}/{nd[1]} vs {nr[0]}/{nr[1]} | {r['isolation']} |")
    if results:
        keys = ("personal", "project", "directory_dir_scope", "directory_repo_scope", "isolation")
        mean = {k: round(sum(r[k] for r in results) / len(results)) for k in keys}
        print(f"| **mean** | {mean['personal']} | {mean['project']} | {mean['directory_dir_scope']} | {mean['directory_repo_scope']} | | {mean['isolation']} |")
    print(json.dumps(results, indent=2))
    return int(any(failed) or len(results) != args.namespaces)


if __name__ == "__main__":
    raise SystemExit(main())
