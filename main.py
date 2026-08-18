"""Dansticker bot entry point."""
from __future__ import annotations
import asyncio
import logging
from pathlib import Path

from telegram.ext import Application

from dansticker.bot.handlers import register_handlers
from dansticker.config import cfg
from dansticker.jobs.cleanup import start_periodic_cleanup
from dansticker.logger import get_logger
from dansticker.storage.db import get_db, close_db

log = get_logger("main")


async def main() -> None:
    # Ensure directories exist
    for d in (cfg.WORK_DIR, cfg.LOG_DIR, cfg.DB_PATH.parent):
        Path(d).mkdir(parents=True, exist_ok=True)

    # Init database
    await get_db()

    log.info("Starting Dansticker bot...")

    app = Application.builder().token(cfg.TELEGRAM_BOT_TOKEN).build()
    register_handlers(app)

    # Background cleanup task
    asyncio.create_task(start_periodic_cleanup())

    log.info("Dansticker is running")
    await app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
