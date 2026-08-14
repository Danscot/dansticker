"""All Telegram bot handlers — commands, messages, callbacks."""
from __future__ import annotations
import asyncio
import os
import uuid
from pathlib import Path

from telegram import Update, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from dansticker.bot.keyboards import pack_confirm_keyboard, customize_keyboard, download_keyboard
from dansticker.bot.messages import (
    esc, pack_found_msg, progress_msg, completion_msg,
    error_msg, INVALID_URL_MSG, START_MSG, HELP_MSG,
)
from dansticker.bot.session import Session, set_session, get_session, get_session_by_user, delete_session
from dansticker.config import cfg
from dansticker.jobs.processor import process_job, cleanup_job
from dansticker.logger import get_logger
from dansticker.storage.db import get_preferred_author, save_user_preferences
from dansticker.telegram.downloader import TelegramDownloader
from dansticker.telegram.pack_resolver import parse_pack_url, is_pack_url, build_pack_url
from dansticker.types import Job

log = get_logger("bot.handlers")

MD = ParseMode.MARKDOWN_V2


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _safe_edit(update: Update, text: str, reply_markup=None) -> None:
    """Edit message text, ignoring 'message not modified' errors."""
    try:
        kwargs = {"text": text, "parse_mode": MD}
        if reply_markup:
            kwargs["reply_markup"] = reply_markup
        await update.callback_query.edit_message_text(**kwargs)
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            log.warning(f"safe_edit error: {e}")


# ── Commands ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_MSG, parse_mode=MD)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_MSG, parse_mode=MD)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session = get_session_by_user(user_id)
    if session:
        delete_session(session.job_id)
        asyncio.create_task(cleanup_job(session.job_id))
        await update.message.reply_text("Conversion cancelled\\.", parse_mode=MD)
    else:
        await update.message.reply_text("No active conversion\\.", parse_mode=MD)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    current = await get_preferred_author(user_id)
    sentinel_id = f"settings_{user_id}"
    from dansticker.types import StickerPack, PackType
    fake_pack = StickerPack(
        id=sentinel_id, telegram_url="", telegram_name="",
        name="", author=current,
    )
    set_session(sentinel_id, Session(
        job_id=sentinel_id,
        user_id=user_id,
        chat_id=update.effective_chat.id,
        pack=fake_pack,
        pack_name="",
        author=current,
        awaiting_input="author",
    ))
    await update.message.reply_text(
        f"Current default author: *{esc(current)}*\n\nSend your new author name:",
        parse_mode=MD,
    )


async def cmd_convert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = " ".join(context.args or []).strip()
    if not url:
        await update.message.reply_text(
            "Usage: /convert `https://t\\.me/addstickers/PackName`", parse_mode=MD
        )
        return
    await _handle_pack_url(update, context, url)


# ── Sticker message — auto-fetch the pack ─────────────────────────────────────

async def msg_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    User forwards/sends any sticker → extract its set name → start the flow.
    Stickers that don't belong to a set (custom emoji etc.) are ignored gracefully.
    """
    sticker = update.message.sticker
    set_name = sticker.set_name if sticker else None

    if not set_name:
        await update.message.reply_text(
            "This sticker doesn't belong to a pack \\(or it's a custom emoji\\)\\.",
            parse_mode=MD,
        )
        return

    url = build_pack_url(set_name)
    await _handle_pack_url(update, context, url)


# ── Plain URL / text messages ──────────────────────────────────────────────────

async def msg_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Check if we're waiting for user input (customize flow)
    session = get_session_by_user(user_id)
    if session and session.awaiting_input:
        await _handle_awaiting_input(update, context, session, text)
        return

    if is_pack_url(text):
        await _handle_pack_url(update, context, text)


# ── Callback queries ───────────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":", 2)
    action = parts[0]
    job_id = parts[1] if len(parts) > 1 else ""
    extra = parts[2] if len(parts) > 2 else ""

    user_id = update.effective_user.id
    session = get_session(job_id)

    if not session:
        await query.edit_message_text("Session expired\\. Please send the URL again\\.", parse_mode=MD)
        return

    if session.user_id != user_id:
        return

    if action == "convert":
        await _start_conversion(update, context, session)

    elif action == "customize":
        await _safe_edit(
            update,
            f"*Customize Pack*\n\nName: {esc(session.pack_name)}\nAuthor: {esc(session.author)}",
            customize_keyboard(job_id),
        )

    elif action == "setname":
        session.awaiting_input = "name"
        await query.edit_message_text("Send the new pack name:")

    elif action == "setauthor":
        session.awaiting_input = "author"
        await query.edit_message_text("Send the new author name:")

    elif action == "back":
        msg = pack_found_msg(session.pack, session.pack_name, session.author)
        await _safe_edit(update, msg, pack_confirm_keyboard(job_id))

    elif action == "cancel":
        delete_session(job_id)
        asyncio.create_task(cleanup_job(job_id))
        await query.edit_message_text("Conversion cancelled\\.", parse_mode=MD)

    elif action == "download":
        idx = int(extra) if extra.isdigit() else 0
        paths = session.output_paths
        if idx < len(paths) and os.path.exists(paths[idx]):
            await context.bot.send_document(
                chat_id=session.chat_id,
                document=open(paths[idx], "rb"),
                filename=Path(paths[idx]).name,
                caption=f"{session.pack_name}" + (f" — Part {idx + 1}" if len(paths) > 1 else ""),
            )
        else:
            await context.bot.send_message(session.chat_id, "File not available\\.", parse_mode=MD)


# ── Core logic ─────────────────────────────────────────────────────────────────

async def _handle_pack_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    pack_name = parse_pack_url(url)
    if not pack_name:
        await update.message.reply_text(INVALID_URL_MSG, parse_mode=MD)
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    loading = await update.message.reply_text("Fetching pack info\\.\\.\\.", parse_mode=MD)

    try:
        downloader = TelegramDownloader(cfg.TELEGRAM_BOT_TOKEN)
        job_id = str(uuid.uuid4())
        pack = await downloader.resolve_pack(pack_name, job_id)
    except Exception as e:
        log.warning(f"Could not resolve pack '{pack_name}': {e}")
        await loading.edit_text(
            "Could not find that sticker pack\\. Check the link and try again\\.",
            parse_mode=MD,
        )
        return

    author = await get_preferred_author(user_id)
    pack.author = author

    session = Session(
        job_id=pack.id,
        user_id=user_id,
        chat_id=chat_id,
        pack=pack,
        pack_name=pack.telegram_name,
        author=author,
        message_id=loading.message_id,
    )
    set_session(pack.id, session)

    msg = pack_found_msg(pack, session.pack_name, session.author)
    await loading.edit_text(msg, parse_mode=MD, reply_markup=pack_confirm_keyboard(pack.id))


async def _handle_awaiting_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
    text: str,
) -> None:
    user_id = update.effective_user.id
    value = text.strip()[:64]

    # Settings-only flow
    if session.job_id.startswith("settings_"):
        await save_user_preferences(user_id, value)
        delete_session(session.job_id)
        await update.message.reply_text(
            f"Default author set to: *{esc(value)}*", parse_mode=MD
        )
        return

    if session.awaiting_input == "name":
        session.pack_name = value
    elif session.awaiting_input == "author":
        session.author = value
        await save_user_preferences(user_id, value)

    session.awaiting_input = None

    await update.message.reply_text(
        f"Updated\\!\n\nPack name: *{esc(session.pack_name)}*\nAuthor: *{esc(session.author)}*",
        parse_mode=MD,
        reply_markup=pack_confirm_keyboard(session.job_id),
    )


async def _start_conversion(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session: Session,
) -> None:
    session.pack.name = session.pack_name
    session.pack.author = session.author
    chat_id = session.chat_id

    job = Job(
        id=session.job_id,
        user_id=session.user_id,
        chat_id=chat_id,
        telegram_url=session.pack.telegram_url,
        pack_name=session.pack_name,
        author=session.author,
    )

    progress_message = await context.bot.send_message(
        chat_id,
        progress_msg(session.pack_name, "Downloading", 0, len(session.pack.stickers)),
        parse_mode=MD,
    )
    prog_id = progress_message.message_id

    stage_labels = {
        "downloading": "Downloading",
        "converting":  "Converting",
        "validating":  "Validating",
        "packaging":   "Packaging",
    }
    last_text = [""]

    async def on_progress(stage: str, done: int, total: int) -> None:
        label = stage_labels.get(stage, stage)
        text = progress_msg(session.pack_name, label, done, total)
        if text == last_text[0]:
            return
        last_text[0] = text
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=prog_id,
                text=text,
                parse_mode=MD,
            )
        except Exception:
            pass

    result = await process_job(job, on_progress)

    if not result.success or not result.output_paths:
        friendly = (
            "None of the stickers could be converted\\. "
            "The pack may use an unsupported format\\."
            if result.error == "No stickers could be converted"
            else esc(result.error or "Unknown error")
        )
        await context.bot.send_message(
            chat_id,
            f"*Conversion Failed*\n\n{friendly}",
            parse_mode=MD,
        )
        delete_session(session.job_id)
        return

    session.output_paths = result.output_paths

    finish_text = completion_msg(
        session.pack_name,
        result.success_count,
        result.failed_count,
        result.total_packs,
    )
    await context.bot.send_message(
        chat_id,
        finish_text,
        parse_mode=MD,
        reply_markup=download_keyboard(result.output_paths, session.job_id),
    )

    # Send files directly
    for i, path in enumerate(result.output_paths):
        if os.path.exists(path):
            caption = session.pack_name + (
                f" — Part {i + 1}" if len(result.output_paths) > 1 else ""
            )
            await context.bot.send_document(
                chat_id=chat_id,
                document=open(path, "rb"),
                filename=Path(path).name,
                caption=caption,
            )

    async def _deferred_cleanup():
        await asyncio.sleep(300)
        delete_session(session.job_id)
        await cleanup_job(session.job_id)

    asyncio.create_task(_deferred_cleanup())


# ── Registration ───────────────────────────────────────────────────────────────

def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("convert", cmd_convert))
    # Sticker sent by user → auto-detect the pack
    app.add_handler(MessageHandler(filters.Sticker.ALL, msg_sticker))
    # Plain text / URLs
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_text))
    app.add_handler(CallbackQueryHandler(callback_handler))
