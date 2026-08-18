"""Convert TGS (Telegram animated sticker / Lottie) to animated WebP."""
from __future__ import annotations
import asyncio
import gzip
import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from dansticker.config import cfg
from dansticker.logger import get_logger
from dansticker.media.animation import encode_animated_webp, EncodeOptions
from dansticker.media.validator import validate_webp
from dansticker.types import ConversionResult, ConversionStrategy

log = get_logger("media.tgs")

W, H = cfg.TARGET_WIDTH, cfg.TARGET_HEIGHT


def decompress_tgs(tgs_path: str) -> dict:
    """Gunzip a .tgs file and return parsed Lottie JSON."""
    with gzip.open(tgs_path, "rb") as f:
        return json.loads(f.read())


async def _render_via_lottie_lib(lottie_data: dict, frames_dir: str, fps: int) -> int:
    """
    Render Lottie JSON to PNG frames using the `lottie` Python library.
    Returns number of frames rendered, or 0 on failure.
    """
    script = f"""
import sys, json
from pathlib import Path

try:
    import lottie
    from lottie.parsers.baseparser import baseparser
    from lottie import exporters, parsers

    data = {json.dumps(lottie_data)}
    anim = parsers.parse(data)

    fps = {fps}
    in_point  = anim.in_point  if hasattr(anim, "in_point")  else 0
    out_point = anim.out_point if hasattr(anim, "out_point") else fps
    frame_count = int(out_point - in_point)

    if frame_count < 1:
        print(0)
        sys.exit(0)

    exporter = exporters.get("png")
    frames_dir = Path("{frames_dir}")
    frames_dir.mkdir(parents=True, exist_ok=True)

    for i in range(frame_count):
        frame = in_point + i
        out = frames_dir / f"frame_{{i+1:04d}}.png"
        exporter.save(anim, str(out), frame=frame)

    print(frame_count)
except Exception as e:
    sys.stderr.write(str(e) + "\\n")
    print(0)
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if stderr:
            log.debug(f"lottie render stderr: {stderr.decode(errors='replace')[:300]}")
        count = int(stdout.decode().strip() or "0")
        return max(count, 0)
    except asyncio.TimeoutError:
        log.warning("Lottie render timed out")
        return 0
    except Exception as e:
        log.warning(f"Lottie render error: {e}")
        return 0


async def _render_via_rlottie(tgs_path: str, frames_dir: str, fps: int) -> int:
    """
    Fallback: render TGS via rlottie Python bindings if installed.
    Returns frame count or 0.
    """
    script = f"""
import sys
try:
    import rlottie_python as rlottie
    from pathlib import Path

    anim = rlottie.LottieAnimation.from_tgs("{tgs_path}")
    width, height = {W}, {H}
    frame_count = anim.lottie_animation_get_totalframe()
    fps = {fps}
    frames_dir = Path("{frames_dir}")
    frames_dir.mkdir(parents=True, exist_ok=True)

    for i in range(frame_count):
        frame_data = anim.lottie_animation_render(i, width, height)
        from PIL import Image
        img = Image.frombytes("RGBA", (width, height), bytes(frame_data))
        img.save(frames_dir / f"frame_{{i+1:04d}}.png")

    print(frame_count)
except Exception as e:
    sys.stderr.write(str(e) + "\\n")
    print(0)
"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if stderr:
            log.debug(f"rlottie stderr: {stderr.decode(errors='replace')[:200]}")
        return max(int(stdout.decode().strip() or "0"), 0)
    except Exception as e:
        log.debug(f"rlottie unavailable: {e}")
        return 0


async def _ffmpeg_tgs_fallback(tgs_path: str, output_path: str, fps: int) -> bool:
    """
    Last resort: try FFmpeg directly on the .tgs file.
    Works if FFmpeg is built with rlottie support.
    """
    scale = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
        f"fps={fps}"
    )
    args = [
        cfg.FFMPEG_PATH, "-y",
        "-i", tgs_path,
        "-vf", scale,
        "-vcodec", "libwebp",
        "-loop", "0",
        "-q:v", str(cfg.WEBP_QUALITY),
        "-an",
        output_path,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            log.debug(f"FFmpeg TGS fallback failed: {stderr.decode(errors='replace')[-200:]}")
            return False
        return True
    except Exception as e:
        log.debug(f"FFmpeg TGS fallback error: {e}")
        return False


async def convert_tgs(source_path: str, output_path: str, job_id: str = "") -> ConversionResult:
    start = time.monotonic()
    frames_dir = str(Path(output_path).parent / f"tgs_frames_{Path(source_path).stem}")

    try:
        # Step 1 – decompress
        try:
            lottie_data = decompress_tgs(source_path)
        except Exception as e:
            return ConversionResult(
                success=False,
                reason=f"tgs_decompress_error: {e}",
                duration_ms=(time.monotonic() - start) * 1000,
            )

        lottie_fps = lottie_data.get("fr", cfg.WEBP_FPS)
        fps = min(int(lottie_fps), cfg.MAX_WEBP_FPS)

        # Step 2 – render frames (try lottie lib, then rlottie)
        frame_count = await _render_via_lottie_lib(lottie_data, frames_dir, fps)

        if frame_count < 1:
            log.debug(f"[{job_id}] lottie lib failed, trying rlottie")
            frame_count = await _render_via_rlottie(source_path, frames_dir, fps)

        if frame_count >= 1:
            # Step 3 – encode PNG frames → animated WebP
            pattern = str(Path(frames_dir) / "frame_%04d.png")
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            await encode_animated_webp(EncodeOptions(
                input_pattern=pattern,
                output_path=output_path,
                fps=fps,
            ))
        else:
            # Step 4 – FFmpeg direct fallback
            log.debug(f"[{job_id}] frame render failed, trying FFmpeg TGS fallback")
            ok = await _ffmpeg_tgs_fallback(source_path, output_path, fps)
            if not ok:
                return ConversionResult(
                    success=False,
                    reason="tgs_all_renderers_failed",
                    duration_ms=(time.monotonic() - start) * 1000,
                )

        # Step 5 – validate
        result = validate_webp(output_path)
        duration_ms = (time.monotonic() - start) * 1000

        if not result.valid:
            return ConversionResult(success=False, reason=f"tgs_validation_failed: {result.reason}",
                                    duration_ms=duration_ms)

        return ConversionResult(
            success=True,
            output_path=output_path,
            strategy=ConversionStrategy.TGS_RENDER,
            duration_ms=duration_ms,
        )

    finally:
        # Clean up frames directory
        if os.path.exists(frames_dir):
            shutil.rmtree(frames_dir, ignore_errors=True)
