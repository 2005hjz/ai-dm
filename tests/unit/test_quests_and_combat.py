"""任务系统 / 战斗骰子 / 职业亲和池 的单元测试(确定性 seed)。"""

from __future__ import annotations

import asyncio

from app.gameplay import accept_quest, apply_command, complete_quest, open_combat, resolve_attack, start_session
from app.models import AttackProposal, DMPlan
from app.persistence import new_id
from app.providers import parse_dm_plan


def test_start_session_injects_quest_board():
    sess = start_session(new_id())
    quests = sess.state.quests
    assert quests
    assert all(q.status == "available" for q in quests)
    assert any(q.source == "冒险者公会" for q in quests)
    assert any(q.source.startswith("NPC") for q in quests)  # NPC 发布任务
    assert any(q.reward_xp > 0 for q in quests)  # 任务奖励经验


def test_accept_and_complete_quest():
    sess = start_session(new_id())
    apply_command(sess, "/accept 1")
    q = sess.state.quests[0]
    assert q.status == "accepted"
    assert any("接受任务" in e for e in sess.state.events)

    gp_before = sess.state.player.gp
    xp_before = sess.state.player.xp
    apply_command(sess, "/complete 1")
    assert q.status == "done"
    assert sess.state.player.xp >= xp_before + q.reward_xp
    assert sess.state.player.gp >= gp_before + q.reward_gp
    assert sess.stats["quests_done"] == 1
    assert any("完成任务" in e for e in sess.state.events)


def test_complete_quest_awards_items():
    sess = start_session(new_id())
    accept_quest(sess, sess.state.quests[1])  # 清剿恶狼 → 狼皮斗篷
    complete_quest(sess, sess.state.quests[1])
    names = [it.name for it in sess.state.player.inventory]
    assert "狼皮斗篷" in names


def test_complete_without_accept_rejected():
    sess = start_session(new_id())
    ok = complete_quest(sess, sess.state.quests[0])
    assert ok is False
    assert sess.state.quests[0].status == "available"


def test_attack_resolves_hit_and_kill(seed=42):
    """战斗开启后攻击检定:d20 命中 vs AC,命中掷伤害骰,击杀结算经验。"""
    sess = start_session(new_id())
    open_combat(sess, {"name": "恶狼", "ac": 12, "hp": 1, "max_hp": 1, "reward_xp": 25, "gold": 5})
    res = resolve_attack(sess, seed=seed)
    assert res is not None
    assert res.target == "恶狼"
    assert res.ac == 12
    assert res.atk_total == res.atk_d20 + res.atk_mod
    if res.hit:
        assert res.damage_total > 0 or res.crit
        assert res.killed is True  # HP=1,命中必击杀
        assert sess.state.combat["killed"] is True
        assert sess.stats["kills"] == 1
        assert sess.state.player.xp >= 25
        assert sess.state.player.gp >= 5
    else:
        assert res.killed is False
        assert sess.stats["kills"] == 0


def test_attack_without_combat_is_none():
    sess = start_session(new_id())
    assert resolve_attack(sess) is None
    apply_command(sess, "/attack 恶狼")
    assert any("没有明确的战斗目标" in (m.content or "") for m in sess.messages)


def test_attack_command_appends_combat_message():
    sess = start_session(new_id())
    open_combat(sess, {"name": "食腐尸怪", "ac": 14, "hp": 6, "max_hp": 6})
    apply_command(sess, "/attack")
    assert any(m.kind == "combat" for m in sess.messages)
    assert any("攻击检定" in (m.content or "") for m in sess.messages)
    assert sess.stats["rolls"] >= 1


def test_capability_cap_grows_with_level():
    from app.dnd import capability_cap

    assert capability_cap(1) == 2
    assert capability_cap(2) == 3
    assert capability_cap(5) == 6
    assert capability_cap(0) == 2  # 兜底


def test_character_options_class_filtered():
    from app.character import character_options

    rogue = character_options(klass="盗贼")["skills"]
    assert all(s["name"] in ("隐匿", "手上功夫", "开锁", "欺瞒", "侦查", "说服") for s in rogue)
    assert not character_options(klass="盗贼")["spells"]  # 非施法者无法术亲和池

    mage = {s["name"] for s in character_options(klass="法师")["skills"]}
    spells = {s["name"] for s in character_options(klass="法师")["spells"]}
    assert "奥秘" in mage
    assert "燃烧之手" in spells
    assert "神导术" in spells  # 法师戏法
    assert character_options()["cap"] == 2


def test_build_from_form_spell_cap_and_auto_equip():
    """初始最多选 2 个法术(每级+1);装备按职业包+身份装备自动分配。"""
    from app.character import build_from_form

    form = {
        "name": "阿德",
        "race": "人类",
        "klass": "法师",
        "background": "学者",
        "birthplace": "圣白城教会",
        "abilities": {"strength": 10, "dexterity": 10, "constitution": 10, "intelligence": 15, "wisdom": 10, "charisma": 10},
        "spells": ["燃烧之手", "魔法飞弹", "睡眠术", "护盾术"],  # 4 个请求,封顶应只取 2
    }
    c = build_from_form(form, birthplaces={"圣白城教会": "书卷与烛火"})
    selected = [s for s in c.spells if s.level > 0]
    assert len(selected) <= 2
    names = [it.name for it in c.inventory]
    assert "法杖" in names  # 职业标准包
    assert "随身笔记" in names  # 身份(背景)装备


def test_build_from_form_same_class_twice_behavior():
    """重复传入职业装备不重复入库(去重)。"""
    from app.character import build_from_form

    form = {
        "name": "阿格",
        "race": "矮人",
        "klass": "战士",
        "background": "士兵",
        "abilities": {"strength": 15, "dexterity": 10, "constitution": 15, "intelligence": 8, "wisdom": 10, "charisma": 8},
        "inventory": [{"name": "长剑", "qty": 1, "desc": "", "value": 5}, {"name": "军徽", "qty": 1, "desc": "", "value": 5}],
    }
    c = build_from_form(form)
    counts = {n: sum(1 for i in c.inventory if i.name == n) for n in ("长剑", "军徽")}
    assert counts["长剑"] == 1
    assert counts["军徽"] == 1


def test_parse_dm_plan_attack_combat_quest_xp():
    raw = (
        '{"narrative": "狼群扑来。", "combat": {"name": "头狼", "ac": 13, "hp": 9, "reward_xp": 30, "gold": 10}, '
        '"attack": {"target": "头狼", "ac": 13}, "quest_done": null, "xp": 0}'
    )
    plan = parse_dm_plan(raw)
    assert plan.combat is not None and plan.combat["name"] == "头狼"
    assert plan.attack is not None and plan.attack.target == "头狼"
    assert plan.attack.ac == 13
    assert plan.xp == 0


def test_propose_or_resolve_kills_enemy_via_dm_plan(monkeypatch):
    """DM 声明 combat+attack → 引擎开战掷骰命中并结算击杀经验。"""

    async def run():
        import app.providers as p

        sess = start_session(new_id())
        plan = DMPlan(
            narrative="狼群从林间扑出!",
            combat={"name": "饿狼", "ac": 12, "hp": 1, "max_hp": 1, "reward_xp": 20},
            attack=AttackProposal(target="饿狼", ac=12),
        )

        class _FakeDM:
            name = "fake"

            def plan(self, session, player_text):
                return plan

        monkeypatch.setattr(p, "get_llm_provider", lambda: _FakeDM())
        return await p.propose_or_resolve(sess, "我挥剑迎击饿狼")

    result = asyncio.run(run())
    atk = result["attack_result"]
    assert result["combat"]["name"] == "饿狼"
    assert atk is not None
    if atk.killed:
        assert result["attack_result"].xp == 20
        assert result["attack_result"].hit is True
