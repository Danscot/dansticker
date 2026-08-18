"""Structured logging for Dansticker."""
import logging
import sys
from pathlib import Path
from dansticker.config import cfg

Path(cfg.LOG_DIR).mkdir(parents=True, exist_ok=True)

_fmt = logging.Formatter(
    "%(asctime)s %(levelname)-8s %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_handler_console = logging.StreamHandler(sys.stdout)
_handler_console.setFormatter(_fmt)

_handler_file = logging.FileHandler(cfg.LOG_DIR / "dansticker.log", encoding="utf-8")
_handler_file.setFormatter(_fmt)

logging.basicConfig(level=cfg.LOG_LEVEL, handlers=[_handler_console, _handler_file])


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def job_logger(job_id: str) -> logging.Logger:
    return logging.getLogger(f"job.{job_id}")


def sticker_logger(job_id: str, index: int) -> logging.Logger:
    return logging.getLogger(f"job.{job_id}.sticker_{index}")
