"""Periodic cleanup of abandoned work directories."""
from __future__ import annotations
import asyncio
import shutil
import time
from pathlib import Path

from dansticker.config import cfg
from dansticker.logger import get_logger

log = get_logger("jobs.cleanup")

MAX_AGE_SECONDS = 6 * 60 * 60  # 6 hours


async def cleanup_abandoned_jobs() -> None:
    work_dir = cfg.WORK_DIR
    if not work_dir.exists():
        return

    now = time.time()
    cleaned = 0

    for entry in work_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            age = now - entry.stat().st_mtime
            if age > MAX_AGE_SECONDS:
                shutil.rmtree(entry, ignore_errors=True)
                cleaned += 1
                log.debug(f"Removed abandoned job dir: {entry.name}")
        except Exception:
            pass

    if cleaned:
        log.info(f"Periodic cleanup: removed {cleaned} abandoned job directories")


async def start_periodic_cleanup(interval_seconds: int = 3600) -> None:
    """Run cleanup in the background every interval_seconds."""
    while True:
        await asyncio.sleep(interval_seconds)
        await cleanup_abandoned_jobs()
