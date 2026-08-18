"""Parse and validate Telegram sticker pack URLs."""
from __future__ import annotations
import re
from typing import Optional

# Matches https://t.me/addstickers/PackName (with optional query params)
_PACK_RE = re.compile(
    r"^(?:https?://)?t\.me/addstickers/([A-Za-z0-9_]{1,64})",
    re.IGNORECASE,
)


def parse_pack_url(text: str) -> Optional[str]:
    """Return the pack name from a Telegram sticker URL, or None."""
    m = _PACK_RE.match(text.strip())
    return m.group(1) if m else None


def is_pack_url(text: str) -> bool:
    return parse_pack_url(text) is not None


def build_pack_url(pack_name: str) -> str:
    return f"https://t.me/addstickers/{pack_name}"


def validate_pack_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_]{1,64}", name))
