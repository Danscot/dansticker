"""In-memory session store for multi-step bot conversations."""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from dansticker.types import StickerPack


@dataclass
class Session:
    job_id: str
    user_id: int
    chat_id: int
    pack: StickerPack
    pack_name: str
    author: str
    message_id: Optional[int] = None
    awaiting_input: Optional[str] = None   # "name" | "author" | None
    output_paths: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


_sessions: Dict[str, Session] = {}


def set_session(job_id: str, session: Session) -> None:
    _sessions[job_id] = session


def get_session(job_id: str) -> Optional[Session]:
    return _sessions.get(job_id)


def get_session_by_user(user_id: int) -> Optional[Session]:
    for s in _sessions.values():
        if s.user_id == user_id:
            return s
    return None


def delete_session(job_id: str) -> None:
    _sessions.pop(job_id, None)


def purge_old_sessions(max_age: float = 7200) -> None:
    now = time.time()
    stale = [jid for jid, s in _sessions.items() if now - s.created_at > max_age]
    for jid in stale:
        _sessions.pop(jid, None)
