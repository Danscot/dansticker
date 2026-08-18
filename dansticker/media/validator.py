"""Validate converted WebP stickers using Pillow."""
from __future__ import annotations
import os
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from dansticker.config import cfg
from dansticker.logger import get_logger
from dansticker.types import ValidationResult

log = get_logger("media.validator")

W = cfg.TARGET_WIDTH
H = cfg.TARGET_HEIGHT


def validate_webp(file_path: str) -> ValidationResult:
    """Synchronous WebP validation — runs in a thread pool."""
    # 1. File exists
    if not os.path.exists(file_path):
        return ValidationResult(valid=False, reason="file_not_found")

    file_size = os.path.getsize(file_path)

    # 2. Not empty
    if file_size == 0:
        return ValidationResult(valid=False, reason="empty_file")

    # 3. Size limit
    if file_size > cfg.MAX_OUTPUT_SIZE:
        return ValidationResult(valid=False, reason="file_too_large", file_size=file_size)

    try:
        img = Image.open(file_path)

        # 4. Format must be WebP
        if img.format != "WEBP":
            return ValidationResult(valid=False, reason="not_webp")

        # 5. Dimensions
        if img.width != W or img.height != H:
            return ValidationResult(
                valid=False,
                reason="wrong_dimensions",
                width=img.width,
                height=img.height,
            )

        # 6. Check if animated
        animated = hasattr(img, "n_frames") and img.n_frames > 1
        frame_count = getattr(img, "n_frames", 1)

        if animated:
            if frame_count < 2:
                return ValidationResult(valid=False, reason="zero_frame_animation", frame_count=frame_count)

            # 7. Decode all frames to catch corruption
            try:
                for frame_idx in range(frame_count):
                    img.seek(frame_idx)
                    img.load()
            except EOFError:
                pass  # Normal end of frames
            except Exception as e:
                return ValidationResult(valid=False, reason=f"corrupt_frame: {e}")

        else:
            # 8. Static — just decode
            img.load()

        return ValidationResult(
            valid=True,
            width=img.width,
            height=img.height,
            animated=animated,
            frame_count=frame_count,
            file_size=file_size,
        )

    except UnidentifiedImageError:
        return ValidationResult(valid=False, reason="unidentified_image")
    except Exception as e:
        log.warning(f"Validation exception for {Path(file_path).name}: {e}")
        return ValidationResult(valid=False, reason=f"validation_exception: {e}")
