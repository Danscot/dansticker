from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _opt(key: str, fallback: str) -> str:
    return os.getenv(key, fallback)


def _opt_int(key: str, fallback: int) -> int:
    val = os.getenv(key)
    return int(val) if val else fallback


def _opt_float(key: str, fallback: float) -> float:
    val = os.getenv(key)
    return float(val) if val else fallback


class Config:
    # Token — lazily validated so tests can import without a real token
    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        val = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not val:
            raise RuntimeError("Missing required environment variable: TELEGRAM_BOT_TOKEN")
        return val

    DEFAULT_AUTHOR: str = _opt("DEFAULT_AUTHOR", "Dansticker")
    DB_PATH: Path = Path(_opt("DB_PATH", "data/dansticker.db"))
    WORK_DIR: Path = Path(_opt("WORK_DIR", "work"))
    LOG_DIR: Path = Path(_opt("LOG_DIR", "logs"))
    LOG_LEVEL: str = _opt("LOG_LEVEL", "INFO")
    MAX_CONCURRENT_JOBS: int = _opt_int("MAX_CONCURRENT_JOBS", 2)
    MAX_CONCURRENT_DOWNLOADS: int = _opt_int("MAX_CONCURRENT_DOWNLOADS", 3)
    MAX_STICKERS_PER_PACK: int = _opt_int("MAX_STICKERS_PER_PACK", 30)
    MAX_SINGLE_STICKER_SIZE: int = _opt_int("MAX_SINGLE_STICKER_SIZE", 10_485_760)
    MAX_DOWNLOAD_SIZE: int = _opt_int("MAX_DOWNLOAD_SIZE", 209_715_200)
    MAX_VIDEO_DURATION: float = _opt_float("MAX_VIDEO_DURATION", 8.0)
    MAX_OUTPUT_SIZE: int = _opt_int("MAX_OUTPUT_SIZE", 512_000)
    MAX_JOB_RUNTIME: int = _opt_int("MAX_JOB_RUNTIME", 600)
    MAX_FFMPEG_TIMEOUT: int = _opt_int("MAX_FFMPEG_TIMEOUT", 120)
    TARGET_WIDTH: int = 512
    TARGET_HEIGHT: int = 512
    THUMBNAIL_WIDTH: int = 96
    THUMBNAIL_HEIGHT: int = 96
    WEBP_QUALITY: int = _opt_int("WEBP_QUALITY", 80)
    WEBP_FPS: int = _opt_int("WEBP_FPS", 15)
    MAX_WEBP_FPS: int = 30
    FFMPEG_PATH: str = _opt("FFMPEG_PATH", "ffmpeg")
    FFPROBE_PATH: str = _opt("FFPROBE_PATH", "ffprobe")


cfg = Config()
