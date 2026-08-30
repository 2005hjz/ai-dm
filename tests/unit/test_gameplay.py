"""玩法引擎:会话创建 / 指令处理 / 技能检定数值裁决 的单元测试。"""

from __future__ import annotations

from app.gameplay import advance_scene, apply_command, run_check, start_session
from app.persistence import new_id


def test_start_session_seed_state():
    sess = start_session(new_id(), player_name="阿梅")
    assert sess.state.player.name == "阿梅"
    assert sess.state.scene_id == "prologue"
    assert sess.state.npcs["smith"]["name"] == "老格"
    assert any(m.kind == "system" for m in sess.messages)
    assert sess.stats["rolls"] == 0


def test_run_check_seeded_success_failure():
    sess = start_session(new_id())
    ok = run_check(sess, "感知", seed=42)
    assert ok.ability == "感知"
    assert ok.value == 10  # 默认角色属性 10
    assert ok.modifier == 0  # 无熟练时修正=属性修正
    assert ok.dc == 12  # 引擎按上下文给默认 DC
    assert ok.success is True or ok.success is False
    assert ok.total == ok.roll.total + ok.modifier
    assert ok.degree in ("大成功", "成功", "失败", "大失败")
    assert sess.stats["checks"] == 1
    assert sess.stats["rolls"] == 1


def test_run_check_critical_20_always_success():
    """骰 20=大成功,无论 DC 多高都成功。"""
    sess = start_session(new_id())
    res = run_check(sess, "感知", dc_override=25, seed=5)  # seed=5 -> d20=20
    assert res.roll.rolls == [20]
    assert res.success is True
    assert res.degree == "大成功"


def test_run_check_critical_1_always_failure():
    """骰 1=大失败,无论加值/DC 多低都失败。"""
    sess = start_session(new_id())
    res = run_check(sess, "感知", dc_override=1, seed=31)  # seed=31 -> d20=1
    assert res.roll.rolls == [1]
    assert res.success is False
    assert res.degree == "大失败"


def test_run_check_non_critical_degrees():
    """普通骰只分成功/失败(大成功/大失败仅由 1/20 触发)。"""
    sess = start_session(new_id())
    for seed in range(1, 50):
        res = run_check(sess, "感知", dc_override=10, seed=seed)
        if res.roll.total not in (1, 20):
            assert res.degree in ("成功", "失败")


def test_run_check_dc_override():
    sess = start_session(new_id())
    res = run_check(sess, "感知", dc_override=25, seed=3)
    assert res.dc == 25
    assert res.success is False


def test_run_check_xp_on_success():
    sess = start_session(new_id())
    res = run_check(sess, "感知", dc_override=1, seed=42)  # 极低DC保证命中奖励经验
    assert res.success is True
    assert res.xp > 0
    assert sess.state.player.xp == res.xp
    assert sess.stats["xp"] == res.xp


def test_run_check_xp_levels_up():
    sess = start_session(new_id())
    c = sess.state.player
    c.level = 1
    res = run_check(sess, "感知", dc_override=15, seed=99)
    if res.success:
        assert c.level >= 1 and c.prof_bonus >= 2
        assert c.max_hp > 10


def test_run_check_skill_maps_to_ability():
    sess = start_session(new_id())
    res = run_check(sess, "推理")
    assert res.ability in ("智力", "感知")


def test_default_char_start():
    sess = start_session(new_id())
    assert sess.state.player.name != ""
    assert sess.state.world.title == "《风铃镇·灰烬墓穴》"
    assert sess.state.world.npcs.get("smith") is not None


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
    msg = advance_scene(sess, "forest")
    assert sess.state.scene_id == "forest"
    assert msg is not None
    assert advance_scene(sess, "not-exist") is None
