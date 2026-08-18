"""FFprobe-based media inspector."""
from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from dansticker.config import cfg
from dansticker.logger import get_logger
from dansticker.types import MediaInfo

log = get_logger("media.inspector")


def _parse_fps(fps_str: Optional[str]) -> Optional[float]:
    if not fps_str:
        return None
    if "/" in fps_str:
        parts = fps_str.split("/")
        try:
            num, den = float(parts[0]), float(parts[1])
            return num / den if den != 0 else None
        except ValueError:
            return None
    try:
        return float(fps_str)
    except ValueError:
        return None


async def inspect_media(file_path: str) -> MediaInfo:
    """Run ffprobe on a file and return MediaInfo."""
    file_size = os.path.getsize(file_path)

    cmd = [
        cfg.FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        file_path,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        log.warning(f"ffprobe timed out for {file_path}")
        return MediaInfo(file_size=file_size)
    except Exception as e:
        log.warning(f"ffprobe error for {file_path}: {e}")
        return MediaInfo(file_size=file_size)

    if proc.returncode != 0:
        log.warning(f"ffprobe returned {proc.returncode} for {file_path}")
        return MediaInfo(file_size=file_size)

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return MediaInfo(file_size=file_size)

    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})

    fps = _parse_fps(video_stream.get("avg_frame_rate")) or _parse_fps(video_stream.get("r_frame_rate")) if video_stream else None
    pix_fmt = video_stream.get("pix_fmt", "") if video_stream else ""
    has_alpha = any(x in pix_fmt for x in ("a", "rgba", "yuva"))

    nb_frames = None
    if video_stream and video_stream.get("nb_frames"):
        try:
            nb_frames = int(video_stream["nb_frames"])
        except (ValueError, TypeError):
            pass

    duration = None
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except (ValueError, TypeError):
            pass

    return MediaInfo(
        file_size=file_size,
        codec=video_stream.get("codec_name") if video_stream else None,
        width=video_stream.get("width") if video_stream else None,
        height=video_stream.get("height") if video_stream else None,
        duration=duration,
        fps=fps,
        pixel_format=pix_fmt or None,
        has_alpha=has_alpha,
        has_audio=audio_stream is not None,
        frame_count=nb_frames,
    )
