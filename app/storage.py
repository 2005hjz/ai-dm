"""SQLite 遥测库:结构化数值检定审计 + 会话度量持久化。

设计说明:
- 会话正文以 JSON 文档存储(persistence.py,易读、可版本化);
- 结构化「检定记录 / 会话度量」写入 SQLite(便于 SQL 审计与评测召回),构成 ER 图中的核心表。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS check_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  turn INTEGER NOT NULL DEFAULT 0,
  scene_id TEXT,
  skill TEXT,
  dc INTEGER,
  total INTEGER,
  success INTEGER,
  degree TEXT,
  expression TEXT,
  ts REAL NOT NULL,
  meta TEXT
);
CREATE TABLE IF NOT EXISTS session_metrics (
  session_id TEXT PRIMARY KEY,
  player TEXT,
  scene_id TEXT,
  rolls INTEGER DEFAULT 0,
  checks INTEGER DEFAULT 0,
  passed INTEGER DEFAULT 0,
  failed INTEGER DEFAULT 0,
  big_success INTEGER DEFAULT 0,
  big_failure INTEGER DEFAULT 0,
  turns INTEGER DEFAULT 0,
  created_at REAL,
  updated_at REAL
);
CREATE INDEX IF NOT EXISTS idx_check_session ON check_log(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_check_skill ON check_log(skill);
"""


class TelemetryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or config.DATA_DIR / "telemetry.db"
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        with self._lock:
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

    def log_check(
        self,
        session_id: str,
        turn: int,
        scene_id: str,
        skill: str,
        dc: int,
        total: int,
        success: bool,
        degree: str,
        expression: str,
        meta: dict | None = None,
        ts: float | None = None,
    ) -> int:
        import time

        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO check_log (session_id, turn, scene_id, skill, dc, total, success, degree, expression, ts, meta)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    turn,
                    scene_id,
                    skill,
                    dc,
                    total,
                    1 if success else 0,
                    degree,
                    expression,
                    ts if ts is not None else time.time(),
                    json.dumps(meta or {}, ensure_ascii=False),
                ),
            )
            self.conn.commit()
            return cur.lastrowid

    def upsert_metrics(
        self, session_id: str, data: dict, created_at: float | None = None, updated_at: float | None = None
    ) -> None:
        import time

        now = time.time()
        with self._lock:
            self.conn.execute(
                "INSERT INTO session_metrics (session_id, player, scene_id, rolls, checks, passed, failed,"
                " big_success, big_failure, turns, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(session_id) DO UPDATE SET"
                " player=excluded.player, scene_id=excluded.scene_id, rolls=excluded.rolls, checks=excluded.checks,"
                " passed=excluded.passed, failed=excluded.failed, big_success=excluded.big_success,"
                " big_failure=excluded.big_failure, turns=excluded.turns, updated_at=excluded.updated_at",
                (
                    session_id,
                    data.get("player", ""),
                    data.get("scene_id", ""),
                    data.get("rolls", 0),
                    data.get("checks", 0),
                    data.get("passed", 0),
                    data.get("failed", 0),
                    data.get("big_success", 0),
                    data.get("big_failure", 0),
                    data.get("turns", 0),
                    created_at if created_at is not None else now,
                    updated_at if updated_at is not None else now,
                ),
            )
            self.conn.commit()

    def query_checks(self, session_id: str, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT session_id, turn, scene_id, skill, dc, total, success, degree, expression, ts"
            " FROM check_log WHERE session_id=? ORDER BY ts DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        cols = ["session_id", "turn", "scene_id", "skill", "dc", "total", "success", "degree", "expression", "ts"]
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()


_store: TelemetryStore | None = None


def get_store() -> TelemetryStore:
    global _store
    if _store is None:
        _store = TelemetryStore()
    return _store


def telemetry_enabled() -> bool:
    return config.TELEMETRY_ENABLED
