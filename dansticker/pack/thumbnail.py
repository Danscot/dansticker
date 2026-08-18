"""Generate 96×96 PNG thumbnails."""
from __future__ import annotations
from pathlib import Path

from PIL import Image

from dansticker.config import cfg
from dansticker.logger import get_logger

log = get_logger("pack.thumbnail")

TW, TH = cfg.THUMBNAIL_WIDTH, cfg.THUMBNAIL_HEIGHT


def generate_thumbnail(source_path: str, output_path: str) -> str:
    """Generate a 96×96 PNG thumbnail from any WebP or PNG source."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        img = Image.open(source_path)

        # Use first frame for animated images
        if hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(0)

        img = img.convert("RGBA")
        img.thumbnail((TW, TH), Image.LANCZOS)

        # Compose on white background (PNG thumbnails should be opaque)
        canvas = Image.new("RGB", (TW, TH), (255, 255, 255))
        x = (TW - img.width) // 2
        y = (TH - img.height) // 2
        canvas.paste(img, (x, y), mask=img)
        canvas.save(output_path, format="PNG")

        log.debug(f"Thumbnail saved: {output_path}")
        return output_path

    except Exception as e:
        log.warning(f"Thumbnail generation failed ({e}), using white placeholder")
        canvas = Image.new("RGB", (TW, TH), (255, 255, 255))
        canvas.save(output_path, format="PNG")
        return output_path
