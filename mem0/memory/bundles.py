"""Portable memory bundles with proof and load-time verification.

Implements the export/import interchange discussed in RFC mem0ai/mem0#7376:
a bundle format for memories that carries evidence (bidirectional outcome
records) and chain-of-custody hops, plus a fail-closed load-time verification
step that reports the verification level actually reached.

Design rules (from the RFC discussion):

- Bidirectional records: every evidence entry carries an ``outcome`` in
  {success, explicit_failure, silent_timeout}. A failure record states what
  was attempted and under which conditions it failed. Absence of a record is
  never knowledge of success — a bundle that only ever records success is
  indistinguishable from one that silently dropped its failures.
- A verification level, not a boolean: ``hash_only`` proves the content has
  not changed since the digests were computed; it is never a claim that the
  content is *correct*. ``re_executed`` and ``semantically_validated`` are
  reserved levels for importers that can actually reach them — this module
  never claims a level it did not reach.
- Fail-closed verification: any missing or malformed field is a recorded
  failure. Absence of evidence is never treated as success.
- Trust is never inherited: the import path stamps the verification level
  actually reached into each memory's metadata so downstream consumers can
  gate on it rather than on convention.
"""

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

BUNDLE_FORMAT = "mem0.bundle"
BUNDLE_VERSION = "1"


class Outcome(str, Enum):
    """Outcome of the operation an evidence record describes."""

    SUCCESS = "success"
    EXPLICIT_FAILURE = "explicit_failure"
    SILENT_TIMEOUT = "silent_timeout"


class VerificationLevel(str, Enum):
    """What a verifier actually established about a bundle.

    ``hash_only`` is an integrity claim ("content unchanged"), never a
    correctness claim. ``re_executed`` compares operation outcomes, and only
    ``semantically_validated`` says anything about correctness.
    """

    UNVERIFIED = "unverified"
    HASH_ONLY = "hash_only"
    RE_EXECUTED = "re_executed"
    SEMANTICALLY_VALIDATED = "semantically_validated"


class Operation(BaseModel):
    """What was attempted, and under which environment."""

    command: str
    environment: Dict[str, str] = Field(default_factory=dict)


class Result(BaseModel):
    """What the attempted operation produced.

    ``output_digest`` is the sha256 hex digest of the operation's output.
    For failure records, ``error_class`` states the failure mode.
    """

    exit_code: Optional[int] = None
    output_digest: Optional[str] = None
    stdout_hash: Optional[str] = None
    stderr_hash: Optional[str] = None
    error_class: Optional[str] = None


class EvidenceRecord(BaseModel):
    record_id: str
    sequence: int
    outcome: Outcome
    operation: Operation
    result: Result
    timestamp: str


class BundleHop(BaseModel):
    """One transfer in the chain of custody, with the checks performed."""

    source: str
    destination: str
    at: str
    checks: List[str] = Field(default_factory=list)


class BundleRecord(BaseModel):
    """A single memory, digest-covered, with whatever evidence exists."""

    memory_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[EvidenceRecord] = Field(default_factory=list)
    digest: Optional[str] = None


class MemoryBundle(BaseModel):
    format: str = BUNDLE_FORMAT
    version: str = BUNDLE_VERSION
    source: str
    created_at: str
    records: List[BundleRecord] = Field(default_factory=list)
    hops: List[BundleHop] = Field(default_factory=list)
    digest: Optional[str] = None


class VerificationReport(BaseModel):
    """The result of load-time verification, exposed to the caller.

    ``level`` is the level actually reached, not the level intended.
    ``failures`` is machine-readable: ``"records[2].digest:mismatch"``
    rather than a prose sentence.
    """

    valid: bool
    level: VerificationLevel
    checks_performed: List[str] = Field(default_factory=list)
    failures: List[str] = Field(default_factory=list)
    record_count: int = 0


def canonical_json(payload: Any) -> str:
    """Deterministic JSON serialization; every digest is computed over this form."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_digest(payload: Any) -> str:
    """sha256 over ``canonical_json(payload)`."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_payload(record: BundleRecord) -> Dict[str, Any]:
    data = record.model_dump(mode="json")
    data.pop("digest", None)
    return data


def _bundle_payload(bundle: MemoryBundle) -> Dict[str, Any]:
    data = bundle.model_dump(mode="json")
    data.pop("digest", None)
    return data


def build_bundle(
    records: List[Union[BundleRecord, Dict[str, Any]]],
    source: str,
    destination: Optional[str] = None,
) -> MemoryBundle:
    """Assemble records into a digest-covered bundle.

    Each record gets a digest over its own content (excluding the digest
    field), and the bundle gets a digest over everything (excluding the
    bundle's own digest field). If ``destination`` is given, the export is
    recorded as a chain-of-custody hop.
    """
    now = _utc_now()
    stamped: List[BundleRecord] = []
    for item in records:
        record = item if isinstance(item, BundleRecord) else BundleRecord.model_validate(item)
        record = record.model_copy(update={"digest": compute_digest(_record_payload(record))})
        stamped.append(record)

    hops: List[BundleHop] = []
    if destination is not None:
        hops.append(
            BundleHop(
                source=source,
                destination=destination,
                at=now,
                checks=["record_digest"],
            )
        )

    bundle = MemoryBundle(source=source, created_at=now, records=stamped, hops=hops)
    bundle = bundle.model_copy(update={"digest": compute_digest(_bundle_payload(bundle))})
    return bundle


def verify_bundle(bundle: Union[MemoryBundle, Dict[str, Any]]) -> VerificationReport:
    """Fail-closed load-time verification of a bundle.

    Recomputes every record digest and the bundle digest, and checks
    required fields are present and well-formed. Any missing or malformed
    field is a recorded failure — absence of evidence is never success. A
    bundle with zero failures is ``hash_only``: integrity, not correctness.
    """
    failures: List[str] = []
    checks_performed: List[str] = []

    if isinstance(bundle, MemoryBundle):
        parsed = bundle
    elif isinstance(bundle, dict):
        try:
            parsed = MemoryBundle.model_validate(bundle)
        except Exception as exc:  # pydantic ValidationError (missing/malformed fields)
            return VerificationReport(
                valid=False,
                level=VerificationLevel.UNVERIFIED,
                checks_performed=["schema_parse"],
                failures=[f"schema_parse:{str(exc)[:300]}"],
                record_count=0,
            )
        checks_performed.append("schema_parse")
    else:
        return VerificationReport(
            valid=False,
            level=VerificationLevel.UNVERIFIED,
            checks_performed=[],
            failures=[f"unsupported_type:{type(bundle).__name__}"],
            record_count=0,
        )

    checks_performed.append("format_version")
    if parsed.format != BUNDLE_FORMAT or parsed.version != BUNDLE_VERSION:
        failures.append(f"unsupported_format:{parsed.format}/{parsed.version}")

    checks_performed.append("record_count")
    if len(parsed.records) == 0:
        failures.append("no_records")

    for idx, record in enumerate(parsed.records):
        if record.digest is None:
            failures.append(f"records[{idx}].digest:missing")
            continue
        checks_performed.append(f"records[{idx}].digest")
        if compute_digest(_record_payload(record)) != record.digest:
            failures.append(f"records[{idx}].digest:mismatch")

    if parsed.digest is None:
        failures.append("bundle.digest:missing")
    else:
        checks_performed.append("bundle.digest")
        if compute_digest(_bundle_payload(parsed)) != parsed.digest:
            failures.append("bundle.digest:mismatch")

    level = VerificationLevel.HASH_ONLY if not failures else VerificationLevel.UNVERIFIED
    return VerificationReport(
        valid=not failures,
        level=level,
        checks_performed=checks_performed,
        failures=failures,
        record_count=len(parsed.records),
    )


def export_bundle(
    memory: Any,
    *,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    source: Optional[str] = None,
    destination: Optional[str] = None,
) -> Dict[str, Any]:
    """Export a memory client's memories as a portable, digest-covered bundle.

    Implements the interchange format discussed in #7376. Every exported record
    carries its content, surviving metadata, and a per-record digest; the
    bundle carries chain-of-custody hops and a whole-bundle digest. Evidence
    is only included when the stored memories actually carry some — none is
    invented. Verification is the importer's job (see ``import_bundle``);
    this function makes no trust claims on the receiving side.

    Args:
        memory: A ``mem0.memory.main.Memory`` instance (duck-typed: only its
            public ``get_all`` surface is used, so this also works with test
            doubles — and avoids a circular import with the Memory module).
        user_id (str, optional): Scope export to this user.
        agent_id (str, optional): Scope export to this agent.
        run_id (str, optional): Scope export to this run.
        source (str, optional): Identifier of the exporting deployment.
            Defaults to "mem0".
        destination (str, optional): Identifier of the receiving deployment;
            recorded as a chain-of-custody hop when provided.

    Returns:
        dict: The JSON-serializable bundle (format "mem0.bundle").

    Raises:
        ValueError: If none of user_id, agent_id, run_id is provided.
    """
    filters: Dict[str, Any] = {}
    if user_id is not None:
        filters["user_id"] = user_id
    if agent_id is not None:
        filters["agent_id"] = agent_id
    if run_id is not None:
        filters["run_id"] = run_id
    if not filters:
        raise ValueError("export_bundle requires at least one of: user_id, agent_id, run_id")

    memories = memory.get_all(filters=filters, top_k=100_000)["results"]

    records: List[Dict[str, Any]] = []
    for item in memories:
        metadata = {key: value for key, value in item.items() if key not in ("id", "memory", "metadata")}
        if isinstance(item.get("metadata"), dict):
            metadata.update(item["metadata"])
        records.append(
            {
                "memory_id": item["id"],
                "content": item["memory"],
                "metadata": metadata,
                "evidence": [],
            }
        )

    bundle = build_bundle(records, source=source or "mem0", destination=destination)
    return bundle.model_dump(mode="json")


def import_bundle(
    memory: Any,
    bundle: Dict[str, Any],
    *,
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a bundle produced by ``export_bundle`` — fail-closed.

    Verification runs first and its report is returned to the caller so a
    consuming system can gate on it. If the bundle does not verify, **nothing
    is added** (no partial import); the report's failures say why. Trust is
    never inherited: every imported memory is stamped with the verification
    level actually reached (``hash_only`` at best) in its metadata under
    ``bundle_provenance``.

    Args:
        memory: A ``mem0.memory.main.Memory`` instance (duck-typed: only its
            public ``add`` surface is used).
        bundle (dict): The bundle to import (from ``export_bundle``).
        user_id (str, optional): Scope import to this user.
        agent_id (str, optional): Scope import to this agent.
        run_id (str, optional): Scope import to this run.

    Returns:
        dict: {"imported": <int>, "verification": <report dict>}.

    Raises:
        ValueError: If the bundle verifies but no target scope is provided.
    """
    report = verify_bundle(bundle)
    if not report.valid:
        return {"imported": 0, "verification": report.model_dump(mode="json")}

    if not (user_id or agent_id or run_id):
        raise ValueError("import_bundle requires at least one of: user_id, agent_id, run_id")

    provenance = {
        "source": bundle.get("source"),
        "verification_level": report.level.value,
        "imported_at": _utc_now(),
    }

    imported = 0
    for record in bundle["records"]:
        metadata = dict(record.get("metadata") or {})
        metadata["bundle_provenance"] = provenance
        memory.add(
            record["content"],
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            infer=False,
            metadata=metadata,
        )
        imported += 1

    return {"imported": imported, "verification": report.model_dump(mode="json")}
