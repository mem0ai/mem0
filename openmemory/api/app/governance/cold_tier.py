"""Cold tier governance job (task_07 / ADR-003, ADR-005).

Arquiva projects inativos: quando um project não tem atividade há mais de
``cold_tier_idle_days``, exporta suas memórias ativas para o object store (cold
tier) e remove o acervo quente (Qdrant + estado SQL ``archived``), de forma
reversível por re-importação do objeto exportado.

Como a coleção Qdrant é compartilhada entre projects (D1 ainda não implementado),
o "snapshot do escopo" é um **export lógico** dos pontos do project (filtrados por
``metadata.project``), não um snapshot nativo de coleção. A ordem é
export→remoção: se o export falhar, nada é removido.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Callable, List, Optional

from app.database import SessionLocal
from app.models import Memory, MemoryState, Project
from app.utils.governance_policy import resolve_policy
from app.utils.metrics import GOVERNANCE_COLD_TIER_ARCHIVED_TOTAL
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

COLD_TIER_BUCKET = os.getenv("S3_BUCKET", "mem0-backups")


def _default_archive_writer(key: str, data: bytes) -> None:
    """Grava o objeto de arquivamento no bucket S3-compatível."""
    from app.utils.backup import make_s3_client

    make_s3_client().put_object(Bucket=COLD_TIER_BUCKET, Key=key, Body=data)


def run_cold_tier_job(
    *,
    project: Optional[str],
    job_id: str,
    limit: int = 500,
    session_factory=SessionLocal,
    vector_store_provider: Optional[Callable] = None,
    archive_writer: Callable[[str, bytes], None] = _default_archive_writer,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """Arquiva o project se inativo. Retorna o nº de memórias arquivadas."""
    if not project:
        return 0

    policy = resolve_policy(project, session_factory=session_factory)
    now = clock()
    cutoff = now - timedelta(days=policy.cold_tier_idle_days)

    db: Session = session_factory()
    try:
        row = db.query(Project).filter(Project.name == project).first()
        # Sem atividade registrada ou ainda dentro da janela => não arquiva.
        if row is None or row.last_activity_at is None:
            return 0
        last = row.last_activity_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        if last > cutoff:
            return 0

        rows: List[Memory] = [
            m
            for m in db.query(Memory).filter(Memory.state == MemoryState.active).all()
            if (m.metadata_ or {}).get("project") == project
        ][: min(limit, policy.batch_limit)]
        if not rows:
            return 0

        # 1) Export lógico ANTES de remover (reversibilidade).
        export = [
            {"id": str(m.id), "content": m.content, "metadata": m.metadata_ or {}}
            for m in rows
        ]
        key = f"cold/{project}/{now.strftime('%Y%m%dT%H%M%S')}.json"
        archive_writer(key, json.dumps(export).encode())

        # 2) Remoção do acervo quente (Qdrant + estado SQL).
        vs = _vector_store(vector_store_provider)
        archived = 0
        for m in rows:
            if vs is not None:
                try:
                    vs.delete(str(m.id))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("qdrant delete failed for %s: %s", m.id, exc)
            m.state = MemoryState.archived
            archived += 1
        db.commit()
        GOVERNANCE_COLD_TIER_ARCHIVED_TOTAL.inc(archived)
        logger.info("cold-tier archived %s memories of project %s to %s", archived, project, key)
        return archived
    finally:
        db.close()


def _vector_store(provider: Optional[Callable]):
    if provider is not None:
        return provider()
    from app.utils.memory import get_memory_client_safe

    client = get_memory_client_safe()
    return None if client is None else client.vector_store
