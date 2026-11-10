from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

DEFAULT_THRESHOLD_PERCENT = 30

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tracked_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_text TEXT NOT NULL UNIQUE,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_items (
    item_id TEXT PRIMARY KEY,
    model_id INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class TrackedModel:
    id: int
    search_text: str
    added_at: str


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(_SCHEMA)
        await conn.commit()


async def add_tracked_model(db_path: str, search_text: str) -> int:
    added_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "INSERT INTO tracked_models (search_text, added_at) VALUES (?, ?)",
            (search_text, added_at),
        )
        await conn.commit()
        return cursor.lastrowid


async def remove_tracked_model(db_path: str, model_id: int) -> bool:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("DELETE FROM tracked_models WHERE id = ?", (model_id,))
        await conn.commit()
        return cursor.rowcount > 0


async def list_tracked_models(db_path: str) -> list[TrackedModel]:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT id, search_text, added_at FROM tracked_models ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [TrackedModel(row[0], row[1], row[2]) for row in rows]


async def get_threshold_percent(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT value FROM settings WHERE key = 'threshold_percent'"
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else DEFAULT_THRESHOLD_PERCENT


async def set_threshold_percent(db_path: str, value: int) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO settings (key, value) VALUES ('threshold_percent', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(value),),
        )
        await conn.commit()


async def filter_unseen_item_ids(db_path: str, item_ids: list[str]) -> list[str]:
    if not item_ids:
        return []
    async with aiosqlite.connect(db_path) as conn:
        placeholders = ",".join("?" for _ in item_ids)
        cursor = await conn.execute(
            f"SELECT item_id FROM seen_items WHERE item_id IN ({placeholders})",
            item_ids,
        )
        rows = await cursor.fetchall()
        seen = {row[0] for row in rows}
        return [item_id for item_id in item_ids if item_id not in seen]


async def mark_items_seen(db_path: str, model_id: int, item_ids: list[str]) -> None:
    if not item_ids:
        return
    first_seen_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(
            "INSERT OR IGNORE INTO seen_items (item_id, model_id, first_seen_at) "
            "VALUES (?, ?, ?)",
            [(item_id, model_id, first_seen_at) for item_id in item_ids],
        )
        await conn.commit()


async def purge_old_seen_items(db_path: str, older_than_days: int = 30) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("DELETE FROM seen_items WHERE first_seen_at < ?", (cutoff,))
        await conn.commit()
        return cursor.rowcount
