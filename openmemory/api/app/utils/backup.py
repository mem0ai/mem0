"""Backup / restore para object store S3-compatível (task_02 / ADR-003).

Faz snapshot nativo das coleções do Qdrant e dump do PostgreSQL e envia os
artefatos para um bucket (MinIO on-prem por padrão; qualquer S3 via env). O
serviço expõe *seams* injetáveis (cliente S3, provider do Qdrant, runner do
``pg_dump``, relógio) para ser testável sem infraestrutura real.

Convenção de chave (ver TechSpec, "Modelos de Dados"):
    backups/{YYYY-MM-DD}/qdrant/{collection}.snapshot
    backups/{YYYY-MM-DD}/postgres/dump.sql.gz

Verificação ao vivo (MinIO + Qdrant + PostgreSQL) é feita pelo drill da task_03;
aqui os caminhos default usam boto3/QdrantClient/pg_dump reais, exercitados em
produção, e os testes cobrem a orquestração via mocks.
"""

from __future__ import annotations

import gzip
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable, List, Optional

from app.database import DATABASE_URL, is_postgresql
from app.utils.metrics import (
    BACKUP_DURATION_SECONDS,
    BACKUP_ERRORS_TOTAL,
    BACKUP_LAST_SUCCESS_TIMESTAMP,
)

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = os.getenv("S3_BUCKET", "mem0-backups")


def make_s3_client():
    """Cliente boto3 S3 a partir do ambiente (MinIO ou S3 externo)."""
    import boto3  # lazy import — só necessário no caminho real

    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
    )


def _default_pg_dump(db_url: str) -> bytes:
    """Roda ``pg_dump`` e retorna o dump comprimido (gzip)."""
    out = subprocess.run(
        ["pg_dump", "--dbname", db_url], check=True, capture_output=True
    ).stdout
    return gzip.compress(out)


@dataclass
class BackupResult:
    key_prefix: str
    qdrant_objects: List[str] = field(default_factory=list)
    postgres_object: Optional[str] = None
    duration_seconds: float = 0.0


class BackupService:
    """Orquestra backup/restore para um bucket S3-compatível."""

    def __init__(
        self,
        *,
        s3_client=None,
        bucket: str = DEFAULT_BUCKET,
        db_url: str = DATABASE_URL,
        qdrant_client_provider: Optional[Callable] = None,
        pg_dump_runner: Callable[[str], bytes] = _default_pg_dump,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._s3 = s3_client
        self._bucket = bucket
        self._db_url = db_url
        self._qdrant_provider = qdrant_client_provider
        self._pg_dump = pg_dump_runner
        self._clock = clock

    # -- helpers -----------------------------------------------------------
    def _s3_client(self):
        if self._s3 is None:
            self._s3 = make_s3_client()
        return self._s3

    def _qdrant(self):
        if self._qdrant_provider is not None:
            return self._qdrant_provider()
        from app.utils.memory import get_memory_client_safe

        client = get_memory_client_safe()
        return None if client is None else client.vector_store.client

    def _collections(self, qc) -> List[str]:
        cols = qc.get_collections().collections
        return [c.name for c in cols]

    # -- backup ------------------------------------------------------------
    def run_backup(self, prefix: str = "backups") -> BackupResult:
        started = time.perf_counter()
        ts = self._clock()
        date_key = ts.strftime("%Y-%m-%d")
        result = BackupResult(key_prefix=f"{prefix}/{date_key}")
        try:
            s3 = self._s3_client()
            qc = self._qdrant()
            if qc is not None:
                for name in self._collections(qc):
                    snapshot = qc.create_snapshot(collection_name=name)
                    data = qc.download_snapshot(collection_name=name, snapshot_name=_snap_name(snapshot))
                    key = f"{result.key_prefix}/qdrant/{name}.snapshot"
                    s3.put_object(Bucket=self._bucket, Key=key, Body=data)
                    result.qdrant_objects.append(key)

            if is_postgresql(self._db_url):
                dump = self._pg_dump(self._db_url)
                key = f"{result.key_prefix}/postgres/dump.sql.gz"
                s3.put_object(Bucket=self._bucket, Key=key, Body=dump)
                result.postgres_object = key

            result.duration_seconds = time.perf_counter() - started
            BACKUP_DURATION_SECONDS.set(result.duration_seconds)
            BACKUP_LAST_SUCCESS_TIMESTAMP.set(ts.timestamp())
            return result
        except Exception:
            BACKUP_ERRORS_TOTAL.inc()
            logger.exception("backup run failed")
            raise

    # -- status ------------------------------------------------------------
    def status(self, prefix: str = "backups") -> dict:
        s3 = self._s3_client()
        listing = s3.list_objects_v2(Bucket=self._bucket, Prefix=prefix + "/")
        contents = listing.get("Contents", [])
        if not contents:
            return {"last_backup": None, "objects": 0, "rpo_age_seconds": None}
        latest = max(contents, key=lambda o: o.get("LastModified"))
        last_dt = latest.get("LastModified")
        age = None
        if isinstance(last_dt, datetime):
            age = (self._clock() - last_dt).total_seconds()
        return {
            "last_backup": latest.get("Key"),
            "objects": len(contents),
            "rpo_age_seconds": age,
        }

    def exists(self, key_prefix: str) -> bool:
        """Whether any backup object lives under ``key_prefix``."""
        s3 = self._s3_client()
        listing = s3.list_objects_v2(Bucket=self._bucket, Prefix=key_prefix + "/")
        return bool(listing.get("Contents"))

    # -- restore -----------------------------------------------------------
    def restore(self, key_prefix: str) -> dict:
        """Restaura Qdrant (snapshots) e PostgreSQL (dump) a partir de um prefixo.

        Ordem: PostgreSQL primeiro (metadados/fila), depois Qdrant (vetores), de
        modo que o catálogo reflita os pontos recuperados.
        """
        s3 = self._s3_client()
        listing = s3.list_objects_v2(Bucket=self._bucket, Prefix=key_prefix + "/")
        keys = [o["Key"] for o in listing.get("Contents", [])]
        if not keys:
            raise KeyError(f"no backup objects under {key_prefix}")

        restored = {"postgres": None, "qdrant": []}
        pg_keys = [k for k in keys if "/postgres/" in k]
        if pg_keys and is_postgresql(self._db_url):
            self._restore_postgres(s3, pg_keys[0])
            restored["postgres"] = pg_keys[0]

        qc = self._qdrant()
        if qc is not None:
            for k in [k for k in keys if "/qdrant/" in k]:
                name = k.rsplit("/", 1)[-1].removesuffix(".snapshot")
                obj = s3.get_object(Bucket=self._bucket, Key=k)
                qc.recover_snapshot(collection_name=name, location=obj["Body"].read())
                restored["qdrant"].append(name)
        return restored

    def _restore_postgres(self, s3, key: str) -> None:
        obj = s3.get_object(Bucket=self._bucket, Key=key)
        sql = gzip.decompress(obj["Body"].read())
        subprocess.run(
            ["psql", "--dbname", self._db_url], input=sql, check=True
        )


def _snap_name(snapshot) -> str:
    """Extrai o nome do snapshot de uma resposta do QdrantClient."""
    return getattr(snapshot, "name", snapshot) if snapshot is not None else ""
