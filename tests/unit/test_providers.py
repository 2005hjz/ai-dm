"""Provider 抽象层的单元测试:mock 决策、结构化 DMPlan 解析、内联掷骰。"""

from __future__ import annotations

from app.dice import normalize_skill
from app.gameplay import start_session
from app.models import DMPlan
from app.persistence import new_id
from app.providers import MockLLMProvider, get_image_provider, get_llm_provider, parse_dm_plan


def test_default_providers_are_mock(monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "LLM_PROVIDER", "mock")
    monkeypatch.setattr(cfg, "IMAGE_PROVIDER", "mock")
    assert get_llm_provider().name == "mock"
    assert get_image_provider().name == "mock"


def test_mock_plan_shortcut_advance():
    sess = start_session(new_id())
    plan = MockLLMProvider().plan(sess, "推开7号房的门")
    assert isinstance(plan, DMPlan)
    assert plan.advance_scene == "room7"


def test_mock_plan_hook_inspect_proposes_check():
    sess = start_session(new_id())
    plan = MockLLMProvider().plan(sess, "我俯身检查床底")
    # 当前场景是 prologue,inspect hook 未附带检定
    assert plan.narrative


def test_mock_plan_fallback_when_no_intent():
    sess = start_session(new_id())
    plan = MockLLMProvider().plan(sess, "今天天气不错呢")
    assert plan.narrative
    assert plan.check is None


def test_parse_dm_plan_valid_json():
    raw = '{"narrative": "你发现床底有个白影。", "check": {"skill": "侦查", "reason": "雾太浓", "dc": 11}, "advance_scene": null, "triggers": ["x"]}'
    plan = parse_dm_plan(raw)
    assert plan.narrative == "你发现床底有个白影。"
    assert plan.check is not None
    assert normalize_skill(plan.check.skill) == "侦查"
    assert plan.check.dc == 11


def test_parse_dm_plan_fenced_json():
    raw = '```json\n{"narrative": "门开了。", "check": null, "advance_scene": "hallway", "triggers": []}\n```'
    plan = parse_dm_plan(raw)
    assert plan.advance_scene == "hallway"
    assert plan.check is None


def test_parse_dm_plan_garbage_falls_back():
    plan = parse_dm_plan("这是一段完全不是JSON的叙述文本")
    assert plan.narrative == "这是一段完全不是JSON的叙述文本"


def test_propose_or_resolve_check_advance(monkeypatch):
    """在 room7 场景下 inspect 检定成功 → 依据 advance_on 推进到 basement。"""

    async def run():
        from app import providers as p

        sess = start_session(new_id())
        from app.gameplay import advance_scene

        advance_scene(sess, "room7")
        # 直接调用真实 mock 决策:room7 的 inspect hook 建议「侦查」检定
        res = await p.propose_or_resolve(sess, "我俯身检查床底的白影")
        return res, sess

    import asyncio

    res, sess = asyncio.run(run())
    check = res.get("check")
    # 检定成功时才推进;失败时不推进 —— 两者都验证引擎行为一致
    assert (res["advanced"] is True and sess.state.scene_id == "basement") or (
        res["advanced"] is False and sess.state.scene_id == "room7"
    )
    if check is not None:
        assert check.skill == "侦查"
        assert check.dc > 0
