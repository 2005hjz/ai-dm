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


def test_mock_fallback_is_scene_aware():
    """降级文案不再是一句与场景无关的固定话:至少带出当前场景名,仍不预写剧情/推进/检定。"""
    sess = start_session(new_id())
    plan = MockLLMProvider().plan(sess, "我沿着钟楼下的小巷往东走")
    assert plan.narrative
    assert "风铃镇广场" in plan.narrative
    assert plan.check is None and plan.advance_scene is None
    # 玩家动作不应当被原样搬进降级叙述
    assert "钟楼下的小巷" not in plan.narrative


def test_deepseek_retries_on_transient_failure_then_uses_real_plan(monkeypatch):
    """瞬时超时先重试,重试成功后走真实 LLM 剧本,不再静默降级成固定氛围文案。"""
    import asyncio

    import httpx

    import app.providers as p

    calls = {"n": 0}

    def flaky_call(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("first attempt timed out")
        return '{"narrative": "小巷尽头是铁匠铺,你闻到了炉火与铁锈的味道。", "check": null}'

    sess = start_session(new_id())
    provider = p.DeepSeekLLMProvider()
    monkeypatch.setattr(provider, "_call_chat", flaky_call)

    async def run():
        return await provider.plan(sess, "我沿着钟楼下的小巷往东走")

    plan = asyncio.run(run())
    assert calls["n"] == 2
    assert "铁匠铺" in plan.narrative
    assert plan.check is None


def test_deepseek_falls_back_only_after_exhausting_retries(monkeypatch):
    """重试全部失败时才降级 mock,且降级文案带当前场景名。"""
    import asyncio

    import httpx

    import app.providers as p

    sess = start_session(new_id())

    def always_fail(messages):
        raise httpx.ConnectTimeout("still down")

    provider = p.DeepSeekLLMProvider()
    monkeypatch.setattr(provider, "_call_chat", always_fail)

    async def run():
        return await provider.plan(sess, "我检查广场边的水井")

    plan = asyncio.run(run())
    assert isinstance(plan, DMPlan)
    assert "风铃镇广场" in plan.narrative
    assert plan.check is None
    assert plan.advance_scene is None


def test_narrative_stream_slice_decodes_on_the_fly():
    """流式抽取器:应把 JSON 前缀里的 narrative 逐步解码(含续界转义/换行),未闭合时给当前可见片段。"""
    from app.providers import _narrative_stream_slice

    # 完整片段:标准转义解码
    buf = '{"narrative":"雾里\\n传来一声钟响","check":null}'
    assert _narrative_stream_slice(buf) == "雾里\n传来一声钟响"

    # 未闭合:返回当前可见部分
    assert _narrative_stream_slice('{"narrative":"雾里\\n传来一') == "雾里\n传来一"

    # 转义符恰被截断在末尾(末尾单个反斜杠) → 尚未闭合,应等下一块补齐,不产生乱码
    assert _narrative_stream_slice('{"narrative":"雾里' + "\\") == "雾里"

    # narrative 尚未开始:返回空
    assert _narrative_stream_slice('{"check":null') == ""


def test_plan_stream_yields_tokens_then_plan(monkeypatch):
    """流式判决:按增量顺序产出 narrative token,最后产出完整 DMPlan;极端失败也稳定产出兜底 plan。"""
    import app.providers as p

    sess = start_session(new_id())
    provider = p.DeepSeekLLMProvider()

    async def fake_stream_chat(messages):
        deltas = ['{"narrative":"你踏上猎道。', "林间有雾。", '","check":{"skill":"感知","dc":10}}']
        for d in deltas:
            yield d

    monkeypatch.setattr(provider, "_stream_chat_async", fake_stream_chat)

    async def run():
        out_tokens = []
        plan = None
        async for kind, value in provider.plan_stream(sess, "我出发去森林"):
            if kind == "token":
                out_tokens.append(value)
            elif kind == "plan":
                plan = value
        return out_tokens, plan

    out_tokens, plan = asyncio.run(run())
    assert "".join(out_tokens).startswith("你踏上猎道。")
    assert isinstance(plan, DMPlan)
    assert plan.advance_scene is None
    assert plan.check and plan.check.dc == 10
    assert plan.narrative == "你踏上猎道。林间有雾。"
