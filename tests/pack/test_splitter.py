import pytest
from dansticker.pack.splitter import split_into_wa_packs
from dansticker.pack.builder import _build_filename
from dansticker.types import StickerPack, Sticker, StickerSourceType, StickerStatus, PackType


def make_pack(stickers_spec) -> StickerPack:
    stickers = []
    for i, spec in enumerate(stickers_spec):
        stickers.append(Sticker(
            index=i,
            file_id=f"f{i}",
            source_type=StickerSourceType.WEBP,
            emoji="😀",
            animated=spec.get("animated", False),
            status=spec.get("status", StickerStatus.SUCCESS),
            output_path=spec.get("output", f"/fake/s{i}.webp"),
        ))
    return StickerPack(
        id="test", telegram_url="https://t.me/addstickers/Test",
        telegram_name="Test", name="Test Pack", author="Dansticker",
        stickers=stickers,
    )


def test_small_pack_single_result():
    pack = make_pack([{}] * 10)
    result = split_into_wa_packs(pack)
    assert len(result) == 1
    assert len(result[0].stickers) == 10


def test_splits_at_30():
    pack = make_pack([{}] * 47)
    result = split_into_wa_packs(pack)
    assert len(result) == 2
    assert len(result[0].stickers) == 30
    assert len(result[1].stickers) == 17


def test_separates_static_animated():
    specs = [{"animated": False}] * 5 + [{"animated": True}] * 5
    pack = make_pack(specs)
    result = split_into_wa_packs(pack)
    assert len(result) == 2
    assert all(not s.animated for s in result[0].stickers)
    assert all(s.animated for s in result[1].stickers)


def test_excludes_failed():
    specs = [
        {"status": StickerStatus.SUCCESS, "output": "/f/s0.webp"},
        {"status": StickerStatus.FAILED,  "output": None},
        {"status": StickerStatus.SUCCESS, "output": "/f/s2.webp"},
    ]
    pack = make_pack(specs)
    result = split_into_wa_packs(pack)
    assert len(result[0].stickers) == 2


def test_part_numbers():
    pack = make_pack([{}] * 47)
    result = split_into_wa_packs(pack)
    assert result[0].part_index == 1
    assert result[1].part_index == 2
    assert result[0].total_parts == 2


def test_display_name_never_has_suffix():
    """Pack name shown to user must always be clean — no Part/Static/Animated."""
    pack = make_pack([{}] * 47)
    for wa_pack in split_into_wa_packs(pack):
        assert "Part" not in wa_pack.name
        assert "Static" not in wa_pack.name
        assert "Animated" not in wa_pack.name
        assert wa_pack.name == "Test Pack"


def test_filename_has_part_suffix():
    """Filename (not display name) carries the part/chunk info."""
    pack = make_pack([{}] * 47)
    result = split_into_wa_packs(pack)
    fn0 = _build_filename(result[0])
    fn1 = _build_filename(result[1])
    assert "part1" in fn0
    assert "part2" in fn1
    assert fn0.endswith(".wastickers")
    assert fn1.endswith(".wastickers")


def test_mixed_pack_filenames_have_type():
    """Static/animated groups get type label in filename when both exist."""
    specs = [{"animated": False}] * 5 + [{"animated": True}] * 5
    pack = make_pack(specs)
    result = split_into_wa_packs(pack)
    filenames = [_build_filename(p) for p in result]
    assert any("static" in fn for fn in filenames)
    assert any("animated" in fn for fn in filenames)


def test_empty_pack():
    pack = make_pack([])
    result = split_into_wa_packs(pack)
    assert result == []
