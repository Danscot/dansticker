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
    2. Separate static and animated stickers into different packs.
    3. Each group is chunked at MAX_STICKERS_PER_PACK.

    The WhatsAppPack.name is ALWAYS the clean user-chosen name — no suffixes.
    Part/type info lives only in the filename (handled by the builder).
    """
    max_s = cfg.MAX_STICKERS_PER_PACK

    successful = [
        s for s in pack.stickers
        if s.status == StickerStatus.SUCCESS and s.output_path
    ]

    static   = [s for s in successful if not s.animated]
    animated = [s for s in successful if s.animated]

    result: List[WhatsAppPack] = []
    has_both = bool(static) and bool(animated)

    def _add_group(stickers: List[Sticker], group: str) -> None:
        """group is 'static' | 'animated' | '' — used only for filename, not display name."""
        chunks = _chunks(stickers, max_s)
        for i, chunk in enumerate(chunks):
            result.append(WhatsAppPack(
                name=pack.name,          # always clean — no Part X, no Static/Animated
                author=pack.author,
                stickers=chunk,
                source_url=pack.telegram_url,
                thumbnail_path=pack.thumbnail_path,
                # store metadata for builder to use in the filename only
                _group=group,
                _chunk_index=i,
                _chunk_total=len(chunks),
            ))

    if static:
        _add_group(static, "static" if has_both else "")
    if animated:
        _add_group(animated, "animated" if has_both else "")

    # Assign overall part numbers
    total = len(result)
    for i, p in enumerate(result):
        p.part_index = i + 1
        p.total_parts = total

    return result
