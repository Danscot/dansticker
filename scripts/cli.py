#!/usr/bin/env python3
"""CLI mode: convert a Telegram sticker pack without the bot.

Usage:
    python scripts/cli.py https://t.me/addstickers/PackName
    python scripts/cli.py https://t.me/addstickers/PackName --author "My Name" --name "Custom Name"
"""
from __future__ import annotations
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dansticker.config import cfg
from dansticker.jobs.processor import process_job
from dansticker.telegram.pack_resolver import parse_pack_url
from dansticker.types import Job


async def run(url: str, author: str, name: str) -> None:
    pack_name = parse_pack_url(url)
    if not pack_name:
        print("ERROR: Invalid Telegram sticker pack URL", file=sys.stderr)
        sys.exit(1)

    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        user_id=0,
        chat_id=0,
        telegram_url=url,
        pack_name=name or pack_name,
        author=author or cfg.DEFAULT_AUTHOR,
    )

    print(f"\nResolving pack: {pack_name}")
    print(f"Author:         {job.author}\n")

    stage_map = {
        "downloading": "Downloading",
        "converting":  "Converting ",
        "validating":  "Validating ",
        "packaging":   "Packaging  ",
    }

    async def on_progress(stage: str, done: int, total: int) -> None:
        label = stage_map.get(stage, stage)
        pct = int((done / total) * 100) if total else 0
        bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
        print(f"\r  {label} [{bar}] {done}/{total}", end="", flush=True)
        if done == total:
            print()

    result = await process_job(job, on_progress)
    print()

    if not result.success:
        print(f"FAILED: {result.error}", file=sys.stderr)
        sys.exit(1)

    print(f"Converted: {result.success_count} stickers")
    if result.failed_count:
        print(f"Failed:    {result.failed_count} stickers")
    print(f"Packs:     {result.total_packs}\n")
    print("Output files:")
    for path in result.output_paths:
        print(f"  -> {Path(path).resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dansticker CLI converter")
    parser.add_argument("url", help="Telegram sticker pack URL")
    parser.add_argument("--author", default="", help="Author name for the pack")
    parser.add_argument("--name", default="", help="Custom pack name")
    args = parser.parse_args()

    asyncio.run(run(args.url, args.author, args.name))
