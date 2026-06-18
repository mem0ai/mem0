"""Governance policy resolution (Fase 3 task_02 / ADR-005)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from app.database import SessionLocal
from app.models import Config as ConfigModel
from app.models import GovernancePolicy
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session


GOVERNANCE_CONFIG_KEY = "governance"
GLOBAL_SCOPE = "__global__"

DEFAULT_POLICY: Dict[str, Any] = {
    "ttl_max_age_days": 365,
    "ttl_idle_days": 90,
    "quarantine_window_days": 30,
    "consolidation_enabled": False,
    "similarity_threshold": 0.92,
    "contradiction_tiebreak": "recency",
    "protected_categories": ["decision", "security"],
    # Teto de memórias por project (task_05 / ADR-005). ``None`` = sem teto.
    # ``max_memories_action``: "alert" (somente métrica) | "enforce" (quarentena
    # até o teto). ``cold_tier_idle_days``: inatividade que qualifica um project
    # para arquivamento em cold tier (task_07).
    "max_memories": None,
    "max_memories_action": "alert",
    "cold_tier_idle_days": 180,
    "schedules": {
        "dedup": "daily",
        "ttl_prune": "daily",
        "consolidate": "weekly",
        "purge": "daily",
        "quality_eval": "weekly",
    },
    "off_peak_hours_utc": [2, 3, 4, 5],
    "batch_limit": 500,
}


class GovernancePolicySchema(BaseModel):
    ttl_max_age_days: int = Field(default=365, ge=1)
    ttl_idle_days: int = Field(default=90, ge=1)
    quarantine_window_days: int = Field(default=30, ge=1)
    consolidation_enabled: bool = False
    similarity_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    contradiction_tiebreak: str = "recency"
    protected_categories: Tuple[str, ...] = ("decision", "security")
    max_memories: Optional[int] = Field(default=None, ge=1)
    max_memories_action: str = "alert"
    cold_tier_idle_days: int = Field(default=180, ge=1)
    schedules: Dict[str, str] = Field(default_factory=dict)
    off_peak_hours_utc: Tuple[int, ...] = (2, 3, 4, 5)
    batch_limit: int = Field(default=500, ge=1)

    @field_validator("contradiction_tiebreak")
    @classmethod
    def validate_tiebreak(cls, value: str) -> str:
        if value not in {"recency", "confidence"}:
            raise ValueError("contradiction_tiebreak must be 'recency' or 'confidence'")
        return value

    @field_validator("max_memories_action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        if value not in {"alert", "enforce"}:
            raise ValueError("max_memories_action must be 'alert' or 'enforce'")
        return value


@dataclass(frozen=True)
class EffectivePolicy:
    ttl_max_age_days: int
    ttl_idle_days: int
    quarantine_window_days: int
    consolidation_enabled: bool
    similarity_threshold: float
    contradiction_tiebreak: str
    protected_categories: Tuple[str, ...] = field(default_factory=tuple)
    max_memories: Optional[int] = None
    max_memories_action: str = "alert"
    cold_tier_idle_days: int = 180
    schedules: Dict[str, str] = field(default_factory=dict)
    off_peak_hours_utc: Tuple[int, ...] = (2, 3, 4, 5)
    batch_limit: int = 500


def validate_policy_document(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a governance policy document."""
    merged = {**DEFAULT_POLICY, **(data or {})}
    model = GovernancePolicySchema.model_validate(merged)
    return model.model_dump()


def _to_effective(data: Dict[str, Any]) -> EffectivePolicy:
    validated = validate_policy_document(data)
    return EffectivePolicy(
        ttl_max_age_days=validated["ttl_max_age_days"],
        ttl_idle_days=validated["ttl_idle_days"],
        quarantine_window_days=validated["quarantine_window_days"],
        consolidation_enabled=validated["consolidation_enabled"],
        similarity_threshold=validated["similarity_threshold"],
        contradiction_tiebreak=validated["contradiction_tiebreak"],
        protected_categories=tuple(validated["protected_categories"]),
        max_memories=validated["max_memories"],
        max_memories_action=validated["max_memories_action"],
        cold_tier_idle_days=validated["cold_tier_idle_days"],
        schedules=dict(validated.get("schedules") or DEFAULT_POLICY["schedules"]),
        off_peak_hours_utc=tuple(
            validated.get("off_peak_hours_utc") or DEFAULT_POLICY["off_peak_hours_utc"]
        ),
        batch_limit=validated["batch_limit"],
    )


def get_global_policy(db: Session) -> Dict[str, Any]:
    row = db.query(ConfigModel).filter(ConfigModel.key == GOVERNANCE_CONFIG_KEY).first()
    if row is None or not row.value:
        return dict(DEFAULT_POLICY)
    return validate_policy_document(row.value)


def save_global_policy(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    validated = validate_policy_document(data)
    row = db.query(ConfigModel).filter(ConfigModel.key == GOVERNANCE_CONFIG_KEY).first()
    if row is None:
        row = ConfigModel(key=GOVERNANCE_CONFIG_KEY, value=validated)
        db.add(row)
    else:
        row.value = validated
    db.commit()
    db.refresh(row)
    return row.value


def get_project_override(db: Session, project: str) -> Optional[Dict[str, Any]]:
    row = (
        db.query(GovernancePolicy)
        .filter(GovernancePolicy.project_name == project)
        .first()
    )
    if row is None:
        return None
    return dict(row.overrides or {})


def save_project_override(db: Session, project: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
    validate_policy_document({**DEFAULT_POLICY, **overrides})
    row = (
        db.query(GovernancePolicy)
        .filter(GovernancePolicy.project_name == project)
        .first()
    )
    if row is None:
        row = GovernancePolicy(project_name=project, overrides=overrides)
        db.add(row)
    else:
        row.overrides = overrides
    db.commit()
    db.refresh(row)
    return dict(row.overrides)


def merge_policy(global_doc: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = validate_policy_document(global_doc)
    if not override:
        return base
    merged = {**base, **override}
    if "schedules" in override:
        merged["schedules"] = {**base.get("schedules", {}), **override.get("schedules", {})}
    if "protected_categories" in override:
        merged["protected_categories"] = override["protected_categories"]
    return validate_policy_document(merged)


def resolve_policy(project: str, *, session_factory=SessionLocal) -> EffectivePolicy:
    """Merge global Config governance document with a sparse project override."""
    db = session_factory()
    try:
        global_doc = get_global_policy(db)
        override = get_project_override(db, project) if project else None
        return _to_effective(merge_policy(global_doc, override))
    finally:
        db.close()


def list_policies(*, session_factory=SessionLocal) -> Dict[str, Any]:
    db = session_factory()
    try:
        global_doc = get_global_policy(db)
        overrides = {
            row.project_name: dict(row.overrides or {})
            for row in db.query(GovernancePolicy).all()
        }
        return {"global": global_doc, "projects": overrides}
    finally:
        db.close()
