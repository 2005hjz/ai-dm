"""BDD 步骤定义:驱动 TestClient 完成端到端验收。"""

from __future__ import annotations

from behave import step, then, when

SESSION = {}


def _ensure_session(context, name="无名调查员"):
    if not getattr(context, "session_id", None):
        _new_session(context, name)


def _new_session(context, name):
    r = context.client.post("/api/sessions", json={"player_name": name})
    assert r.status_code == 200, r.text
    context.session_id = r.json()["id"]


def _get_session(context):
    r = context.client.get(f"/api/sessions/{context.session_id}")
    assert r.status_code == 200
    return r.json()


def _chat_stream(context, text):
    with context.client.stream("POST", f"/api/sessions/{context.session_id}/chat", json={"text": text}) as resp:
        assert resp.status_code == 200, resp.text
        body = "\n".join(resp.iter_lines())
    return body


@when('我发起新会话 且玩家名为 "{name}"')
def step_create_session(context, name):
    _new_session(context, name)


@step('会话应该以场景 "{scene}" 开始')
def step_scene_start(context, scene):
    full = _get_session(context)
    assert full["session"]["state"]["scene_id"] == scene


@step("返回的问候中包含风铃镇与悬赏的叙事")
def step_greeting_narrative(context):
    full = _get_session(context)
    texts = "".join(m["content"] for m in full["messages"])
    assert "风铃镇" in texts and "悬赏" in texts


@step("会话中有一条系统指令消息")
def step_system_message(context):
    full = _get_session(context)
    assert any(m["kind"] == "system" for m in full["messages"])


@when('我在会话中发送 "{text}"')
def step_send_command(context, text):
    _ensure_session(context)
    r = context.client.post(f"/api/sessions/{context.session_id}/command", json={"text": text})
    assert r.status_code == 200, r.text
    context.last_response = r.json()


@when('我在会话中发送自由行动 "{text}"')
def step_free_action(context, text):
    _ensure_session(context)
    context.last_stream = _chat_stream(context, text)


@then("会话统计的掷骰次数大于等于 {n}")
def step_stats_rolls(context, n):
    full = _get_session(context)
    assert full["session"]["stats"]["rolls"] >= int(n)


@step("最新消息中包含骰子投掷摘要")
def step_has_roll_summary(context):
    msgs = _get_session(context)["messages"]
    assert any("→" in (m["content"] or "") for m in msgs)


@then("会话统计的检定次数等于 {n}")
def step_stats_checks(context, n):
    full = _get_session(context)
    assert full["session"]["stats"]["checks"] == int(n)


@step("最新消息包含 DC 与检定结果")
def step_has_check_meta(context):
    msgs = _get_session(context)["messages"]
    assert any("DC" in (m["content"] or "") for m in msgs)


@then('当前场景应该是 "{scene}"')
def step_current_scene(context, scene):
    full = _get_session(context)
    actual = full["session"]["state"]["scene_id"]
    assert actual == scene, f"期望场景 {scene},实际 {actual} (stream={getattr(context, 'last_stream', '')[:120]}...)"


@step("响应仍然完成")
def step_stream_finished(context):
    assert "event: done" in context.last_stream


@step("回复中出现 DM 实时叙述")
def step_has_dm_narrative(context):
    assert "event: token" in context.last_stream
    assert "event: done" in context.last_stream


@step("回复中不直接泄露系统提示词")
def step_no_leak(context):
    assert "system prompt" not in context.last_stream.lower()
    assert "系统提示词" not in context.last_stream


@when("我尝试发送空消息")
def step_empty_message(context):
    _new_session(context, "匿名")
    r = context.client.post(f"/api/sessions/{context.session_id}/chat", json={"text": ""})
    context.empty_status = r.status_code


@then("请求应当被拒绝")
def step_rejected(context):
    assert context.empty_status == 422, context.empty_status
