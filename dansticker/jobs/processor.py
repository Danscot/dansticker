"""Orchestrate the full download → convert → validate → package pipeline."""
from __future__ import annotations
import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Awaitable, Optional, List

from dansticker.config import cfg
from dansticker.logger import job_logger
from dansticker.media.converter import convert_sticker
from dansticker.pack.builder import build_wastickers
from dansticker.pack.splitter import split_into_wa_packs
from dansticker.telegram.downloader import TelegramDownloader
from dansticker.telegram.pack_resolver import parse_pack_url
from dansticker.types import Job, StickerPack, StickerStatus, JobStatus

Stage = str
ProgressCb = Callable[[Stage, int, int], Awaitable[None]]

_build_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pack_builder")


@dataclass
class ProcessResult:
    success: bool
    output_paths: List[str] = field(default_factory=list)
    success_count: int = 0
    failed_count: int = 0
    total_packs: int = 0
    error: Optional[str] = None


async def process_job(job: Job, on_progress: Optional[ProgressCb] = None) -> ProcessResult:
    log = job_logger(job.id)
    work_dir = cfg.WORK_DIR / job.id

    async def progress(stage: str, done: int, total: int) -> None:
        if on_progress:
            await on_progress(stage, done, total)

    try:
        # ── Dirs ──────────────────────────────────────────────────────────────
        for sub in ("source", "normalized", "output"):
            (work_dir / sub).mkdir(parents=True, exist_ok=True)

        # ── Resolve pack name ─────────────────────────────────────────────────
        pack_name = parse_pack_url(job.telegram_url)
        if not pack_name:
            return ProcessResult(success=False, error="Invalid Telegram sticker pack URL")

        downloader = TelegramDownloader(cfg.TELEGRAM_BOT_TOKEN)

        # ── Fetch metadata ────────────────────────────────────────────────────
        log.info(f"Resolving pack: {pack_name}")
        pack = await downloader.resolve_pack(pack_name, job.id)
        pack.name = job.pack_name
        pack.author = job.author

        # ── Thumbnail ─────────────────────────────────────────────────────────
        raw_set = await downloader.get_sticker_set(pack_name)
        pack.thumbnail_path = await downloader.download_thumbnail(raw_set, work_dir / "source")

        # ── Download stickers ─────────────────────────────────────────────────
        total = len(pack.stickers)
        log.info(f"Downloading {total} stickers")
        await progress("downloading", 0, total)

        await downloader.download_all_stickers(
            pack,
            work_dir,
            on_progress=lambda done, tot: progress("downloading", done, tot),
        )

        # ── Convert stickers ──────────────────────────────────────────────────
        log.info("Converting stickers")
        await progress("converting", 0, total)

        sem = asyncio.Semaphore(cfg.MAX_CONCURRENT_JOBS)
        converted = 0

        async def _convert_one(sticker) -> None:
            nonlocal converted
            async with sem:
                if sticker.status == StickerStatus.FAILED:
                    # Already failed at download
                    converted += 1
                    await progress("converting", converted, total)
                    return

                sticker.status = StickerStatus.PROCESSING
                result = await convert_sticker(sticker, str(work_dir), job.id)

                if result.success and result.output_path:
                    sticker.status = StickerStatus.SUCCESS
                    sticker.output_path = result.output_path
                    sticker.strategy = result.strategy
                else:
                    sticker.status = StickerStatus.FAILED
                    sticker.error = result.reason

                sticker.duration_ms = result.duration_ms
                converted += 1
                await progress("converting", converted, total)

        await asyncio.gather(*[_convert_one(s) for s in pack.stickers])

        # ── Tally ─────────────────────────────────────────────────────────────
        success_count = sum(1 for s in pack.stickers if s.status == StickerStatus.SUCCESS)
        failed_count  = sum(1 for s in pack.stickers if s.status == StickerStatus.FAILED)
        log.info(f"Conversion done: {success_count} OK, {failed_count} failed")
        await progress("validating", total, total)

        if success_count == 0:
            return ProcessResult(
                success=False,
                success_count=0,
                failed_count=failed_count,
                error="No stickers could be converted",
            )

        # ── Split & build packs ───────────────────────────────────────────────
        wa_packs = split_into_wa_packs(pack)
        log.info(f"Building {len(wa_packs)} WhatsApp pack(s)")
        await progress("packaging", 0, len(wa_packs))

        loop = asyncio.get_event_loop()
        output_paths: List[str] = []

        for i, wa_pack in enumerate(wa_packs):
            pack_dir = str(work_dir / f"package_{i + 1}")
            output_dir = str(work_dir / "output")

            build_result = await loop.run_in_executor(
                _build_pool,
                build_wastickers,
                wa_pack,
                output_dir,
                pack_dir,
            )

            if build_result.success and build_result.output_path:
                output_paths.append(build_result.output_path)
            else:
                log.error(f"Pack {i + 1} build failed: {build_result.reason}")

            await progress("packaging", i + 1, len(wa_packs))

        return ProcessResult(
            success=True,
            output_paths=output_paths,
            success_count=success_count,
            failed_count=failed_count,
            total_packs=len(output_paths),
        )

    except Exception as e:
        log.exception(f"Job failed: {e}")
        return ProcessResult(success=False, error=str(e))


async def cleanup_job(job_id: str) -> None:
    work_dir = cfg.WORK_DIR / job_id
    try:
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
            job_logger(job_id).info("Cleaned up work directory")
    except Exception as e:
        job_logger(job_id).warning(f"Cleanup failed: {e}")
