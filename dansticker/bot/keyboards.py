"""Inline keyboard builders."""
from __future__ import annotations
from typing import List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def pack_confirm_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Convert", callback_data=f"convert:{job_id}"),
            InlineKeyboardButton("Customize", callback_data=f"customize:{job_id}"),
        ],
        [InlineKeyboardButton("Cancel", callback_data=f"cancel:{job_id}")],
    ])


def customize_keyboard(job_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Change Name", callback_data=f"setname:{job_id}")],
        [InlineKeyboardButton("Change Author", callback_data=f"setauthor:{job_id}")],
        [
            InlineKeyboardButton("Back", callback_data=f"back:{job_id}"),
            InlineKeyboardButton("Cancel", callback_data=f"cancel:{job_id}"),
        ],
    ])


def download_keyboard(output_paths: List[str], job_id: str) -> InlineKeyboardMarkup:
    rows = []
    for i, _ in enumerate(output_paths):
        rows.append([
            InlineKeyboardButton(
                f"Download Part {i + 1}",
                callback_data=f"download:{job_id}:{i}",
            )
        ])
    return InlineKeyboardMarkup(rows)
