"""会话持久化:每个会话一个 JSON 文件。重启服务后仍可恢复对话。"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from . import config
from .models import Character, GameSession, Message, WorldOutline


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _safe_name(name: str) -> str:
    name = re.sub(r"[^\w\u4e00-\u9fff-]", "_", name or "").strip("_")[:20]
    return name or "session"


def _path(session_id: str) -> Path:
    return config.SESSION_DIR / f"{session_id}.json"


def _world_path(world_id: str) -> Path:
    return config.WORLD_DIR / f"{world_id}.json"


def save_world(world: WorldOutline) -> None:
    _world_path(world.id).write_text(world.model_dump_json(indent=2), encoding="utf-8")


def load_world(world_id: str) -> WorldOutline | None:
    path = _world_path(world_id)
    if not path.exists():
        return None
    try:
        return WorldOutline.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def _char_path(profile_id: str) -> Path:
    return config.CHARACTER_DIR / f"{profile_id}.json"


def save_character_profile(profile_id: str, character: Character) -> None:
    _char_path(profile_id).write_text(character.model_dump_json(indent=2), encoding="utf-8")


def load_character_profile(profile_id: str) -> Character | None:
    path = _char_path(profile_id)
    if not path.exists():
        return None
    try:
        return Character.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def list_character_profiles() -> list[dict]:
    out: list[dict] = []
    for path in sorted(config.CHARACTER_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        c = load_character_profile(path.stem)
        if c:
            out.append(
                {
                    "id": path.stem,
                    "name": c.name,
                    "race": c.race,
                    "klass": c.klass,
                    "background": c.background,
                    "birthplace": c.birthplace,
                    "level": c.level,
                    "hp": c.hp,
                    "max_hp": c.max_hp,
                    "gp": c.gp,
                }
            )
    return out


def delete_character_profile(profile_id: str) -> bool:
    path = _char_path(profile_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def list_worlds() -> list[WorldOutline]:
    out = []
    for path in sorted(config.WORLD_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        world = load_world(path.stem)
        if world:
            out.append(world)
    return out


def save_session(session: GameSession) -> None:
    session.updated_at = _now()
    _path(session.id).write_text(session.model_dump_json(indent=2), encoding="utf-8")


def load_session(session_id: str) -> GameSession | None:
    path = _path(session_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    sess = GameSession.model_validate(data)
    sess.messages = [Message.model_validate(m) for m in sess.messages]
    return sess


def list_sessions() -> list[dict]:
    out = []
    for path in sorted(config.SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append(
            {
                "id": data.get("id", path.stem),
                "title": data.get("title", ""),
                "created_at": data.get("created_at", 0),
                "updated_at": data.get("updated_at", 0),
                "scene_id": data.get("state", {}).get("scene_id", ""),
                "msg_count": len(data.get("messages", [])),
                "player": data.get("state", {}).get("player", {}).get("name", ""),
            }
        )
    return out


def delete_session(session_id: str) -> bool:
    path = _path(session_id)
    if path.exists():
        path.unlink()
        return True
    return False


def _now() -> float:
    import time

    return time.time()
