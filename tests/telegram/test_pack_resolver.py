import pytest
from dansticker.telegram.pack_resolver import parse_pack_url, is_pack_url, build_pack_url, validate_pack_name


@pytest.mark.parametrize("url,expected", [
    ("https://t.me/addstickers/FunnyCats",        "FunnyCats"),
    ("http://t.me/addstickers/Pack_123",           "Pack_123"),
    ("t.me/addstickers/MyPack",                   "MyPack"),
    ("https://t.me/addstickers/FunnyCats?x=1",    "FunnyCats"),
    ("  https://t.me/addstickers/TrimMe  ",       "TrimMe"),
])
def test_parse_valid(url, expected):
    assert parse_pack_url(url) == expected


@pytest.mark.parametrize("url", [
    "https://t.me/FunnyCats",
    "https://telegram.me/addstickers/Pack",
    "https://example.com",
    "not a url",
    "",
])
def test_parse_invalid(url):
    assert parse_pack_url(url) is None


def test_is_pack_url_true():
    assert is_pack_url("https://t.me/addstickers/Test") is True


def test_is_pack_url_false():
    assert is_pack_url("https://t.me/Test") is False


def test_build_pack_url():
    assert build_pack_url("MyPack") == "https://t.me/addstickers/MyPack"


@pytest.mark.parametrize("name,valid", [
    ("FunnyCats",   True),
    ("Pack_123",    True),
    ("A" * 64,      True),
    ("",            False),
    ("Pack Name",   False),
    ("Pack!",       False),
    ("A" * 65,      False),
])
def test_validate_pack_name(name, valid):
    assert validate_pack_name(name) is valid
