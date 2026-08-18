"""Download sticker packs and media from Telegram."""
from __future__ import annotations
import asyncio
import os
from pathlib import Path
from typing import Optional, Callable, Awaitable

import httpx

from dansticker.config import cfg
from dansticker.logger import get_logger
from dansticker.types import (
    Sticker, StickerPack, StickerSourceType, PackType, MediaInfo
)

log = get_logger("telegram.downloader")

API_BASE = "https://api.telegram.org"


def _infer_source_type(is_video: bool, is_animated: bool) -> StickerSourceType:
    if is_video:
        return StickerSourceType.WEBM
    if is_animated:
        return StickerSourceType.TGS
    return StickerSourceType.WEBP


class TelegramDownloader:
    def __init__(self, token: str):
        self._token = token
        self._api = f"{API_BASE}/bot{token}"
        self._file_api = f"{API_BASE}/file/bot{token}"

    # ── API helpers ────────────────────────────────────────────────────────────

    async def _get(self, method: str, **params) -> dict:
        url = f"{self._api}/{method}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error in {method}: {data.get('description', 'unknown')}")
        return data["result"]

    async def get_sticker_set(self, pack_name: str) -> dict:
        return await self._get("getStickerSet", name=pack_name)

    async def get_file(self, file_id: str) -> dict:
        return await self._get("getFile", file_id=file_id)

    async def download_file(self, file_id: str, dest_path: Path) -> None:
        """Download a Telegram file by file_id to dest_path."""
        file_info = await self.get_file(file_id)
        file_path = file_info.get("file_path")
        if not file_path:
            raise RuntimeError(f"No file_path for file_id={file_id}")

        file_size = file_info.get("file_size", 0)
        if file_size and file_size > cfg.MAX_SINGLE_STICKER_SIZE:
            raise RuntimeError(
                f"File too large: {file_size} bytes (max {cfg.MAX_SINGLE_STICKER_SIZE})"
            )

        url = f"{self._file_api}/{file_path}"
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)

        log.debug(f"Downloaded {file_id} -> {dest_path}")

    # ── Pack resolution ────────────────────────────────────────────────────────

    async def resolve_pack(self, pack_name: str, job_id: str) -> StickerPack:
        """Fetch pack metadata and build a StickerPack (no download yet)."""
        log.info(f"[{job_id}] Resolving pack: {pack_name}")
        raw = await self.get_sticker_set(pack_name)

        stickers = []
        for i, s in enumerate(raw.get("stickers", [])):
            source_type = _infer_source_type(s.get("is_video", False), s.get("is_animated", False))
            animated = s.get("is_animated", False) or s.get("is_video", False)
            stickers.append(Sticker(
                index=i,
                file_id=s["file_id"],
                source_type=source_type,
                emoji=s.get("emoji", "🎉"),
                animated=animated,
                video=s.get("is_video", False),
            ))

        has_static = any(not s.animated for s in stickers)
        has_animated = any(s.animated for s in stickers)
        if has_static and has_animated:
            pack_type = PackType.MIXED
        elif has_animated:
            pack_type = PackType.ANIMATED
        else:
            pack_type = PackType.STATIC

        return StickerPack(
            id=job_id,
            telegram_url=f"https://t.me/addstickers/{pack_name}",
            telegram_name=raw["title"],
            name=raw["title"],
            author=cfg.DEFAULT_AUTHOR,
            stickers=stickers,
            pack_type=pack_type,
        )

    async def download_thumbnail(self, raw_set: dict, dest_dir: Path) -> Optional[str]:
        thumb = raw_set.get("thumbnail")
        if not thumb:
            return None
        dest = dest_dir / "thumbnail_source"
        try:
            await self.download_file(thumb["file_id"], dest)
            return str(dest)
        except Exception as e:
            log.warning(f"Thumbnail download failed: {e}")
            return None

    async def download_sticker(self, sticker: Sticker, dest_dir: Path) -> str:
        ext = sticker.source_type.value
        dest = dest_dir / f"sticker_{sticker.index}.{ext}"
        await self.download_file(sticker.file_id, dest)
        return str(dest)

    async def download_all_stickers(
        self,
        pack: StickerPack,
        dest_dir: Path,
        on_progress: Optional[Callable[[int, int], Awaitable[None]]] = None,
    ) -> None:
        """Download all stickers with limited concurrency."""
        sem = asyncio.Semaphore(cfg.MAX_CONCURRENT_DOWNLOADS)
        done = 0
        total = len(pack.stickers)

        async def _download_one(sticker: Sticker) -> None:
            nonlocal done
            async with sem:
                try:
                    path = await self.download_sticker(sticker, dest_dir / "source")
                    sticker.source_path = path
                except Exception as e:
                    log.error(f"Failed to download sticker {sticker.index}: {e}")
                    sticker.status = __import__('dansticker.types', fromlist=['StickerStatus']).StickerStatus.FAILED
                    sticker.error = "download_failed"
                finally:
                    done += 1
                    if on_progress:
                        await on_progress(done, total)

        await asyncio.gather(*[_download_one(s) for s in pack.stickers])
