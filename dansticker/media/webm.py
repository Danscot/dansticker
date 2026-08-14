"""Convert WebM video stickers to animated WebP with 3-strategy fallback + size reduction."""
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

# Size-reduction ladder: (fps, quality, compression_level)
# Tried in order when output is file_too_large.
_SIZE_LADDER = [
    (15, 80, 6),
    (12, 70, 6),
    (10, 60, 6),
    (8,  55, 6),
    (8,  50, 6),
    (6,  45, 6),
    (6,  40, 6),
]


def _target_fps(info: MediaInfo) -> int:
    """Cap source FPS at MAX_WEBP_FPS."""
    return min(int(info.fps or cfg.WEBP_FPS), cfg.MAX_WEBP_FPS)


# ── Per-strategy encode functions (accept fps/quality/compression) ─────────────

async def _encode_alpha(source: str, out: str, fps: int, quality: int, comp: int) -> bool:
    fc = (
        f"[0:v]fps={fps},"
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
        f"format=rgba[v]"
    )
    try:
        await encode_animated_webp(EncodeOptions(
            input_file=source, output_path=out,
            fps=fps, quality=quality,
            filter_complex=fc,
            extra_output_args=["-map", "[v]", "-compression_level", str(comp)],
        ))
        return True
    except Exception as e:
        log.debug(f"alpha encode error: {e}")
        return False


async def _encode_rgba(source: str, out: str, fps: int, quality: int, comp: int) -> bool:
    fc = (
        f"[0:v]fps={fps},"
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
        f"format=yuva420p[v]"
    )
    try:
        await encode_animated_webp(EncodeOptions(
            input_file=source, output_path=out,
            fps=fps, quality=quality,
            filter_complex=fc,
            extra_output_args=["-map", "[v]", "-pix_fmt", "yuva420p", "-compression_level", str(comp)],
        ))
        return True
    except Exception as e:
        log.debug(f"rgba encode error: {e}")
        return False


async def _encode_flatten(source: str, out: str, fps: int, quality: int, comp: int) -> bool:
    try:
        await encode_animated_webp(EncodeOptions(
            input_file=source, output_path=out,
            fps=fps, quality=quality,
            extra_output_args=["-compression_level", str(comp)],
        ))
        return True
    except Exception as e:
        log.debug(f"flatten encode error: {e}")
        return False


_STRATEGIES = [
    (ConversionStrategy.ALPHA_PRESERVE, _encode_alpha),
    (ConversionStrategy.RGBA_NORMALIZE, _encode_rgba),
    (ConversionStrategy.FLATTEN_BG,     _encode_flatten),
]


async def _try_encode_with_size_reduction(
    source: str,
    out: str,
    info: MediaInfo,
    encode_fn,
    strategy_name: str,
) -> bool:
    """
    Try encoding with progressively lower FPS/quality until the file fits
    within MAX_OUTPUT_SIZE. Returns True if a valid, small-enough file was produced.
    """
    base_fps = _target_fps(info)

    # Build ladder: start with base settings, then work down
    ladder = [(base_fps, cfg.WEBP_QUALITY, 6)] + [
        (min(fps, base_fps), q, c) for fps, q, c in _SIZE_LADDER
    ]
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for entry in ladder:
        if entry not in seen:
            seen.add(entry)
            deduped.append(entry)

    for fps, quality, comp in deduped:
        if os.path.exists(out):
            os.unlink(out)

        ok = await encode_fn(source, out, fps, quality, comp)
        if not ok:
            return False  # encode itself failed — no point retrying this strategy

        result = validate_webp(out)
        if result.valid:
            log.debug(f"{strategy_name} succeeded at fps={fps} q={quality}")
            return True

        if result.reason == "file_too_large":
            file_size = os.path.getsize(out) if os.path.exists(out) else 0
            log.debug(
                f"{strategy_name} file_too_large at fps={fps} q={quality} "
                f"({file_size // 1024}KB > {cfg.MAX_OUTPUT_SIZE // 1024}KB) — reducing"
            )
            continue  # try next ladder rung

        # Any other validation failure — stop trying this strategy
        log.warning(f"{strategy_name} produced invalid output: {result.reason}")
        return False

    log.warning(f"{strategy_name} still too large after full size ladder")
    return False


# ── Main converter ────────────────────────────────────────────────────────────

async def convert_webm(source_path: str, output_path: str, job_id: str = "") -> ConversionResult:
    start = time.monotonic()
    logger = log.getChild(job_id) if job_id else log

    # Step 1 – inspect
    try:
        info = await inspect_media(source_path)
        logger.debug(
            f"Inspected: codec={info.codec} {info.width}x{info.height} "
            f"fps={info.fps:.1f} duration={info.duration} alpha={info.has_alpha}"
        )
    except Exception as e:
        return ConversionResult(
            success=False, reason=f"ffprobe_error: {e}",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    # Step 2 – duration guard
    if info.duration and info.duration > cfg.MAX_VIDEO_DURATION:
        return ConversionResult(
            success=False,
            reason=f"video_too_long: {info.duration:.1f}s",
            duration_ms=(time.monotonic() - start) * 1000,
        )

    # Step 3 – try each strategy, each with its own size-reduction ladder
    for strategy, encode_fn in _STRATEGIES:
        if os.path.exists(output_path):
            os.unlink(output_path)

        logger.debug(f"Trying strategy: {strategy.value}")
        success = await _try_encode_with_size_reduction(
            source_path, output_path, info, encode_fn, strategy.value
        )

        if success:
            logger.debug(f"Strategy {strategy.value} succeeded")
            return ConversionResult(
                success=True,
                output_path=output_path,
                strategy=strategy,
                duration_ms=(time.monotonic() - start) * 1000,
            )

    return ConversionResult(
        success=False,
        reason="all_strategies_failed",
        duration_ms=(time.monotonic() - start) * 1000,
    )
