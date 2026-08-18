import pytest
from dansticker.pack.metadata import build_info_json
from dansticker.types import WhatsAppPack, Sticker, StickerSourceType, StickerStatus


def make_wa_pack(animated=False) -> WhatsAppPack:
    stickers = [
        Sticker(index=0, file_id="f1", source_type=StickerSourceType.WEBP,
                emoji="😂", animated=animated, status=StickerStatus.SUCCESS,
                output_path="/fake/s1.webp"),
        Sticker(index=1, file_id="f2", source_type=StickerSourceType.WEBP,
                emoji="🐱", animated=animated, status=StickerStatus.SUCCESS,
                output_path="/fake/s2.webp"),
    ]
    return WhatsAppPack(
        name="Funny Cats", author="Dansticker",
        stickers=stickers,
        source_url="https://t.me/addstickers/FunnyCats",
    )


def test_structure():
    info = build_info_json(make_wa_pack(), "test-id")
    assert "sticker_packs" in info
    assert len(info["sticker_packs"]) == 1


def test_pack_fields():
    pack = build_info_json(make_wa_pack(), "test-id")["sticker_packs"][0]
    assert pack["name"] == "Funny Cats"
    assert pack["publisher"] == "Dansticker"
    assert pack["identifier"] == "test-id"
    assert pack["tray_image_file"] == "thumbnail.png"


def test_sticker_filenames():
    stickers = build_info_json(make_wa_pack(), "x")["sticker_packs"][0]["stickers"]
    assert stickers[0]["image_file"] == "sticker_001.webp"
    assert stickers[1]["image_file"] == "sticker_002.webp"


def test_emoji_preserved():
    stickers = build_info_json(make_wa_pack(), "x")["sticker_packs"][0]["stickers"]
    assert "😂" in stickers[0]["emojis"]
    assert "🐱" in stickers[1]["emojis"]


def test_animated_flag_false():
    info = build_info_json(make_wa_pack(animated=False), "x")
    assert info["sticker_packs"][0]["animated_sticker_pack"] is False


def test_animated_flag_true():
    info = build_info_json(make_wa_pack(animated=True), "x")
    assert info["sticker_packs"][0]["animated_sticker_pack"] is True


def test_publisher_website():
    info = build_info_json(make_wa_pack(), "x")
    assert "FunnyCats" in info["sticker_packs"][0]["publisher_website"]
