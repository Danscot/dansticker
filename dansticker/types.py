"""Shared dataclasses and enums for Dansticker."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from datetime import datetime


class StickerSourceType(str, Enum):
    WEBP = "webp"
    TGS = "tgs"
    WEBM = "webm"
    UNKNOWN = "unknown"


class StickerStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ConversionStrategy(str, Enum):
    ALPHA_PRESERVE = "alpha_preserve"
    RGBA_NORMALIZE = "rgba_normalize"
    FLATTEN_BG = "flatten_bg"
    TGS_RENDER = "tgs_render"


class PackType(str, Enum):
    STATIC = "static"
    ANIMATED = "animated"
    MIXED = "mixed"


class JobStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    CONVERTING = "converting"
    VALIDATING = "validating"
    PACKAGING = "packaging"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Sticker:
    index: int
    file_id: str
    source_type: StickerSourceType
    emoji: str = "🎉"
    animated: bool = False
    video: bool = False
    status: StickerStatus = StickerStatus.PENDING
    source_path: Optional[str] = None
    output_path: Optional[str] = None
    error: Optional[str] = None
    strategy: Optional[ConversionStrategy] = None
    duration_ms: Optional[float] = None


@dataclass
class StickerPack:
    id: str
    telegram_url: str
    telegram_name: str
    name: str
    author: str
    stickers: List[Sticker] = field(default_factory=list)
    pack_type: PackType = PackType.STATIC
    thumbnail_path: Optional[str] = None


@dataclass
class WhatsAppPack:
    name: str           # always the clean user-chosen name — no suffixes
    author: str
    stickers: List[Sticker]
    source_url: str
    thumbnail_path: Optional[str] = None
    part_index: int = 1
    total_parts: int = 1
    # Used by the builder to construct a descriptive filename — never shown to user
    _group: str = ""          # "static" | "animated" | ""
    _chunk_index: int = 0     # 0-based chunk within group
    _chunk_total: int = 1     # total chunks in this group


@dataclass
class MediaInfo:
    file_size: int
    codec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    fps: Optional[float] = None
    pixel_format: Optional[str] = None
    has_alpha: bool = False
    has_audio: bool = False
    frame_count: Optional[int] = None


@dataclass
class ConversionResult:
    success: bool
    output_path: Optional[str] = None
    strategy: Optional[ConversionStrategy] = None
    reason: Optional[str] = None
    duration_ms: Optional[float] = None


@dataclass
class ValidationResult:
    valid: bool
    reason: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    animated: Optional[bool] = None
    frame_count: Optional[int] = None
    file_size: Optional[int] = None


@dataclass
class UserPreferences:
    telegram_user_id: int
    preferred_author: str
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Job:
    id: str
    user_id: int
    chat_id: int
    telegram_url: str
    pack_name: str
    author: str
    status: JobStatus = JobStatus.QUEUED
    message_id: Optional[int] = None
    error: Optional[str] = None
    output_paths: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
