"""ASCII visualization utilities for the synaptic memory network."""

from __future__ import annotations

from synaptic_memory.models import MemoryAugmented, Synapse

_BAR_WIDTH = 20


def _strength_bar(strength: float) -> str:
    filled = round(strength * _BAR_WIDTH)
    filled = max(0, min(_BAR_WIDTH, filled))
    return "[" + "#" * filled + "-" * (_BAR_WIDTH - filled) + "]"


def _truncate(text: str, max_len: int = 40) -> str:
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def format_network_ascii(
    memory_id: str,
    inbound: list[Synapse],
    outbound: list[Synapse],
    metrics: MemoryAugmented,
    memory_texts: dict[str, str],
) -> str:
    lines: list[str] = []
    center_text = _truncate(memory_texts.get(memory_id, memory_id), 50)

    lines.append("=" * 60)
    lines.append(f"  MEMORY: {center_text}")
    lines.append("=" * 60)

    lines.append(
        f"  PageRank:     {metrics.page_rank:.4f}  |  "
        f"Hub:     {metrics.hub_score:.4f}"
    )
    lines.append(
        f"  Importance:   {metrics.importance_score:.4f}  |  "
        f"Strength: {metrics.total_strength:.4f}"
    )
    lines.append(f"  Accesses:     {metrics.total_access_count}")
    lines.append("-" * 60)

    if inbound:
        lines.append(f"  INBOUND  ({len(inbound)})")
        for syn in sorted(inbound, key=lambda s: s.strength, reverse=True):
            src_text = _truncate(memory_texts.get(syn.source_id, syn.source_id), 28)
            bar = _strength_bar(syn.strength)
            lines.append(
                f"  {bar} {syn.strength:.3f}  [{syn.citation_type.value}]"
                f"  <-- {src_text}"
            )
    else:
        lines.append("  INBOUND  (none)")

    lines.append("-" * 60)

    if outbound:
        lines.append(f"  OUTBOUND ({len(outbound)})")
        for syn in sorted(outbound, key=lambda s: s.strength, reverse=True):
            tgt_text = _truncate(memory_texts.get(syn.target_id, syn.target_id), 28)
            bar = _strength_bar(syn.strength)
            lines.append(
                f"  {bar} {syn.strength:.3f}  [{syn.citation_type.value}]"
                f"  --> {tgt_text}"
            )
    else:
        lines.append("  OUTBOUND (none)")

    lines.append("=" * 60)
    return "\n".join(lines)


def format_strength_report(
    synapses: list[Synapse], memory_texts: dict[str, str]
) -> str:
    if not synapses:
        return "No synapses to report."

    sorted_synapses = sorted(synapses, key=lambda s: s.strength, reverse=True)

    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  TOP SYNAPSES BY STRENGTH")
    lines.append("=" * 70)
    lines.append(
        f"  {'STRENGTH':>8}  {'BAR':<22}  {'TYPE':<12}  SOURCE -> TARGET"
    )
    lines.append("-" * 70)

    for syn in sorted_synapses:
        src = _truncate(memory_texts.get(syn.source_id, syn.source_id), 18)
        tgt = _truncate(memory_texts.get(syn.target_id, syn.target_id), 18)
        bar = _strength_bar(syn.strength)
        lines.append(
            f"  {syn.strength:>8.4f}  {bar}  "
            f"{syn.citation_type.value:<12}  {src} -> {tgt}"
        )

    lines.append("=" * 70)
    lines.append(f"  Total: {len(sorted_synapses)} synapses")
    lines.append("=" * 70)
    return "\n".join(lines)


def format_metrics_summary(metrics: list[MemoryAugmented]) -> str:
    if not metrics:
        return "No memory metrics to display."

    sorted_metrics = sorted(metrics, key=lambda m: m.page_rank, reverse=True)

    id_w = 22
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("  MEMORY METRICS SUMMARY")
    lines.append("=" * 78)
    lines.append(
        f"  {'MEMORY_ID':<{id_w}}  {'PAGE_RANK':>9}  {'HUB':>7}  "
        f"{'STRENGTH':>9}  {'IMPORTANCE':>10}"
    )
    lines.append("-" * 78)

    for m in sorted_metrics:
        mid = _truncate(m.memory_id, id_w)
        lines.append(
            f"  {mid:<{id_w}}  {m.page_rank:>9.4f}  {m.hub_score:>7.4f}  "
            f"{m.total_strength:>9.4f}  {m.importance_score:>10.4f}"
        )

    lines.append("=" * 78)
    lines.append(f"  Total: {len(sorted_metrics)} memories")
    lines.append("=" * 78)
    return "\n".join(lines)
