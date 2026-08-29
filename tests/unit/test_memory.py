"""上下文记忆管理的单元测试。"""

from __future__ import annotations

from app import config, memory
from app.gameplay import add_message, start_session
from app.persistence import new_id


def test_estimate_tokens():
    assert memory.estimate_tokens("中文字符计数") >= 7
    assert memory.estimate_tokens("hello world") >= 2


def test_window_limits_messages(monkeypatch):
    monkeypatch.setattr(config, "MAX_MESSAGES_IN_CONTEXT", 4)
    sess = start_session(new_id())
    for i in range(10):
        add_message(sess, "player", "player", f"消息{i}")
    win = memory.window_messages(sess)
    assert len(win) == 4


def test_window_skips_irrelevant_kinds():
    sess = start_session(new_id())
    add_message(sess, "player", "player", "我检查房间")
    add_message(sess, "story", "dm", "你发现线索。")
    add_message(sess, "roll", "dice", "1d20 → 12")
    win = memory.window_messages(sess)
    assert any("玩家:" in w for w in win)
    assert any("DM/系统:" in w for w in win)


def test_build_system_prompt_injects_state():
    sess = start_session(new_id(), player_name="小叶")
    prompt = memory.build_system_prompt(sess)
    assert "小叶" in prompt
    assert "铁门之外" in prompt or "prologue" in prompt
    assert "7号房" not in ""  # noqa: SIM300 占位断言避免空洞


def test_build_context_respects_budget(monkeypatch):
    monkeypatch.setattr(config, "MAX_CONTEXT_TOKENS", 300)
    sess = start_session(new_id())
    for i in range(60):
        add_message(sess, "player", "player", f"第{i}条很长的玩家消息内容" * 3)
    ctx = memory.build_context(sess)
    total = sum(memory.estimate_tokens(m["content"]) for m in ctx)
    assert total <= config.MAX_CONTEXT_TOKENS + 200
    assert ctx[0]["role"] == "system"
