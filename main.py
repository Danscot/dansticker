"""Dansticker bot entry point."""
import asyncio
from pathlib import Path

from telegram.ext import Application

from dansticker.bot.handlers import register_handlers
from dansticker.config import cfg
from dansticker.jobs.cleanup import start_periodic_cleanup
from dansticker.logger import get_logger
from dansticker.storage.db import get_db, close_db

log = get_logger("main")


async def post_init(app: Application) -> None:
    """Called by PTB after the event loop is running — safe to do async work here."""
    await get_db()
    asyncio.create_task(start_periodic_cleanup())
    log.info("Dansticker is running")


def main() -> None:
    # Ensure directories exist
    for d in (cfg.WORK_DIR, cfg.LOG_DIR, cfg.DB_PATH.parent):
        Path(d).mkdir(parents=True, exist_ok=True)

    log.info("Starting Dansticker bot...")

    app = (
        Application.builder()
        .token(cfg.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    register_handlers(app)

    # PTB v20+ manages its own event loop — do NOT wrap in asyncio.run()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
