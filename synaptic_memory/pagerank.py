"""PageRank and HITS network centrality for synaptic memory graphs."""

from __future__ import annotations

import math

from synaptic_memory.memory_db import MemoryMetricsDB
from synaptic_memory.synapse_db import SynapseDB


async def calculate_network_centrality(
    synapse_db: SynapseDB,
    memory_db: MemoryMetricsDB,
    damping: float = 0.85,
    iterations: int = 30,
) -> dict[str, float]:
    memory_ids = await synapse_db.get_all_memory_ids()
    if not memory_ids:
        return {}

    node_list = sorted(memory_ids)
    n = len(node_list)
    idx: dict[str, int] = {mid: i for i, mid in enumerate(node_list)}

    all_synapses = await synapse_db.get_all()

    outbound: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    inbound: list[list[tuple[int, float]]] = [[] for _ in range(n)]

    for syn in all_synapses:
        if syn.source_id not in idx or syn.target_id not in idx:
            continue
        si = idx[syn.source_id]
        ti = idx[syn.target_id]
        outbound[si].append((ti, syn.strength))
        inbound[ti].append((si, syn.strength))

    out_sum: list[float] = [sum(s for _, s in outbound[i]) for i in range(n)]

    # PageRank
    pr = [1.0 / n] * n
    teleport = (1.0 - damping) / n

    for _ in range(iterations):
        new_pr = [teleport] * n
        dangling_sum = sum(pr[i] for i in range(n) if out_sum[i] == 0.0)
        dangling_contribution = damping * dangling_sum / n

        for i in range(n):
            new_pr[i] += dangling_contribution

        for i in range(n):
            if out_sum[i] > 0.0:
                share = damping * pr[i] / out_sum[i]
                for ti, strength in outbound[i]:
                    new_pr[ti] += share * strength

        pr = new_pr

    pr_max = max(pr) or 1.0
    pr = [v / pr_max for v in pr]

    # HITS
    hub = [1.0 / n] * n
    auth = [1.0 / n] * n

    for _ in range(iterations):
        new_auth = [0.0] * n
        new_hub = [0.0] * n

        for i in range(n):
            for si, strength in inbound[i]:
                new_auth[i] += hub[si] * strength

        for i in range(n):
            for ti, strength in outbound[i]:
                new_hub[i] += auth[ti] * strength

        auth_norm = math.sqrt(sum(v * v for v in new_auth)) or 1.0
        hub_norm = math.sqrt(sum(v * v for v in new_hub)) or 1.0
        auth = [v / auth_norm for v in new_auth]
        hub = [v / hub_norm for v in new_hub]

    for i, memory_id in enumerate(node_list):
        await memory_db.get_or_create(memory_id)
        await memory_db.update_centrality(
            memory_id, page_rank=pr[i], hub_score=hub[i]
        )
        importance = pr[i] * 0.5 + auth[i] * 0.3 + hub[i] * 0.2
        importance = max(0.0, min(1.0, importance))
        await memory_db.update_importance(memory_id, importance)

    return {node_list[i]: pr[i] for i in range(n)}
