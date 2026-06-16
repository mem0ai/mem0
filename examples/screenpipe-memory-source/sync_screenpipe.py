from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_DB_PATH = Path("~/.screenpipe/db.sqlite").expanduser()
DEFAULT_TABLES = ("frames", "ocr_text", "audio_transcriptions")

TEXT_COLUMNS = ("accessibility_text", "text", "transcription", "content", "ocr_text")
TIME_COLUMNS = ("timestamp", "created_at", "captured_at", "recorded_at", "start_time", "datetime")
APP_COLUMNS = ("app_name", "application_name", "app")
WINDOW_COLUMNS = ("window_name", "window_title", "title")
URL_COLUMNS = ("url", "browser_url", "source_url")
DEVICE_COLUMNS = ("device_name", "device", "audio_device")
SPEAKER_COLUMNS = ("speaker_name", "speaker", "speaker_id")


@dataclass(frozen=True)
class ScreenpipeEntry:
    table: str
    row_id: int
    text: str
    captured_at: Optional[str] = None
    app_name: Optional[str] = None
    window_name: Optional[str] = None
    url: Optional[str] = None
    device_name: Optional[str] = None
    speaker: Optional[str] = None

    @property
    def source_type(self) -> str:
        if self.table == "audio_transcriptions":
            return "audio"
        if self.table == "ocr_text":
            return "ocr"
        return "screen"

    def to_memory_text(self, *, max_text_chars: int = 4000) -> str:
        parts = [f"Screenpipe {self.source_type} observation"]
        if self.captured_at:
            parts.append(f"captured_at={self.captured_at}")
        if self.app_name:
            parts.append(f"app={self.app_name}")
        if self.window_name:
            parts.append(f"window={self.window_name}")
        if self.url:
            parts.append(f"url={self.url}")

        text = self.text.strip()
        if len(text) > max_text_chars:
            text = f"{text[:max_text_chars].rstrip()}..."
        return f"{' | '.join(parts)}\n\n{text}"

    def to_metadata(self) -> Dict[str, Any]:
        metadata = {
            "source": "screenpipe",
            "screenpipe_table": self.table,
            "screenpipe_row_id": self.row_id,
            "screenpipe_type": self.source_type,
        }
        optional_values = {
            "captured_at": self.captured_at,
            "app_name": self.app_name,
            "window_name": self.window_name,
            "url": self.url,
            "device_name": self.device_name,
            "speaker": self.speaker,
        }
        metadata.update({key: value for key, value in optional_values.items() if value})
        return metadata


def read_screenpipe_entries(
    db_path: Path,
    *,
    tables: Iterable[str] = DEFAULT_TABLES,
    limit: int = 50,
    since: Optional[str] = None,
) -> List[ScreenpipeEntry]:
    if limit <= 0:
        raise ValueError("limit must be greater than 0")
    if not db_path.exists():
        raise FileNotFoundError(f"Screenpipe database not found: {db_path}")

    since_dt = parse_datetime(since) if since else None
    entries: List[ScreenpipeEntry] = []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing_tables = get_table_names(conn)

        for table in tables:
            if table not in existing_tables:
                continue

            columns = get_columns(conn, table)
            text_column = first_existing(columns, TEXT_COLUMNS)
            if not text_column:
                continue

            selected_columns = {
                "text": text_column,
                "captured_at": first_existing(columns, TIME_COLUMNS),
                "app_name": first_existing(columns, APP_COLUMNS),
                "window_name": first_existing(columns, WINDOW_COLUMNS),
                "url": first_existing(columns, URL_COLUMNS),
                "device_name": first_existing(columns, DEVICE_COLUMNS),
                "speaker": first_existing(columns, SPEAKER_COLUMNS),
            }

            rows = fetch_rows(conn, table, selected_columns, per_table_limit=max(limit * 2, limit))
            for row in rows:
                entry = row_to_entry(table, row, selected_columns)
                if since_dt and entry.captured_at:
                    entry_dt = parse_datetime(entry.captured_at)
                    if entry_dt and entry_dt < since_dt:
                        continue
                if entry.text:
                    entries.append(entry)

    entries.sort(key=lambda item: item.captured_at or "", reverse=True)
    return entries[:limit]


def sync_entries(
    memory: Any,
    entries: Iterable[ScreenpipeEntry],
    *,
    user_id: str,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    infer: bool = False,
    dry_run: bool = False,
    max_text_chars: int = 4000,
) -> int:
    synced = 0
    for entry in entries:
        content = entry.to_memory_text(max_text_chars=max_text_chars)
        metadata = entry.to_metadata()

        if dry_run:
            print(f"[dry-run] {entry.table}:{entry.row_id} {content[:120]!r}")
            synced += 1
            continue

        if memory.__class__.__name__.endswith("MemoryClient"):
            filters = {"user_id": user_id}
            if agent_id:
                filters["agent_id"] = agent_id
            if run_id:
                filters["run_id"] = run_id
            memory.add(content, filters=filters, metadata=metadata, infer=infer)
        else:
            memory.add(content, user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=metadata, infer=infer)
        synced += 1

    return synced


def build_memory_client(config_path: Optional[Path]) -> Any:
    if config_path:
        from mem0 import Memory

        with config_path.open("r", encoding="utf-8") as file:
            config = json.load(file)
        return Memory.from_config(config)

    from mem0 import MemoryClient

    return MemoryClient()


def get_table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
    return {row["name"] for row in rows}


def first_existing(columns: set[str], candidates: Iterable[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def fetch_rows(
    conn: sqlite3.Connection,
    table: str,
    selected_columns: Dict[str, Optional[str]],
    *,
    per_table_limit: int,
) -> List[sqlite3.Row]:
    column_names = ["rowid", *[column for column in selected_columns.values() if column]]
    seen = set()
    deduped_columns = []
    for column in column_names:
        if column not in seen:
            seen.add(column)
            deduped_columns.append(column)

    text_column = selected_columns["text"]
    order_column = selected_columns.get("captured_at") or "rowid"
    sql = (
        f"SELECT {', '.join(quote_identifier(column) for column in deduped_columns)} "
        f"FROM {quote_identifier(table)} "
        f"WHERE {quote_identifier(text_column)} IS NOT NULL "
        f"AND TRIM({quote_identifier(text_column)}) != '' "
        f"ORDER BY {quote_identifier(order_column)} DESC "
        "LIMIT ?"
    )
    return conn.execute(sql, (per_table_limit,)).fetchall()


def row_to_entry(table: str, row: sqlite3.Row, selected_columns: Dict[str, Optional[str]]) -> ScreenpipeEntry:
    def value(name: str) -> Optional[str]:
        column = selected_columns.get(name)
        if not column or column not in row.keys():
            return None
        raw_value = row[column]
        return str(raw_value).strip() if raw_value is not None and str(raw_value).strip() else None

    return ScreenpipeEntry(
        table=table,
        row_id=int(row["rowid"]),
        text=value("text") or "",
        captured_at=normalize_timestamp(value("captured_at")),
        app_name=value("app_name"),
        window_name=value("window_name"),
        url=value("url"),
        device_name=value("device_name"),
        speaker=value("speaker"),
    )


def normalize_timestamp(value: Optional[str]) -> Optional[str]:
    parsed = parse_datetime(value)
    return parsed.isoformat() if parsed else value


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        numeric = float(value)
    except ValueError:
        numeric = None

    if numeric is not None:
        if numeric > 1_000_000_000_000:
            numeric = numeric / 1000
        return datetime.fromtimestamp(numeric, tz=timezone.utc)

    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) + chr(34))}"'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Screenpipe SQLite observations into Mem0.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to Screenpipe db.sqlite.")
    parser.add_argument("--config", type=Path, help="Mem0 OSS config JSON. Omit to use Mem0 Platform.")
    parser.add_argument("--user-id", required=True, help="Mem0 user_id to attach to synced memories.")
    parser.add_argument("--agent-id", help="Optional Mem0 agent_id.")
    parser.add_argument("--run-id", help="Optional Mem0 run_id.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum entries to sync.")
    parser.add_argument("--since", help="Only sync entries captured at or after this ISO timestamp.")
    parser.add_argument("--infer", action="store_true", help="Let Mem0 infer concise facts from each observation.")
    parser.add_argument("--dry-run", action="store_true", help="Print entries without writing to Mem0.")
    parser.add_argument("--max-text-chars", type=int, default=4000, help="Maximum text characters per memory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    entries = read_screenpipe_entries(args.db.expanduser(), limit=args.limit, since=args.since)
    memory = None if args.dry_run else build_memory_client(args.config)
    synced = sync_entries(
        memory,
        entries,
        user_id=args.user_id,
        agent_id=args.agent_id,
        run_id=args.run_id,
        infer=args.infer,
        dry_run=args.dry_run,
        max_text_chars=args.max_text_chars,
    )
    print(f"Processed {synced} Screenpipe entries.")


if __name__ == "__main__":
    main()
