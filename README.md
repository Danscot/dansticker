# Dansticker

> Telegram sticker pack → WhatsApp `.wastickers` converter bot, written in Python.

---

## Features

- Converts **static WebP**, **animated TGS** (Lottie), and **video WebM** stickers
- Preserves transparency wherever possible
- 3-strategy fallback pipeline for WebM (alpha → RGBA normalize → flatten)
- Multiple TGS renderers: `lottie` lib → `rlottie-python` → FFmpeg fallback
- Auto-splits packs at WhatsApp's 30-sticker limit
- Separates static and animated stickers into compatible packs
- Per-sticker error isolation — one bad sticker never kills the pack
- Persistent user preferences (preferred author) via SQLite
- Interactive inline keyboard UI with progress updates
- All limits configurable via `.env`
- Docker deployment ready

---

## Quick Start

### Requirements

- Python 3.11+
- FFmpeg + FFprobe (`brew install ffmpeg` / `apt install ffmpeg`)
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

```bash
# Clone
git clone https://github.com/yourname/dansticker.git
cd dansticker

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — add your TELEGRAM_BOT_TOKEN

# Run
python main.py
```

### Optional: TGS support

```bash
pip install lottie          # Python Lottie renderer
pip install rlottie-python  # Native rlottie bindings (faster)
```

### Docker

```bash
cp .env.example .env
# Edit .env
docker-compose up -d
```

---

## CLI (no Telegram needed)

```bash
python scripts/cli.py https://t.me/addstickers/FunnyCats
python scripts/cli.py https://t.me/addstickers/FunnyCats --author "My Name" --name "Custom"
```

---

## Bot Usage

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show help |
| `/convert <url>` | Convert a sticker pack |
| `/settings` | Set your default author name |
| `/cancel` | Cancel the current job |

You can also paste a `t.me/addstickers/` URL directly.

### Flow

```
User: https://t.me/addstickers/FunnyCats

Bot:
  Sticker Pack Found
  Name: Funny Cats | Stickers: 47 | Type: Static
  Pack name: Funny Cats | Author: Dansticker
  [Convert] [Customize] [Cancel]

  → progress updates →

  Conversion Complete
  46/47 stickers converted
  2 WhatsApp packs generated
  [Download Part 1] [Download Part 2]
```

---

## Project Structure

```
dansticker/
├── main.py                   ← Entry point
├── dansticker/
│   ├── config/__init__.py    ← All settings (env-driven)
│   ├── logger.py             ← Structured logging
│   ├── types.py              ← Dataclasses: Sticker, Pack, Job, etc.
│   ├── telegram/
│   │   ├── pack_resolver.py  ← URL parsing & validation
│   │   └── downloader.py     ← Telegram API + async download
│   ├── media/
│   │   ├── inspector.py      ← FFprobe wrapper
│   │   ├── converter.py      ← Type dispatcher
│   │   ├── static_webp.py    ← Pillow: WebP → 512×512 RGBA WebP
│   │   ├── webm.py           ← FFmpeg: 3-strategy WebM pipeline
│   │   ├── tgs.py            ← Lottie/rlottie/FFmpeg TGS pipeline
│   │   ├── animation.py      ← Single FFmpeg animation encoder
│   │   └── validator.py      ← Pillow: full WebP validation
│   ├── pack/
│   │   ├── builder.py        ← .wastickers ZIP builder
│   │   ├── metadata.py       ← info.json generator
│   │   ├── splitter.py       ← 30-sticker limit + static/animated split
│   │   └── thumbnail.py      ← 96×96 PNG thumbnail
│   ├── jobs/
│   │   ├── processor.py      ← Full pipeline orchestrator
│   │   └── cleanup.py        ← Periodic temp file sweeper
│   ├── storage/
│   │   └── db.py             ← aiosqlite user preferences
│   └── bot/
│       ├── handlers.py       ← All PTB handlers
│       ├── keyboards.py      ← Inline keyboard builders
│       ├── messages.py       ← Message templates + MarkdownV2 escaping
│       └── session.py        ← In-memory session state
├── tests/
│   ├── telegram/             ← URL resolver tests
│   ├── media/                ← Validator, static WebP tests
│   └── pack/                 ← Splitter, metadata tests
├── scripts/
│   └── cli.py                ← CLI converter (no Telegram)
├── .env.example
├── Dockerfile
└── docker-compose.yml
```

---

## `.wastickers` Format

```
thumbnail.png      ← 96×96 PNG
sticker_001.webp   ← 512×512 WebP
sticker_002.webp
...
title.txt          ← Pack name
author.txt         ← Author name
link.txt           ← Telegram source URL
info.json          ← WhatsApp sticker metadata
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | required | From @BotFather |
| `DEFAULT_AUTHOR` | `Dansticker` | Default author name |
| `MAX_STICKERS_PER_PACK` | `30` | WhatsApp limit |
| `MAX_CONCURRENT_JOBS` | `2` | Parallel conversions |
| `MAX_VIDEO_DURATION` | `8` | Max WebM duration (seconds) |
| `MAX_OUTPUT_SIZE` | `512000` | Max output sticker size (bytes) |
| `WEBP_QUALITY` | `80` | WebP encoding quality |
| `WEBP_FPS` | `15` | Target animation FPS |

---

## Testing

```bash
pip install -r requirements.txt
pytest
pytest --tb=short -v        # verbose
pytest tests/media/          # one module
```
