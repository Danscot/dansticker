import os
import pytest
from PIL import Image
from dansticker.media.validator import validate_webp


def make_static_webp(path: str, w=512, h=512) -> None:
    Image.new("RGBA", (w, h), (0, 255, 0, 200)).save(path, format="WEBP")


def make_animated_webp(path: str, w=512, h=512, n_frames=3) -> None:
    """Create a genuine animated WebP using WebP save_all."""
    frames = [Image.new("RGBA", (w, h), (i * 40, 100, 200, 200)) for i in range(n_frames)]
    frames[0].save(
        path, format="WEBP", save_all=True,
        append_images=frames[1:], loop=0, duration=100,
        minimize_size=False,
    )
    # Verify Pillow actually wrote multiple frames
    check = Image.open(path)
    assert getattr(check, "n_frames", 1) >= 2, "Pillow failed to write animated WebP in this environment"


def test_valid_static(tmp_path):
    p = str(tmp_path / "s.webp")
    make_static_webp(p)
    r = validate_webp(p)
    assert r.valid
    assert r.width == 512
    assert r.height == 512
    assert r.animated is False


def test_valid_animated(tmp_path):
    p = str(tmp_path / "a.webp")
    try:
        make_animated_webp(p)
    except AssertionError:
        pytest.skip("Pillow on this platform cannot write multi-frame WebP")
    r = validate_webp(p)
    assert r.valid
    assert r.animated is True
    assert r.frame_count >= 2


def test_wrong_dimensions(tmp_path):
    p = str(tmp_path / "small.webp")
    Image.new("RGBA", (256, 256)).save(p, format="WEBP")
    r = validate_webp(p)
    assert not r.valid
    assert r.reason == "wrong_dimensions"


def test_file_not_found():
    r = validate_webp("/nonexistent/file.webp")
    assert not r.valid
    assert r.reason == "file_not_found"


def test_empty_file(tmp_path):
    p = str(tmp_path / "empty.webp")
    open(p, "wb").close()
    r = validate_webp(p)
    assert not r.valid
    assert r.reason == "empty_file"


def test_non_webp(tmp_path):
    p = str(tmp_path / "img.png")
    Image.new("RGB", (512, 512)).save(p, format="PNG")
    r = validate_webp(p)
    assert not r.valid
