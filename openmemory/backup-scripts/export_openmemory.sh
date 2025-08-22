#!/usr/bin/env bash
set -euo pipefail

# Export OpenMemory data from a running Docker container without relying on API endpoints.
# Produces: memories.json + memories.jsonl.gz zipped as memories_export_<USER_ID>.zip
#
# Requirements:
# - docker available locally
# - The target container has Python + SQLAlchemy and access to the same DATABASE_URL it uses in prod
#
# Usage:
#   ./export_openmemory.sh --user-id <USER_ID> [--container <NAME_OR_ID>] [--app-id <UUID>] [--from-date <epoch_secs>] [--to-date <epoch_secs>]
#
# Notes:
# - USER_ID is the external user identifier (e.g., "vikramiyer"), not the internal UUID.
# - If --container is omitted, the script uses container name "openmemory-openmemory-mcp-1".
# - The script writes intermediate files to /tmp inside the container, then docker cp's them out and zips locally.

usage() {
  echo "Usage: $0 --user-id <USER_ID> [--container <NAME_OR_ID>] [--app-id <UUID>] [--from-date <epoch_secs>] [--to-date <epoch_secs>]"
  exit 1
}

USER_ID=""
CONTAINER=""
APP_ID=""
FROM_DATE=""
TO_DATE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user-id) USER_ID="${2:-}"; shift 2 ;;
    --container) CONTAINER="${2:-}"; shift 2 ;;
    --app-id) APP_ID="${2:-}"; shift 2 ;;
    --from-date) FROM_DATE="${2:-}"; shift 2 ;;
    --to-date) TO_DATE="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

if [[ -z "${USER_ID}" ]]; then
  echo "ERROR: --user-id is required"
  usage
fi

if [[ -z "${CONTAINER}" ]]; then
  CONTAINER="openmemory-openmemory-mcp-1"
fi

# Verify the container exists and is running
if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  echo "ERROR: Container '${CONTAINER}' not found/running. Pass --container <NAME_OR_ID> if different."
  exit 1
fi

# Verify python is available inside the container
if ! docker exec "${CONTAINER}" sh -lc 'command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1'; then
  echo "ERROR: Python is not available in container ${CONTAINER}"
  exit 1
fi

PY_BIN="python3"
if ! docker exec "${CONTAINER}" sh -lc 'command -v python3 >/dev/null 2>&1'; then
  PY_BIN="python"
fi

echo "Using container: ${CONTAINER}"
echo "Exporting data for user_id: ${USER_ID}"

# Run Python inside the container to generate memories.json and memories.jsonl.gz in /tmp
set +e
cat <<'PYCODE' | docker exec -i \
  -e EXPORT_USER_ID="${USER_ID}" \
  -e EXPORT_APP_ID="${APP_ID}" \
  -e EXPORT_FROM_DATE="${FROM_DATE}" \
  -e EXPORT_TO_DATE="${TO_DATE}" \
  "${CONTAINER}" "${PY_BIN}" -
import os
import sys
import json
import gzip
import uuid
import datetime
from typing import Any, Dict, List

try:
    from sqlalchemy import create_engine, text
except Exception as e:
    print(f"ERROR: SQLAlchemy not available inside the container: {e}", file=sys.stderr)
    sys.exit(3)

def _iso(dt):
    if dt is None:
        return None
    try:
        if isinstance(dt, str):
            try:
                dt_obj = datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except Exception:
                return dt
        else:
            dt_obj = dt
        if dt_obj.tzinfo is None:
            dt_obj = dt_obj.replace(tzinfo=datetime.timezone.utc)
        else:
            dt_obj = dt_obj.astimezone(datetime.timezone.utc)
        return dt_obj.isoformat()
    except Exception:
        return None

def _json_load_maybe(val):
    if isinstance(val, (dict, list)) or val is None:
        return val
    if isinstance(val, (bytes, bytearray)):
        try:
            return json.loads(val.decode("utf-8"))
        except Exception:
            try:
                return val.decode("utf-8", "ignore")
            except Exception:
                return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val

def _named_in_clause(prefix: str, items: List[Any]):
    names = [f":{prefix}{i}" for i in range(len(items))]
    params = {f"{prefix}{i}": items[i] for i in range(len(items))}
    return ", ".join(names), params

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./openmemory.db")
user_id_str = os.getenv("EXPORT_USER_ID")
app_id_filter = os.getenv("EXPORT_APP_ID") or None
from_date = os.getenv("EXPORT_FROM_DATE")
to_date = os.getenv("EXPORT_TO_DATE")

if not user_id_str:
    print("Missing EXPORT_USER_ID", file=sys.stderr)
    sys.exit(2)

from_ts = None
to_ts = None
try:
    if from_date:
        from_ts = int(from_date)
    if to_date:
        to_ts = int(to_date)
except Exception:
    pass

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    user_row = conn.execute(
        text("SELECT id, user_id, name, email, metadata, created_at, updated_at FROM users WHERE user_id = :uid"),
        {"uid": user_id_str}
    ).mappings().first()
    if not user_row:
        print(f'User not found for user_id "{user_id_str}"', file=sys.stderr)
        sys.exit(1)

    user_uuid = user_row["id"]

    # Build memories filter
    params = {"user_id": user_uuid}
    conditions = ["user_id = :user_id"]
    if from_ts is not None:
        params["from_dt"] = datetime.datetime.fromtimestamp(from_ts, tz=datetime.timezone.utc)
        conditions.append("created_at >= :from_dt")
    if to_ts is not None:
        params["to_dt"] = datetime.datetime.fromtimestamp(to_ts, tz=datetime.timezone.utc)
        conditions.append("created_at <= :to_dt")
    if app_id_filter:
        try:
            # Accept UUID or raw DB value
            app_uuid = uuid.UUID(app_id_filter)
            params["app_id"] = str(app_uuid)
        except Exception:
            params["app_id"] = app_id_filter
        conditions.append("app_id = :app_id")

    mem_sql = f"""
      SELECT id, user_id, app_id, content, metadata, state, created_at, updated_at, archived_at, deleted_at
      FROM memories
      WHERE {' AND '.join(conditions)}
    """
    mem_rows = list(conn.execute(text(mem_sql), params).mappings())
    memory_ids = [r["id"] for r in mem_rows]
    app_ids = sorted({r["app_id"] for r in mem_rows if r["app_id"] is not None})

    # memory_categories
    mc_rows = []
    if memory_ids:
        names, in_params = _named_in_clause("mid", memory_ids)
        mc_rows = list(conn.execute(
            text(f"SELECT memory_id, category_id FROM memory_categories WHERE memory_id IN ({names})"),
            in_params
        ).mappings())

    # categories for referenced category_ids
    cats = []
    cat_ids = sorted({r["category_id"] for r in mc_rows})
    if cat_ids:
        names, in_params = _named_in_clause("cid", cat_ids)
        cats = list(conn.execute(
            text(f"SELECT id, name, description, created_at, updated_at FROM categories WHERE id IN ({names})"),
            in_params
        ).mappings())

    # apps for referenced app_ids
    apps = []
    if app_ids:
        names, in_params = _named_in_clause("aid", app_ids)
        apps = list(conn.execute(
            text(f"SELECT id, owner_id, name, description, metadata, is_active, created_at, updated_at FROM apps WHERE id IN ({names})"),
            in_params
        ).mappings())

    # status history for selected memories
    history = []
    if memory_ids:
        names, in_params = _named_in_clause("hid", memory_ids)
        history = list(conn.execute(
            text(f"SELECT id, memory_id, changed_by, old_state, new_state, changed_at FROM memory_status_history WHERE memory_id IN ({names})"),
            in_params
        ).mappings())

    # access_controls for the apps
    acls = []
    if app_ids:
        names, in_params = _named_in_clause("sid", app_ids)
        acls = list(conn.execute(
            text(f"""SELECT id, subject_type, subject_id, object_type, object_id, effect, created_at
                     FROM access_controls
                     WHERE subject_type = 'app' AND subject_id IN ({names})"""),
            in_params
        ).mappings())

    # Build helper maps
    app_name_by_id = {r["id"]: r["name"] for r in apps}
    app_rec_by_id = {r["id"]: r for r in apps}
    cat_name_by_id = {r["id"]: r["name"] for r in cats}
    mem_cat_ids_map: Dict[Any, List[Any]] = {}
    mem_cat_names_map: Dict[Any, List[str]] = {}
    for r in mc_rows:
        mem_cat_ids_map.setdefault(r["memory_id"], []).append(r["category_id"])
        mem_cat_names_map.setdefault(r["memory_id"], []).append(cat_name_by_id.get(r["category_id"], ""))

    # Build sqlite-like payload
    sqlite_payload = {
        "user": {
            "id": str(user_row["id"]),
            "user_id": user_row["user_id"],
            "name": user_row.get("name"),
            "email": user_row.get("email"),
            "metadata": _json_load_maybe(user_row.get("metadata")),
            "created_at": _iso(user_row.get("created_at")),
            "updated_at": _iso(user_row.get("updated_at")),
        },
        "apps": [
            {
                "id": str(a["id"]),
                "owner_id": str(a["owner_id"]) if a.get("owner_id") else None,
                "name": a["name"],
                "description": a.get("description"),
                "metadata": _json_load_maybe(a.get("metadata")),
                "is_active": bool(a.get("is_active")),
                "created_at": _iso(a.get("created_at")),
                "updated_at": _iso(a.get("updated_at")),
            }
            for a in apps
        ],
        "categories": [
            {
                "id": str(c["id"]),
                "name": c["name"],
                "description": c.get("description"),
                "created_at": _iso(c.get("created_at")),
                "updated_at": _iso(c.get("updated_at")),
            }
            for c in cats
        ],
        "memories": [
            {
                "id": str(m["id"]),
                "user_id": str(m["user_id"]),
                "app_id": str(m["app_id"]) if m.get("app_id") else None,
                "content": m.get("content") or "",
                "metadata": _json_load_maybe(m.get("metadata")) or {},
                "state": m.get("state"),
                "created_at": _iso(m.get("created_at")),
                "updated_at": _iso(m.get("updated_at")),
                "archived_at": _iso(m.get("archived_at")),
                "deleted_at": _iso(m.get("deleted_at")),
                "category_ids": [str(cid) for cid in mem_cat_ids_map.get(m["id"], [])],
            }
            for m in mem_rows
        ],
        "memory_categories": [
            {"memory_id": str(r["memory_id"]), "category_id": str(r["category_id"])}
            for r in mc_rows
        ],
        "status_history": [
            {
                "id": str(h["id"]),
                "memory_id": str(h["memory_id"]),
                "changed_by": str(h["changed_by"]),
                "old_state": h.get("old_state"),
                "new_state": h.get("new_state"),
                "changed_at": _iso(h.get("changed_at")),
            }
            for h in history
        ],
        "access_controls": [
            {
                "id": str(ac["id"]),
                "subject_type": ac.get("subject_type"),
                "subject_id": str(ac["subject_id"]) if ac.get("subject_id") else None,
                "object_type": ac.get("object_type"),
                "object_id": str(ac["object_id"]) if ac.get("object_id") else None,
                "effect": ac.get("effect"),
                "created_at": _iso(ac.get("created_at")),
            }
            for ac in acls
        ],
        "export_meta": {
            "app_id_filter": str(app_id_filter) if app_id_filter else None,
            "from_date": from_ts,
            "to_date": to_ts,
            "version": "1",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
    }

    # Write memories.json
    out_json = "/tmp/memories.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(sqlite_payload, f, indent=2, ensure_ascii=False)

    # Write logical jsonl.gz
    out_jsonl_gz = "/tmp/memories.jsonl.gz"
    with gzip.open(out_jsonl_gz, "wb") as gz:
        for m in mem_rows:
            record = {
                "id": str(m["id"]),
                "content": m.get("content") or "",
                "metadata": _json_load_maybe(m.get("metadata")) or {},
                "created_at": _iso(m.get("created_at")),
                "updated_at": _iso(m.get("updated_at")),
                "state": m.get("state"),
                "app": app_name_by_id.get(m.get("app_id")) if m.get("app_id") else None,
                "categories": [c for c in mem_cat_names_map.get(m["id"], []) if c],
            }
            gz.write((json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))

    print(out_json)
    print(out_jsonl_gz)
PYCODE
PY_EXIT=$?
set -e
if [[ $PY_EXIT -ne 0 ]]; then
  echo "ERROR: Export failed inside container (exit code $PY_EXIT)"
  exit $PY_EXIT
fi

# Copy files out of the container
TMPDIR="$(mktemp -d)"
docker cp "${CONTAINER}:/tmp/memories.json" "${TMPDIR}/memories.json"
docker cp "${CONTAINER}:/tmp/memories.jsonl.gz" "${TMPDIR}/memories.jsonl.gz"

# Create zip on host
ZIP_NAME="memories_export_${USER_ID}.zip"
if command -v zip >/dev/null 2>&1; then
  (cd "${TMPDIR}" && zip -q -r "../${ZIP_NAME}" "memories.json" "memories.jsonl.gz")
  mv "${TMPDIR}/../${ZIP_NAME}" "./${ZIP_NAME}"
else
  # Fallback: use Python zipfile
  python3 - <<PYFALLBACK
import sys, zipfile
zf = zipfile.ZipFile("${ZIP_NAME}", "w", compression=zipfile.ZIP_DEFLATED)
zf.write("${TMPDIR}/memories.json", arcname="memories.json")
zf.write("${TMPDIR}/memories.jsonl.gz", arcname="memories.jsonl.gz")
zf.close()
print("${ZIP_NAME}")
PYFALLBACK
fi

echo "Wrote ./${ZIP_NAME}"
echo "Done."