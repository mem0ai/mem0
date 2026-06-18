"""Entrypoint da rotina de backup (task_02 / ADR-003).

Executado pelo serviço ``backup`` do compose (``python -m app.scripts.run_backup``)
ou agendado por cron externo. Faz um backup completo (Qdrant + PostgreSQL) para o
bucket S3-compatível configurado por ambiente.
"""

import logging

from app.utils.backup import BackupService


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    result = BackupService().run_backup()
    logging.getLogger(__name__).info(
        "backup ok: %s qdrant objetos, postgres=%s, %.1fs",
        len(result.qdrant_objects),
        result.postgres_object,
        result.duration_seconds,
    )


if __name__ == "__main__":
    main()
