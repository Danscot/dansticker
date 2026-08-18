"""User-facing message templates."""
from __future__ import annotations
import re

from dansticker.types import StickerPack, PackType


def esc(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    return re.sub(r"([_*\[\]()~`>#+\-=|{}.!\\])", r"\\\1", str(text))


def pack_found_msg(pack: StickerPack, pack_name: str, author: str) -> str:
    type_label = {
        PackType.STATIC: "Static",
        PackType.ANIMATED: "Animated",
        PackType.MIXED: "Mixed",
    }.get(pack.pack_type, "Unknown")

    return (
        f"*Sticker Pack Found*\n\n"
        f"Name: *{esc(pack.telegram_name)}*\n"
        f"Stickers: *{len(pack.stickers)}*\n"
        f"Type: {esc(type_label)}\n\n"
        f"Pack name: {esc(pack_name)}\n"
        f"Author: {esc(author)}"
    )


def progress_msg(pack_name: str, stage: str, done: int, total: int) -> str:
    bar_width = 20
    filled = round((done / total) * bar_width) if total > 0 else 0
    bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
    return (
        f"*{esc(pack_name)}*\n\n"
        f"{esc(stage)}\n"
        f"`{bar}` {done}/{total}"
    )


def completion_msg(pack_name: str, success: int, failed: int, total_packs: int) -> str:
    lines = [f"*Conversion Complete*\n"]
    lines.append(f"{success} sticker{'s' if success != 1 else ''} converted successfully")
    if failed:
        lines.append(f"{failed} sticker{'s' if failed != 1 else ''} could not be converted")
    if total_packs > 1:
        lines.append(f"\n{total_packs} WhatsApp packs generated")
    return "\n".join(lines)


def error_msg(reason: str) -> str:
    return f"*Conversion Failed*\n\n{esc(reason)}"


INVALID_URL_MSG = (
    "That doesn't look like a Telegram sticker pack URL\\.\n\n"
    "Please send a link like:\n"
    "`https://t\\.me/addstickers/PackName`"
)

START_MSG = (
    "*Welcome to Dansticker\\!*\n\n"
    "Send me a Telegram sticker pack link and I'll convert it "
    "to a `\\.wastickers` file for WhatsApp\\.\n\n"
    "Example:\n"
    "`https://t\\.me/addstickers/PackName`\n\n"
    "Or use /convert \\<url\\>"
)

HELP_MSG = (
    "*Dansticker Help*\n\n"
    "*Commands:*\n"
    "/convert \\<url\\> — Convert a sticker pack\n"
    "/settings — Set your default author name\n"
    "/cancel — Cancel the current conversion\n"
    "/help — Show this message\n\n"
    "*How it works:*\n"
    "1\\. Send a Telegram sticker pack URL\n"
    "2\\. Confirm or customize pack name & author\n"
    "3\\. Wait while stickers are converted\n"
    "4\\. Download your `\\.wastickers` file\\(s\\)\n"
    "5\\. Import into your sticker app"
)
