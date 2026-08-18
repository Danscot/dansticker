"""Convert WebM video stickers to animated WebP with 3-strategy fallback."""
from __future__ import annotations
import asyncio
import os
import time
from pathlib import Path

from dansticker.config import cfg
from dansticker.logger import get_logger
from dansticker.media.animation import encode_animated_webp, EncodeOptions
from dansticker.media.inspector import inspect_media
from dansticker.media.validator import validate_webp
from dansticker.types import ConversionResult, ConversionStrategy, MediaInfo

log = get_logger("media.webm")

W, H = cfg.TARGET_WIDTH, cfg.TARGET_HEIGHT


def _fps(info: MediaInfo) -> int:
    return min(int(info.fps or cfg.WEBP_FPS), cfg.MAX_WEBP_FPS)


# ── Strategy A: preserve alpha via rgba pixel format ─────────────────────────

async def _strategy_alpha(source: str, out: str, info: MediaInfo) -> bool:
    fps = _fps(info)
    fc = (
        f"[0:v]fps={fps},"
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
        f"format=rgba[v]"
    )
    try:
        await encode_animated_webp(EncodeOptions(
            input_file=source,
            output_path=out,
            fps=fps,
            filter_complex=fc,
            extra_output_args=["-map", "[v]"],
        ))
        return True
    except Exception as e:
        log.debug(f"Strategy alpha failed: {e}")
        return False


# ── Strategy B: yuva420p normalization ───────────────────────────────────────

async def _strategy_rgba_normalize(source: str, out: str, info: MediaInfo) -> bool:
    fps = _fps(info)
    fc = (
        f"[0:v]fps={fps},"
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
        f"format=yuva420p[v]"
    )
    try:
        await encode_animated_webp(EncodeOptions(
            input_file=source,
            output_path=out,
            fps=fps,
            filter_complex=fc,
            extra_output_args=["-map", "[v]", "-pix_fmt", "yuva420p"],
        ))
        return True
    except Exception as e:
        log.debug(f"Strategy rgba_normalize failed: {e}")
        return False


# ── Strategy C: flatten (no alpha) ───────────────────────────────────────────

async def _strategy_flatten(source: str, out: str, info: MediaInfo) -> bool:
    fps = _fps(info)
    try:
        await encode_animated_webp(EncodeOptions(
            input_file=source,
            output_path=out,
            fps=fps,
        ))
        return True
    except Exception as e:
        log.debug(f"Strategy flatten failed: {e}")
        return False


# ── Main converter ────────────────────────────────────────────────────────────

async def convert_webm(source_path: str, output_path: str, job_id: str = "") -> ConversionResult:
    start = time.monotonic()
    logger = log.getChild(job_id) if job_id else log

    # Step 1 – inspect
    try:
        info = await inspect_media(source_path)
        logger.debug(f"Inspected: codec={info.codec} {info.width}x{info.height} "
                     f"fps={info.fps} duration={info.duration} alpha={info.has_alpha}")
    except Exception as e:
        return ConversionResult(success=False, reason=f"ffprobe_error: {e}",
                                duration_ms=(time.monotonic() - start) * 1000)

    # Step 2 – duration guard
    if info.duration and info.duration > cfg.MAX_VIDEO_DURATION:
        return ConversionResult(
            success=False,
            reason=f"video_too_long: {info.duration:.1f}s",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    strategies = [
        (ConversionStrategy.ALPHA_PRESERVE,  _strategy_alpha),
        (ConversionStrategy.RGBA_NORMALIZE,  _strategy_rgba_normalize),
        (ConversionStrategy.FLATTEN_BG,      _strategy_flatten),
    ]

    for strategy, fn in strategies:
        # Clean previous attempt
        if os.path.exists(output_path):
            os.unlink(output_path)

        logger.debug(f"Trying strategy: {strategy.value}")
        ok = await fn(source_path, output_path, info)
        if not ok:
            continue

        result = validate_webp(output_path)
        if result.valid:
            logger.debug(f"Strategy {strategy.value} succeeded")
            return ConversionResult(
                success=True,
                output_path=output_path,
                strategy=strategy,
                duration_ms=(time.monotonic() - start) * 1000,
            )
        logger.warning(f"Strategy {strategy.value} produced invalid output: {result.reason}")

    return ConversionResult(
        success=False,
        reason="all_strategies_failed",
        duration_ms=(time.monotonic() - start) * 1000,
    )
