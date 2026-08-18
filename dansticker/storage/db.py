"""SQLite storage for user preferences using aiosqlite."""
from __future__ import annotations
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from dansticker.config import cfg
from dansticker.logger import get_logger
from dansticker.types import UserPreferences

log = get_logger("storage.db")

_db: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        Path(cfg.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _db = await aiosqlite.connect(cfg.DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _migrate(_db)
        log.info(f"Database opened: {cfg.DB_PATH}")
    return _db


async def _migrate(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            telegram_user_id INTEGER PRIMARY KEY,
            preferred_author  TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        )
    """)
    await db.commit()
    log.debug("Database migrated")


async def get_user_preferences(user_id: int) -> Optional[UserPreferences]:
    db = await get_db()
    async with db.execute(
        "SELECT * FROM user_preferences WHERE telegram_user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return None
    return UserPreferences(
        telegram_user_id=row["telegram_user_id"],
        preferred_author=row["preferred_author"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


async def save_user_preferences(user_id: int, author: str) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT INTO user_preferences (telegram_user_id, preferred_author, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_user_id) DO UPDATE SET
            preferred_author = excluded.preferred_author,
            updated_at       = excluded.updated_at
        """,
        (user_id, author, datetime.utcnow().isoformat()),
    )
    await db.commit()


async def get_preferred_author(user_id: int) -> str:
    prefs = await get_user_preferences(user_id)
    return prefs.preferred_author if prefs else cfg.DEFAULT_AUTHOR


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None
