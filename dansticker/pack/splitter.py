"""Split a converted StickerPack into WhatsApp-compatible WhatsAppPack list."""
from __future__ import annotations
from typing import List

from dansticker.config import cfg
from dansticker.types import StickerPack, WhatsAppPack, Sticker, StickerStatus


def _chunks(lst: List[Sticker], size: int) -> List[List[Sticker]]:
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def split_into_wa_packs(pack: StickerPack) -> List[WhatsAppPack]:
    """
    Rules:
    1. Only include stickers with status=SUCCESS and an output_path.
    2. Separate static and animated stickers.
    3. Each group is chunked at MAX_STICKERS_PER_PACK.
    """
    max_s = cfg.MAX_STICKERS_PER_PACK

    successful = [
        s for s in pack.stickers
        if s.status == StickerStatus.SUCCESS and s.output_path
    ]

    static   = [s for s in successful if not s.animated]
    animated = [s for s in successful if s.animated]

    result: List[WhatsAppPack] = []

    def _add_group(stickers: List[Sticker], label: str) -> None:
        chunks = _chunks(stickers, max_s)
        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                name = f"{pack.name} — {label} Part {i + 1}"
            elif label:
                name = f"{pack.name} — {label}"
            else:
                name = pack.name

            result.append(WhatsAppPack(
                name=name,
                author=pack.author,
                stickers=chunk,
                source_url=pack.telegram_url,
                thumbnail_path=pack.thumbnail_path,
            ))

    has_both = bool(static) and bool(animated)

    if static:
        _add_group(static, "Static" if has_both else "")
    if animated:
        _add_group(animated, "Animated" if has_both else "")

    # Assign part numbers
    total = len(result)
    for i, p in enumerate(result):
        p.part_index = i + 1
        p.total_parts = total

    return result
