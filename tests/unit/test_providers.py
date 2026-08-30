"""Provider 抽象层单元测试:mock 氛围兜底、结构化 DMPlan 解析、LLM 实时判决的引擎裁决。"""

from __future__ import annotations

import asyncio

from app.dice import normalize_skill
from app.gameplay import start_session
from app.models import DMPlan, SkillProposal
from app.persistence import new_id
from app.providers import (
    MockLLMProvider,
    get_image_provider,
    get_llm_provider,
    parse_dm_plan,
    propose_or_resolve,
)


def test_default_providers_are_mock(monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(cfg, "IMAGE_PROVIDER", "mock")
    assert get_llm_provider().name == "mock"
    assert get_image_provider().name == "mock"


class _FakeDM:
    """替身 DM:把预置的 DMPlan 原样交给引擎,用于确定性测引擎裁决,不再依赖任何离线剧情。"""

    name = "fake"

    def __init__(self, plan: DMPlan):
        self._plan = plan

    def plan(self, session, player_text: str) -> DMPlan:
        return self._plan


def test_mock_plan_is_atmospheric_fallback():
    """Mock 只作离线氛围兜底:无预写剧情文本、无检定建议、无场景跳转。"""
    sess = start_session(new_id())
    plan = MockLLMProvider().plan(sess, "我推开7号房的门")
    assert isinstance(plan, DMPlan)
    assert plan.narrative
    assert "7号房" not in plan.narrative
    assert plan.check is None
    assert plan.advance_scene is None


def test_mock_plan_never_scripts_hook():
    sess = start_session(new_id())
    plan = MockLLMProvider().plan(sess, "我俯身检查床底的白影")
    assert plan.check is None and plan.advance_scene is None


def test_parse_dm_plan_valid_json():
    raw = '{"narrative": "你发现床底有个白影。", "check": {"skill": "侦查", "reason": "雾太浓,想看清", "dc": 11}, "advance_scene": null, "triggers": ["x"]}'
    plan = parse_dm_plan(raw)
    assert plan.narrative == "你发现床底有个白影。"
    assert plan.check is not None
    assert normalize_skill(plan.check.skill) == "侦查"
    assert plan.check.dc == 11


def test_parse_dm_plan_fenced_json():
    raw = '```json\n{"narrative": "门开了。", "check": null, "advance_scene": "forest", "triggers": []}\n```'
    plan = parse_dm_plan(raw)
    assert plan.advance_scene == "forest"
    assert plan.check is None


def test_parse_dm_plan_invented_scene_rejected():
    """引擎防御:LLM 幻觉出未登记的场景 id 会被丢弃,只保留叙述。"""
    raw = '{"narrative": "你走进一个不存在的空间。", "advance_scene": "ghost-realm", "check": null, "triggers": []}'
    plan = parse_dm_plan(raw)
    assert plan.advance_scene is None
    assert plan.narrative == "你走进一个不存在的空间。"


def test_parse_dm_plan_loot_gold_and_ability():
    raw = (
        '{"narrative": "你捡起一把剑。", "check": {"ability": "力量", "dc": 10}, '
        '"loot": [{"name": "火焰大剑", "effect": "火焰+1d4伤害", "value": 60}], "gold": 10, "hp": -2}'
    )
    plan = parse_dm_plan(raw)
    assert plan.check.ability == "力量" if plan.check else False
    assert plan.loot[0].name == "火焰大剑" if plan.loot else False
    assert plan.gold == 10 and plan.hp == -2


def test_parse_dm_plan_garbage_falls_back():
    plan = parse_dm_plan("这是一段完全不是JSON的叙述文本")
    assert plan.narrative == "这是一段完全不是JSON的叙述文本"


def test_propose_or_resolve_advance_whitelisted_branch(monkeypatch):
    """LLM 判定了大分支(declared):引擎校验白名单后推进,并注入分支入场白。"""

    async def run():
        import app.providers as p

        sess = start_session(new_id())
        plan = DMPlan(narrative="风铃镇的钟声在背后响起。", advance_scene="market", triggers=["branch"])
        monkeypatch.setattr(p, "get_llm_provider", lambda: _FakeDM(plan))
        res = await propose_or_resolve(sess, "我走进酒馆·铃铛与玫瑰")
        return res, sess

    res, sess = asyncio.run(run())
    assert res["advanced"] is True
    assert res["advance_dm_text"]
    assert sess.state.scene_id == "market"
    assert any("推进" in e for e in sess.state.events)


def test_propose_or_resolve_blocks_undeclared_advance(monkeypatch):
    """玩家想跳的不是已声明的大分支 → 引擎拒绝推进,剧情仍由 DM 叙述裁决。"""

    async def run():
        import app.providers as p

        sess = start_session(new_id())
        plan = DMPlan(narrative="雾里没有那样的入口。", advance_scene="tomb", triggers=["branch"])
        monkeypatch.setattr(p, "get_llm_provider", lambda: _FakeDM(plan))
        res = await propose_or_resolve(sess, "我直接冲进灰烬墓穴")
        return res, sess

    res, sess = asyncio.run(run())
    # prologue 声明的分支是 market/forest → tomb 未声明,推进被拦
    assert res["advanced"] is False
    assert sess.state.scene_id == "prologue"


def test_propose_or_resolve_check_numeric_adjudication(monkeypatch):
    """LLM 建议检定 → 引擎统一 DC 裁决;成功与否都不由引擎强行推剧情。"""

    async def run():
        import app.providers as p

        sess = start_session(new_id())
        plan = DMPlan(
            narrative="雾太浓,你眯起眼睛想看清帘子。",
            check=SkillProposal(skill="侦查", reason="雾太浓", dc=10),
        )
        monkeypatch.setattr(p, "get_llm_provider", lambda: _FakeDM(plan))
        res = await propose_or_resolve(sess, "我观察帘子后面")
        return res, sess

    res, sess = asyncio.run(run())
    check = res["check"]
    assert check is not None
    assert check.ability == "感知"  # 侦查 → 感知(Wisdom)
    assert check.dc == 10
    assert check.value == 10
    assert check.success is True or check.success is False
    assert res["advanced"] is False
    assert sess.stats["checks"] == 1
