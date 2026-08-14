"""Build .wastickers ZIP archives from validated WhatsApp packs."""
from __future__ import annotations
import json
import os
import re
import shutil
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dansticker.logger import get_logger
from dansticker.pack.metadata import build_info_json
from dansticker.pack.thumbnail import generate_thumbnail
from dansticker.types import WhatsAppPack

log = get_logger("pack.builder")

_thumb_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="thumbnail")


@dataclass
class BuildResult:
    success: bool
    output_path: Optional[str] = None
    reason: Optional[str] = None


def _safe(text: str) -> str:
    """Filesystem-safe slug from arbitrary text."""
    clean = re.sub(r"[^\w\s\-]", "", text).strip()
    return re.sub(r"\s+", "_", clean)[:48] or "pack"


def _build_filename(pack: WhatsAppPack) -> str:
    """
    Construct a descriptive filename without touching the display name.

    Examples:
      FunnyCats.wastickers
      FunnyCats_static.wastickers
      FunnyCats_animated.wastickers
      FunnyCats_static_part2.wastickers
      FunnyCats_animated_part1.wastickers
    """
    parts = [_safe(pack.name)]

    if pack._group:
        parts.append(pack._group)

    if pack._chunk_total > 1:
        parts.append(f"part{pack._chunk_index + 1}")

    return "_".join(parts) + ".wastickers"


def build_wastickers(pack: WhatsAppPack, output_dir: str, pack_dir: str) -> BuildResult:
    """
    Build a .wastickers file (synchronous — call from thread pool).

    ZIP contents (all at root level):
        thumbnail.png
        sticker_001.webp  …
        title.txt         ← clean pack name, no suffixes
        author.txt
        link.txt
        info.json
    """
    output_dir_p = Path(output_dir)
    pack_dir_p = Path(pack_dir)
    output_dir_p.mkdir(parents=True, exist_ok=True)
    pack_dir_p.mkdir(parents=True, exist_ok=True)

    filename = _build_filename(pack)
    output_path = str(output_dir_p / filename)

    try:
        # 1 – Thumbnail
        thumb_dest = str(pack_dir_p / "thumbnail.png")
        thumb_source = pack.thumbnail_path or (
            pack.stickers[0].output_path if pack.stickers else None
        )
        if thumb_source and os.path.exists(thumb_source):
            generate_thumbnail(thumb_source, thumb_dest)
        else:
            from PIL import Image
            Image.new("RGB", (96, 96), (255, 255, 255)).save(thumb_dest, "PNG")

        # 2 – Stickers (sequential names)
        for i, sticker in enumerate(pack.stickers):
            if not sticker.output_path or not os.path.exists(sticker.output_path):
                log.warning(f"Sticker {sticker.index} missing output, skipping")
                continue
            shutil.copy2(sticker.output_path, pack_dir_p / f"sticker_{i + 1:03d}.webp")

        # 3 – Metadata — always the clean name, never the filename
        (pack_dir_p / "title.txt").write_text(pack.name, encoding="utf-8")
        (pack_dir_p / "author.txt").write_text(pack.author, encoding="utf-8")
        (pack_dir_p / "link.txt").write_text(pack.source_url, encoding="utf-8")

        # 4 – info.json
        identifier = str(uuid.uuid4())
        info = build_info_json(pack, identifier)
        (pack_dir_p / "info.json").write_text(
            json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 5 – ZIP → .wastickers
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for item in sorted(pack_dir_p.iterdir()):
                if item.is_file():
                    zf.write(item, arcname=item.name)

        # 6 – Sanity check
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            return BuildResult(success=False, reason="zip_too_small_or_missing")

        size_kb = os.path.getsize(output_path) / 1024
        log.info(f"Built: {filename} ({size_kb:.1f} KB, {len(pack.stickers)} stickers)")
        return BuildResult(success=True, output_path=output_path)

    except Exception as e:
        log.error(f"Pack build error: {e}")
        return BuildResult(success=False, reason=f"build_error: {e}")
