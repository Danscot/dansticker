"""Dispatcher: routes each sticker to the correct converter."""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor

from dansticker.logger import sticker_logger
from dansticker.media.static_webp import convert_static_webp
from dansticker.media.webm import convert_webm
from dansticker.media.tgs import convert_tgs
from dansticker.types import Sticker, StickerSourceType, ConversionResult

# Thread pool for CPU-bound Pillow operations
_thread_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pillow")


async def convert_sticker(sticker: Sticker, work_dir: str, job_id: str) -> ConversionResult:
    import os
    from pathlib import Path

    log = sticker_logger(job_id, sticker.index)

    if not sticker.source_path:
        return ConversionResult(success=False, reason="no_source_path")

    output_path = str(Path(work_dir) / "normalized" / f"sticker_{sticker.index}.webp")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    log.info(f"Converting [{sticker.source_type.value}]")

    loop = asyncio.get_event_loop()

    if sticker.source_type == StickerSourceType.WEBP:
        # Pillow is synchronous — run in thread pool
        result = await loop.run_in_executor(
            _thread_pool,
            convert_static_webp,
            sticker.source_path,
            output_path,
        )

    elif sticker.source_type == StickerSourceType.WEBM:
        result = await convert_webm(sticker.source_path, output_path, job_id)

    elif sticker.source_type == StickerSourceType.TGS:
        result = await convert_tgs(sticker.source_path, output_path, job_id)

    else:
        result = ConversionResult(
            success=False,
            reason=f"unsupported_source_type: {sticker.source_type.value}",
        )

    log.info(
        f"{'SUCCESS' if result.success else 'FAILED'} "
        f"strategy={result.strategy.value if result.strategy else 'none'} "
        f"duration={result.duration_ms:.0f}ms"
        + (f" reason={result.reason}" if not result.success else "")
    )

    return result
