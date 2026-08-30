"""共享测试夹具:注入项目根目录到 sys.path,准备可测试的会话。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import persistence  # noqa: E402

TEST_DIR = ROOT / "data" / "sessions"


@pytest.fixture(autouse=True)
def _force_offline_dm(monkeypatch):
    """所有测试强制离线 mock:不触碰真实 API Key,检定/世界生成/生图全走确定性兜底。"""
    from app import config

    monkeypatch.setattr(config, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(config, "IMAGE_PROVIDER", "mock")


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.fixture()
def session_dir(tmp_path, monkeypatch):
    """把持久化目录切到临时目录,避免污染真实 data/。"""
    monkeypatch.setattr(persistence.config, "SESSION_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir(exist_ok=True)
    return tmp_path / "sessions"
