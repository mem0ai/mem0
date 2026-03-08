#!/usr/bin/env python3
"""Mem0 Platform management CLI for Claude Code projects.

Centralized command-line interface for configuring, managing, and
querying mem0 memories across any Claude Code project.

Commands:
  configure                      - Apply project settings
  verify                         - Verify project configuration
  seed <config_module>           - Seed foundational memories from a project config
  stats                          - Show memory counts by category and source
  search <query>                 - Search memories with advanced retrieval
  graph [query]                  - Query entity-relationship graph
  feedback <id> <rating> [reason] - Rate memory quality
  export                         - Export all project memories as JSON
  expire <id> [days]             - Set expiration on a memory
  webhooks [list|create|delete]  - Manage webhook notifications
  history <id>                   - Show edit history for a memory
  summary                        - Get AI-generated memory summary
  cleanup [--dry-run]            - Find and remove duplicate/low-quality memories
  batch-expire <days> [source]   - Bulk-expire memories by source
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mem0_claude.client import get_client, load_env
from mem0_claude.types import ProjectConfig


def _require_client():
    """Get client or exit with error."""
    client = get_client()
    if not client:
        print("ERROR: MEM0_API_KEY not set in .env or environment")
        sys.exit(1)
    return client


def _load_project_config(module_path=None):
    """Load a ProjectConfig from a module path, or return defaults."""
    if module_path:
        import importlib.util

        spec = importlib.util.spec_from_file_location("project_config", module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "CONFIG"):
            return mod.CONFIG
        if hasattr(mod, "config"):
            return mod.config
        print(f"WARNING: {module_path} has no CONFIG or config. Using defaults.")
    return ProjectConfig(user_id="default", app_id="default")


def configure(config: ProjectConfig):
    """Apply full project settings: instructions, categories, graph, retrieval criteria."""
    client = _require_client()

    print("Configuring project settings...")

    if config.custom_instructions:
        client.project.update(custom_instructions=config.custom_instructions)
        print("  [OK] Custom instructions set")

    if config.custom_categories:
        client.project.update(custom_categories=config.custom_categories)
        print(f"  [OK] Custom categories set ({len(config.custom_categories)} categories)")

    client.project.update(enable_graph=True)
    print("  [OK] Graph memory enabled")

    # Retrieval criteria — weighted scoring
    retrieval_criteria = [
        {
            "name": "architectural_impact",
            "description": "How broadly does this affect system design",
            "weight": 3,
        },
        {
            "name": "implementation_confidence",
            "description": "How well-verified is this information",
            "weight": 3,
        },
        {
            "name": "recency_relevance",
            "description": "How relevant to current development phase",
            "weight": 2,
        },
        {
            "name": "cross_module_scope",
            "description": "Does this span multiple modules or system-wide",
            "weight": 2,
        },
    ]
    client.project.update(retrieval_criteria=retrieval_criteria)
    print("  [OK] Retrieval criteria set (4 weighted dimensions)")

    print("\nDone. Use 'verify' to confirm all settings.")


def verify(config: ProjectConfig):
    """Verify project configuration matches expected state."""
    client = _require_client()
    info = client.project.get()
    print("=== Project Configuration ===\n")

    checks = {
        "enable_graph": (info.get("enable_graph"), True),
        "custom_instructions": (bool(info.get("custom_instructions")), True),
        "custom_categories": (
            len(info.get("custom_categories") or []),
            len(config.custom_categories) if config.custom_categories else 0,
        ),
    }

    all_pass = True
    for key, (actual, expected) in checks.items():
        status = "PASS" if actual == expected else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {key}: {actual} (expected: {expected})")

    criteria_count = len(info.get("retrieval_criterias") or [])
    if criteria_count == 4:
        print(f"  [PASS] retrieval_criterias: {criteria_count} (expected: 4)")
    elif criteria_count == 0:
        print(
            f"  [WARN] retrieval_criterias: {criteria_count} (expected: 4 — platform GET may not expose)"
        )
    else:
        print(f"  [FAIL] retrieval_criterias: {criteria_count} (expected: 4)")
        all_pass = False

    instructions = info.get("custom_instructions", "")
    if instructions:
        has_extract = "Extract and retain" in instructions
        has_exclude = "Exclude:" in instructions
        if has_extract and has_exclude:
            print("  [PASS] custom_instructions content: contains expected sections")
        else:
            print("  [WARN] custom_instructions content: may be outdated")

    cats = info.get("custom_categories") or []
    if cats:
        print(f"\n  Categories ({len(cats)}):")
        for cat in cats:
            for k, v in cat.items():
                print(f"    - {k}: {v}")

    print(f"\n{'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    return all_pass


def stats(config: ProjectConfig):
    """Show memory counts for the project."""
    client = _require_client()

    filters = {"AND": [{"user_id": config.user_id}, {"app_id": config.app_id}]}
    memories = client.get_all(filters=filters, output_format="v1.1")

    if isinstance(memories, dict):
        items = memories.get("results", memories.get("memories", []))
    elif isinstance(memories, list):
        items = memories
    else:
        items = []

    print(f"=== Memory Stats ===\n")
    print(f"Total memories: {len(items)}")

    # Count by category
    cat_counts = {}
    for mem in items:
        cats = mem.get("categories", [])
        if isinstance(cats, list):
            for c in cats:
                cat_counts[c] = cat_counts.get(c, 0) + 1
        elif cats:
            cat_counts[str(cats)] = cat_counts.get(str(cats), 0) + 1

    if cat_counts:
        print("\nBy category:")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

    # Count by metadata.source
    source_counts = {}
    for mem in items:
        meta = mem.get("metadata") or {}
        source = meta.get("source", "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1

    if source_counts:
        print("\nBy source:")
        for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
            print(f"  {src}: {count}")

    # Count by agent_id
    agent_counts = {}
    for mem in items:
        agent = mem.get("agent_id", "unknown")
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

    if agent_counts:
        print("\nBy agent:")
        for agent, count in sorted(agent_counts.items(), key=lambda x: -x[1]):
            print(f"  {agent}: {count}")

    # Count expired vs active
    now = datetime.now().strftime("%Y-%m-%d")
    expired = sum(
        1
        for mem in items
        if mem.get("expiration_date") and mem["expiration_date"] < now
    )
    expiring = sum(1 for mem in items if mem.get("expiration_date"))
    print(f"\nExpiration: {expiring} with expiry set, {expired} already expired")


def search(config: ProjectConfig, query_text: str):
    """Search memories with full advanced retrieval."""
    client = _require_client()
    results = client.search(
        query_text,
        keyword_search=True,
        rerank=True,
        filter_memories=True,
        top_k=10,
        enable_graph=True,
        filters={"AND": [{"user_id": config.user_id}, {"app_id": config.app_id}]},
    )

    if isinstance(results, dict):
        items = results.get("results", results.get("memories", []))
        relations = results.get("relations", [])
    elif isinstance(results, list):
        items = results
        relations = []
    else:
        items = []
        relations = []

    print(f"=== Search: '{query_text}' ({len(items)} results) ===\n")
    for i, mem in enumerate(items):
        score = mem.get("score", "?")
        memory = mem.get("memory", "?")
        cats = mem.get("categories", [])
        mem_id = mem.get("id", "?")
        print(f"  [{i + 1}] (score={score}) {memory}")
        if cats:
            print(f"      categories: {cats}")
        print(f"      id: {mem_id}")
        print()

    if relations:
        print(f"  Graph Relations ({len(relations)}):")
        for rel in relations:
            source = rel.get("source", "?")
            relationship = rel.get("relationship", "?")
            target = rel.get("target", "?")
            score = rel.get("score", "?")
            print(f"    {source} --[{relationship}]--> {target} (score={score})")
        print()


def graph(config: ProjectConfig, query_text: str = None):
    """Query entity-relationship graph."""
    client = _require_client()
    query = query_text or "project architecture"

    results = client.search(
        query,
        user_id=config.user_id,
        enable_graph=True,
        top_k=10,
        filters={"AND": [{"user_id": config.user_id}, {"app_id": config.app_id}]},
    )

    if isinstance(results, dict):
        relations = results.get("relations", [])
        items = results.get("results", [])
    else:
        relations = []
        items = []

    print(f"=== Graph Query: '{query}' ===\n")

    if relations:
        print(f"  Relations ({len(relations)}):")
        for rel in relations:
            source = rel.get("source", "?")
            relationship = rel.get("relationship", "?")
            target = rel.get("target", "?")
            score = rel.get("score", "?")
            print(f"    {source} --[{relationship}]--> {target} (score={score})")
    else:
        print("  No graph relations found.")

    if items:
        print(f"\n  Related Memories ({len(items)}):")
        for i, mem in enumerate(items):
            print(f"    [{i + 1}] {mem.get('memory', '?')[:100]}")
    print()


def feedback(memory_id: str, rating: str, reason: str = None):
    """Rate a memory as POSITIVE, NEGATIVE, or VERY_NEGATIVE."""
    valid_ratings = {"POSITIVE", "NEGATIVE", "VERY_NEGATIVE"}
    rating = rating.upper()
    if rating not in valid_ratings:
        print(f"ERROR: rating must be one of {valid_ratings}")
        sys.exit(1)

    client = _require_client()
    kwargs = {"memory_id": memory_id, "feedback": rating}
    if reason:
        kwargs["feedback_reason"] = reason

    client.feedback(**kwargs)
    print(f"  [OK] Feedback '{rating}' applied to memory {memory_id}")
    if reason:
        print(f"        Reason: {reason}")


def export_memories(config: ProjectConfig):
    """Export all project memories as structured JSON."""
    client = _require_client()
    filters = {"AND": [{"user_id": config.user_id}, {"app_id": config.app_id}]}
    memories = client.get_all(filters=filters, output_format="v1.1")

    out_path = f"mem0_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w") as f:
        json.dump(memories, f, indent=2)

    if isinstance(memories, dict):
        count = len(memories.get("results", []))
    elif isinstance(memories, list):
        count = len(memories)
    else:
        count = 0

    print(f"  [OK] Exported {count} memories to {out_path}")


def expire(memory_id: str, days: int = 30):
    """Set expiration date on a memory."""
    expiry = (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d")
    client = _require_client()
    client.update(memory_id, expiration_date=expiry)
    print(f"  [OK] Memory {memory_id} expires on {expiry} ({days} days)")


def history(memory_id: str):
    """Show edit history for a memory."""
    client = _require_client()
    hist = client.history(memory_id)

    if isinstance(hist, list):
        items = hist
    elif isinstance(hist, dict):
        items = hist.get("results", hist.get("history", []))
    else:
        items = []

    print(f"=== History for {memory_id} ({len(items)} events) ===\n")
    for i, entry in enumerate(items):
        event = entry.get("event", "?")
        old = entry.get("old_memory", entry.get("previous_memory", ""))
        new = entry.get("new_memory", entry.get("memory", ""))
        ts = entry.get("created_at", entry.get("timestamp", "?"))
        print(f"  [{i + 1}] {event} at {ts}")
        if old:
            print(f"      old: {old[:100]}")
        if new:
            print(f"      new: {new[:100]}")
        print()


def summary(config: ProjectConfig):
    """Get AI-generated summary of all memories."""
    client = _require_client()
    try:
        result = client.get_summary(
            user_id=config.user_id,
            app_id=config.app_id,
        )
        print("=== Memory Summary ===\n")
        if isinstance(result, str):
            print(result)
        elif isinstance(result, dict):
            print(result.get("summary", result.get("text", json.dumps(result, indent=2))))
        else:
            print(result)
    except Exception as exc:
        print(f"  ERROR: {exc}")
        print("  (get_summary may not be available on your plan)")


def cleanup(config: ProjectConfig, dry_run: bool = True):
    """Find and remove duplicate or low-quality memories."""
    client = _require_client()
    filters = {"AND": [{"user_id": config.user_id}, {"app_id": config.app_id}]}
    memories = client.get_all(filters=filters, output_format="v1.1")

    if isinstance(memories, dict):
        items = memories.get("results", memories.get("memories", []))
    elif isinstance(memories, list):
        items = memories
    else:
        items = []

    # Find exact duplicates by memory text
    seen_texts = {}
    duplicates = []
    for mem in items:
        text = mem.get("memory", "").strip().lower()
        mem_id = mem.get("id")
        if text in seen_texts:
            duplicates.append((mem_id, text[:80], seen_texts[text]))
        else:
            seen_texts[text] = mem_id

    # Find very short memories (likely low quality)
    short = [(m.get("id"), m.get("memory", "")) for m in items if len(m.get("memory", "")) < 20]

    print(f"=== Cleanup Analysis ===\n")
    print(f"Total memories: {len(items)}")
    print(f"Exact duplicates: {len(duplicates)}")
    print(f"Very short (<20 chars): {len(short)}")

    if duplicates:
        print("\nDuplicates:")
        for mem_id, text, original_id in duplicates:
            print(f"  {mem_id}: '{text}...' (duplicate of {original_id})")

    if short:
        print("\nShort memories:")
        for mem_id, text in short:
            print(f"  {mem_id}: '{text}'")

    if not dry_run and (duplicates or short):
        to_delete = [d[0] for d in duplicates] + [s[0] for s in short]
        print(f"\nDeleting {len(to_delete)} memories...")
        for mem_id in to_delete:
            try:
                client.delete(mem_id)
                print(f"  [OK] Deleted {mem_id}")
            except Exception as exc:
                print(f"  [ERR] {mem_id}: {exc}")
    elif not dry_run:
        print("\nNothing to clean up.")
    else:
        print("\n(dry run — use --execute to delete)")


def batch_expire(config: ProjectConfig, days: int = 30, source_filter: str = None):
    """Bulk-expire memories by source."""
    client = _require_client()
    filters = {"AND": [{"user_id": config.user_id}, {"app_id": config.app_id}]}
    memories = client.get_all(filters=filters, output_format="v1.1")

    if isinstance(memories, dict):
        items = memories.get("results", memories.get("memories", []))
    elif isinstance(memories, list):
        items = memories
    else:
        items = []

    expiry = (datetime.now() + timedelta(days=int(days))).strftime("%Y-%m-%d")

    # Filter by source if specified
    targets = []
    for mem in items:
        meta = mem.get("metadata") or {}
        source = meta.get("source", "")
        mem_id = mem.get("id")
        if not mem_id:
            continue
        # Skip immutable memories
        if mem.get("immutable"):
            continue
        # Skip already-expiring
        if mem.get("expiration_date"):
            continue
        if source_filter and source != source_filter:
            continue
        if meta.get("capture") == "auto":
            targets.append((mem_id, mem.get("memory", "")[:60], source))

    print(f"=== Batch Expire ===\n")
    print(f"Setting {days}-day expiry on {len(targets)} auto-captured memories")
    if source_filter:
        print(f"Source filter: {source_filter}")
    print()

    for mem_id, text, source in targets:
        try:
            client.update(mem_id, expiration_date=expiry)
            print(f"  [OK] {mem_id} ({source}): '{text}...' -> expires {expiry}")
        except Exception as exc:
            print(f"  [ERR] {mem_id}: {exc}")


def webhooks(action: str = "list", url_or_id: str = None):
    """Manage mem0 webhooks."""
    client = _require_client()

    if action == "list":
        try:
            hooks = client.get_webhooks()
            if isinstance(hooks, list):
                items = hooks
            elif isinstance(hooks, dict):
                items = hooks.get("results", hooks.get("webhooks", []))
            else:
                items = []

            print(f"=== Webhooks ({len(items)}) ===\n")
            for wh in items:
                print(f"  ID: {wh.get('id')}")
                print(f"  URL: {wh.get('url')}")
                print(f"  Events: {wh.get('events', [])}")
                print()
            if not items:
                print("  No webhooks configured.")
        except AttributeError:
            print("  SDK webhook methods not available — using REST fallback")
            _webhooks_rest(action, url_or_id)
        except Exception as exc:
            print(f"  ERROR: {exc}")

    elif action == "create":
        if not url_or_id:
            print("ERROR: webhook URL required. Usage: webhooks create <url>")
            sys.exit(1)
        try:
            result = client.create_webhook(
                url=url_or_id,
                events=["memory_add", "memory_update", "memory_delete", "memory_categorize"],
            )
            print(f"  [OK] Webhook created: {result}")
        except AttributeError:
            print("  SDK webhook methods not available — using REST fallback")
            _webhooks_rest(action, url_or_id)
        except Exception as exc:
            print(f"  ERROR: {exc}")

    elif action == "delete":
        if not url_or_id:
            print("ERROR: webhook ID required. Usage: webhooks delete <webhook_id>")
            sys.exit(1)
        try:
            client.delete_webhook(url_or_id)
            print(f"  [OK] Webhook {url_or_id} deleted")
        except AttributeError:
            _webhooks_rest(action, url_or_id)
        except Exception as exc:
            print(f"  ERROR: {exc}")

    else:
        print(f"Unknown webhook action: {action}")
        print("Usage: webhooks [list|create <url>|delete <webhook_id>]")


def _webhooks_rest(action: str, url_or_id: str = None):
    """REST API fallback for webhook management."""
    import urllib.request

    api_key = os.environ.get("MEM0_API_KEY")
    base_url = "https://api.mem0.ai/v1/webhooks/"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }

    if action == "list":
        req = urllib.request.Request(base_url, headers=headers, method="GET")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        hooks = data if isinstance(data, list) else data.get("results", [])
        print(f"=== Webhooks ({len(hooks)}) ===\n")
        for wh in hooks:
            print(f"  ID: {wh.get('id')}, URL: {wh.get('url')}, Events: {wh.get('events', [])}")
        if not hooks:
            print("  No webhooks configured.")

    elif action == "create":
        payload = json.dumps({
            "url": url_or_id,
            "events": ["memory_add", "memory_update", "memory_delete", "memory_categorize"],
        }).encode()
        req = urllib.request.Request(base_url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        print(f"  [OK] Webhook created: {data.get('id', '?')}")

    elif action == "delete":
        req = urllib.request.Request(
            f"{base_url}{url_or_id}/", headers=headers, method="DELETE"
        )
        with urllib.request.urlopen(req) as resp:
            print(f"  [OK] Webhook {url_or_id} deleted")


def usage():
    print("Usage: python cli.py [--config <path>] <command> [args]")
    print()
    print("Options:")
    print("  --config <path>      Path to project config module (with CONFIG object)")
    print("  --cwd <path>         Working directory for .env loading")
    print()
    print("Commands:")
    print("  configure                           - Apply project settings")
    print("  verify                              - Verify project configuration")
    print("  seed <config_module>                - Seed memories (requires project config with SEEDS)")
    print("  stats                               - Show memory counts")
    print("  search <query>                      - Search memories")
    print("  graph [query]                       - Query entity-relationship graph")
    print("  feedback <memory_id> <rating> [reason] - Rate a memory")
    print("  export                              - Export all memories as JSON")
    print("  expire <memory_id> [days]           - Set expiration (default: 30)")
    print("  history <memory_id>                 - Show memory edit history")
    print("  summary                             - AI-generated memory summary")
    print("  cleanup [--execute]                 - Find/remove duplicates")
    print("  batch-expire <days> [source]        - Bulk-expire auto-captured memories")
    print("  webhooks [list|create <url>|delete <id>] - Manage webhooks")
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if not args:
        usage()

    # Parse global options
    config_path = None
    cwd = None

    while args and args[0].startswith("--"):
        if args[0] == "--config" and len(args) > 1:
            config_path = args[1]
            args = args[2:]
        elif args[0] == "--cwd" and len(args) > 1:
            cwd = args[1]
            args = args[2:]
        else:
            break

    if not args:
        usage()

    load_env(cwd)
    config = _load_project_config(config_path)

    cmd = args[0]
    cmd_args = args[1:]

    if cmd == "configure":
        configure(config)
    elif cmd == "verify":
        verify(config)
    elif cmd == "seed":
        # Seed requires a config module with SEEDS list
        if not config_path:
            print("ERROR: seed requires --config <path> with a SEEDS list")
            sys.exit(1)
        import importlib.util

        spec = importlib.util.spec_from_file_location("project_config", config_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        seeds = getattr(mod, "SEEDS", None)
        if not seeds:
            print(f"ERROR: {config_path} has no SEEDS list")
            sys.exit(1)

        client = _require_client()
        print(f"Seeding {len(seeds)} foundational memories...\n")
        for i, seed_data in enumerate(seeds):
            messages = seed_data.pop("messages")
            common = {
                "user_id": config.user_id,
                "app_id": config.app_id,
                "agent_id": config.agent_id_bootstrap,
            }
            params = {**common, **seed_data}
            params["async_mode"] = False
            result = client.add(messages, **params)
            mem_text = messages[0]["content"][:80]
            print(f"  [{i + 1}/{len(seeds)}] {mem_text}...")
            if isinstance(result, dict) and "results" in result:
                for r in result["results"]:
                    print(f"         -> {r.get('event', '?')}: {r.get('memory', '')[:60]}")
        print(f"\nSeeded {len(seeds)} memories.")

    elif cmd == "stats":
        stats(config)
    elif cmd == "search":
        query = " ".join(cmd_args) if cmd_args else "architecture"
        search(config, query)
    elif cmd == "graph":
        query = " ".join(cmd_args) if cmd_args else None
        graph(config, query)
    elif cmd == "feedback":
        if len(cmd_args) < 2:
            print("Usage: feedback <memory_id> <POSITIVE|NEGATIVE|VERY_NEGATIVE> [reason]")
            sys.exit(1)
        reason = " ".join(cmd_args[2:]) if len(cmd_args) > 2 else None
        feedback(cmd_args[0], cmd_args[1], reason)
    elif cmd == "export":
        export_memories(config)
    elif cmd == "expire":
        if not cmd_args:
            print("Usage: expire <memory_id> [days]")
            sys.exit(1)
        days = int(cmd_args[1]) if len(cmd_args) > 1 else 30
        expire(cmd_args[0], days)
    elif cmd == "history":
        if not cmd_args:
            print("Usage: history <memory_id>")
            sys.exit(1)
        history(cmd_args[0])
    elif cmd == "summary":
        summary(config)
    elif cmd == "cleanup":
        dry_run = "--execute" not in cmd_args
        cleanup(config, dry_run=dry_run)
    elif cmd == "batch-expire":
        if not cmd_args:
            print("Usage: batch-expire <days> [source]")
            sys.exit(1)
        days = int(cmd_args[0])
        source_filter = cmd_args[1] if len(cmd_args) > 1 else None
        batch_expire(config, days, source_filter)
    elif cmd == "webhooks":
        action = cmd_args[0] if cmd_args else "list"
        url_or_id = cmd_args[1] if len(cmd_args) > 1 else None
        webhooks(action, url_or_id)
    else:
        print(f"Unknown command: {cmd}")
        usage()


if __name__ == "__main__":
    main()
