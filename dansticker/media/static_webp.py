"""Convert static WebP stickers to 512x512 RGBA WebP."""
from __future__ import annotations
import time
from pathlib import Path

from PIL import Image

from dansticker.config import cfg
from dansticker.logger import get_logger
from dansticker.media.validator import validate_webp
from dansticker.types import ConversionResult, ConversionStrategy

log = get_logger("media.static_webp")

W, H = cfg.TARGET_WIDTH, cfg.TARGET_HEIGHT
Q = cfg.WEBP_QUALITY


def convert_static_webp(source_path: str, output_path: str) -> ConversionResult:
    """Normalize a static WebP to 512×512 RGBA WebP (runs in thread pool)."""
    start = time.monotonic()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        img = Image.open(source_path).convert("RGBA")

        # Fit into 512×512, preserve aspect ratio, pad with transparency
        img.thumbnail((W, H), Image.LANCZOS)

        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        x = (W - img.width) // 2
        y = (H - img.height) // 2
        canvas.paste(img, (x, y), mask=img)

        canvas.save(output_path, format="WEBP", quality=Q, method=6)

        result = validate_webp(output_path)
        duration_ms = (time.monotonic() - start) * 1000

        if not result.valid:
            return ConversionResult(success=False, reason=result.reason, duration_ms=duration_ms)

        return ConversionResult(
            success=True,
            output_path=output_path,
            strategy=ConversionStrategy.ALPHA_PRESERVE,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        log.warning(f"Static WebP conversion error: {e}")
        return ConversionResult(success=False, reason=f"static_webp_error: {e}", duration_ms=duration_ms)
