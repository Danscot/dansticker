import pytest
from PIL import Image
from dansticker.media.static_webp import convert_static_webp


def make_source(path: str, w=300, h=400, transparent=True) -> None:
    mode = "RGBA" if transparent else "RGB"
    img = Image.new(mode, (w, h), (100, 200, 50, 180) if transparent else (100, 200, 50))
    img.save(path, format="WEBP")


def test_converts_to_512x512(tmp_path):
    src = str(tmp_path / "src.webp")
    out = str(tmp_path / "out.webp")
    make_source(src)
    result = convert_static_webp(src, out)
    assert result.success
    img = Image.open(out)
    assert img.width == 512
    assert img.height == 512


def test_preserves_rgba(tmp_path):
    src = str(tmp_path / "src.webp")
    out = str(tmp_path / "out.webp")
    make_source(src, transparent=True)
    result = convert_static_webp(src, out)
    assert result.success
    img = Image.open(out).convert("RGBA")
    assert img.mode == "RGBA"


def test_non_square_input(tmp_path):
    """Landscape input should be padded, not stretched."""
    src = str(tmp_path / "landscape.webp")
    out = str(tmp_path / "out.webp")
    Image.new("RGBA", (800, 400), (255, 0, 0, 255)).save(src, format="WEBP")
    result = convert_static_webp(src, out)
    assert result.success
    img = Image.open(out)
    assert img.width == 512
    assert img.height == 512


def test_bad_source(tmp_path):
    out = str(tmp_path / "out.webp")
    result = convert_static_webp("/nonexistent/source.webp", out)
    assert not result.success
