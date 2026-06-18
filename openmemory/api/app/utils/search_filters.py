"""Search filter helpers for governance (Fase 3 task_03)."""

from __future__ import annotations

from typing import Any, Dict, Optional


def inject_active_state_filter(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ensure governance quarantined memories are excluded from search.

    Legacy points without a ``state`` payload field are treated as active by
    allowing anything that is not explicitly ``quarantined``.
    """
    state_guard = {
        "OR": [
            {"state": "active"},
            {"NOT": [{"state": "quarantined"}]},
        ]
    }
    if not filters:
        return state_guard
    return {"AND": [filters, state_guard]}
