"""Single entry-point for all FFmpeg animation encoding."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from dansticker.config import cfg
from dansticker.logger import get_logger

log = get_logger("media.animation")

W = cfg.TARGET_WIDTH
H = cfg.TARGET_HEIGHT


@dataclass
class EncodeOptions:
    output_path: str
    input_file: Optional[str] = None          # video file input
    input_pattern: Optional[str] = None       # frame glob e.g. frame_%04d.png
    width: int = W
    height: int = H
    fps: int = cfg.WEBP_FPS
    quality: int = cfg.WEBP_QUALITY
    loop: int = 0                             # 0 = infinite
    filter_complex: Optional[str] = None      # override vf filter
    extra_input_args: List[str] = field(default_factory=list)
    extra_output_args: List[str] = field(default_factory=list)


async def encode_animated_webp(opts: EncodeOptions) -> None:
    """Encode frames or a video file to animated WebP via FFmpeg."""
    Path(opts.output_path).parent.mkdir(parents=True, exist_ok=True)

    args = [cfg.FFMPEG_PATH, "-y"]

    # ── Input ──────────────────────────────────────────────────────────────
    if opts.input_file:
        args += opts.extra_input_args + ["-i", opts.input_file]
    elif opts.input_pattern:
        args += ["-framerate", str(opts.fps)] + opts.extra_input_args + ["-i", opts.input_pattern]
    else:
        raise ValueError("encode_animated_webp: must supply input_file or input_pattern")

    # ── Filter ─────────────────────────────────────────────────────────────
    if opts.filter_complex:
        args += ["-filter_complex", opts.filter_complex]
    else:
        scale = (
            f"scale={opts.width}:{opts.height}:force_original_aspect_ratio=decrease,"
            f"pad={opts.width}:{opts.height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
            f"fps={opts.fps}"
        )
        args += ["-vf", scale]

    # ── Output ─────────────────────────────────────────────────────────────
    args += [
        "-vcodec", "libwebp",
        "-loop", str(opts.loop),
        "-preset", "default",
        "-q:v", str(opts.quality),
        "-compression_level", "6",
        "-an",                        # strip audio
    ] + opts.extra_output_args + [opts.output_path]

    log.debug(f"FFmpeg: {' '.join(args)}")

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=cfg.MAX_FFMPEG_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError("FFmpeg encode timed out")

    if proc.returncode != 0:
        snippet = stderr.decode(errors="replace")[-500:]
        raise RuntimeError(f"FFmpeg exited with code {proc.returncode}: {snippet}")


async def extract_frames(input_path: str, frames_dir: str, fps: int) -> int:
    """Extract video frames as PNG files; returns the frame count."""
    Path(frames_dir).mkdir(parents=True, exist_ok=True)
    pattern = str(Path(frames_dir) / "frame_%04d.png")

    args = [
        cfg.FFMPEG_PATH, "-y",
        "-i", input_path,
        "-vf", f"fps={fps}",
        "-vsync", "vfr",
        pattern,
    ]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        await asyncio.wait_for(proc.communicate(), timeout=cfg.MAX_FFMPEG_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise RuntimeError("Frame extraction timed out")

    frames = sorted(Path(frames_dir).glob("frame_*.png"))
    return len(frames)
