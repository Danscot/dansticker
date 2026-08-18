"""Build info.json for .wastickers packages."""
from __future__ import annotations
from typing import List

from dansticker.types import WhatsAppPack


def build_info_json(pack: WhatsAppPack, identifier: str) -> dict:
    """Return the info.json dict matching the WhatsApp sticker pack format."""
    animated = any(s.animated for s in pack.stickers)

    sticker_entries = [
        {
            "image_file": f"sticker_{i + 1:03d}.webp",
            "emojis": [s.emoji or "🎉"],
        }
        for i, s in enumerate(pack.stickers)
    ]

    return {
        "android_play_store_link": "",
        "ios_app_store_link": "",
        "publisher_website": pack.source_url,
        "privacy_policy_website": "",
        "license_agreement_website": "",
        "image_data_version": "1",
        "avoid_cache": False,
        "sticker_packs": [
            {
                "identifier": identifier,
                "name": pack.name,
                "publisher": pack.author,
                "tray_image_file": "thumbnail.png",
                "publisher_email": "",
                "publisher_website": pack.source_url,
                "privacy_policy_website": "",
                "license_agreement_website": "",
                "image_data_version": "1",
                "avoid_cache": False,
                "animated_sticker_pack": animated,
                "stickers": sticker_entries,
            }
        ],
    }
