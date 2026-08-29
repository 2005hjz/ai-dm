"""玩法引擎:会话创建 / 指令处理 / 技能检定数值裁决 的单元测试。"""

from __future__ import annotations

from app.gameplay import advance_scene, apply_command, run_check, start_session
from app.persistence import new_id


def test_start_session_seed_state():
    sess = start_session(new_id(), player_name="阿梅")
    assert sess.state.player.name == "阿梅"
    assert sess.state.scene_id == "prologue"
    assert sess.state.npcs["keeper"]["name"] == "老赵"
    assert any(m.kind == "system" for m in sess.messages)
    assert sess.stats["rolls"] == 0


def test_run_check_seeded_success_failure():
    sess = start_session(new_id())
    ok = run_check(sess, "侦查", seed=42)
    assert ok.skill == "侦查"
    assert ok.success is True or ok.success is False
    assert ok.total == ok.roll.total
    assert ok.degree in ("大成功", "成功", "失败", "大失败")
    assert sess.stats["checks"] == 1
    assert sess.stats["rolls"] == 1


def test_run_check_dc_override():
    sess = start_session(new_id())
    res = run_check(sess, "侦查", dc_override=25, seed=3)
    assert res.dc == 25
    assert res.success is False


def test_apply_roll_command():
    sess = start_session(new_id())
    apply_command(sess, "/roll 1d20+2")
    assert any(m.kind == "roll" for m in sess.messages)
    assert sess.stats["rolls"] == 1


def test_apply_roll_invalid():
    sess = start_session(new_id())
    apply_command(sess, "/roll banana")
    assert any("无法解析" in (m.content or "") for m in sess.messages)


def test_apply_check_command():
    sess = start_session(new_id())
    apply_command(sess, "/check 推理")
    assert any(m.kind == "check" for m in sess.messages)
    assert any(m.kind == "roll" for m in sess.messages)


def test_apply_scene_command():
    sess = start_session(new_id())
    apply_command(sess, "/scene")
    assert any(m.kind == "card" for m in sess.messages)


def test_apply_hp_and_help():
    sess = start_session(new_id())
    apply_command(sess, "/hp")
    assert any("HP" in (m.content or "") for m in sess.messages)
    apply_command(sess, "/help")
    assert any("自由行动" in (m.content or "") for m in sess.messages)


def test_apply_restart_keeps_player():
    sess = start_session(new_id(), player_name="小北")
    apply_command(sess, "/restart")
    assert sess.state.player.name == "小北"
    assert sess.state.scene_id == "prologue"


def test_apply_command_returns_none_for_free_action():
    sess = start_session(new_id())
    assert apply_command(sess, "我检查那扇门") is None


def test_advance_scene():
    sess = start_session(new_id())
    msg = advance_scene(sess, "hallway")
    assert sess.state.scene_id == "hallway"
    assert msg is not None
    assert advance_scene(sess, "not-exist") is None
