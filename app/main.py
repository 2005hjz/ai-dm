"""FastAPI 入口:会话管理 + REST 指令 + SSE 流式 DM 剧情 + 剧情分支树端点。

启动:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

防御性编程落点:
- 全局异常处理(500 → 结构化 JSON,日志脱敏)
- 输入校验(safety.sanitize_input)+ 提示词防护(safety.scan_guardrails)
- 滑动窗口频控(rate_limit.SlidingWindowRateLimiter)
- 图片生成失败回退 mock、LLM 调用失败回退 mock
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import config, persistence, safety, storage
from .gameplay import add_message, apply_command, start_session
from .providers import get_image_provider, get_llm_provider, propose_or_resolve
from .rate_limit import SlidingWindowRateLimiter
from .safety import InputValidationError
from .scenario import SCENARIO

logger = logging.getLogger("ai_dm")

BASE_DIR = config.BASE_DIR
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="AI-DM · 赛博跑团引擎", version="1.0.0")
_limiter: SlidingWindowRateLimiter | None = None  # 在启动钩子中初始化,便于测试注入


@app.on_event("startup")
async def _startup() -> None:
    global _limiter
    if _limiter is None:  # 测试可先行注入宽松限流,避免被重置
        _limiter = SlidingWindowRateLimiter()
    # 预热:远程生图在后台缓存场景卡 / NPC 头像,避免首次会话卡顿
    img = get_image_provider()
    if img.name == "remote":
        asyncio.get_running_loop().create_task(_prewarm_images())


@app.exception_handler(InputValidationError)
async def _input_validation_handler(request: Request, exc: Exception) -> JSONResponse:
    """输入校验失败 → 422 结构化错误(而非 500)。"""
    return JSONResponse({"error": str(exc)}, status_code=422)


async def _prewarm_images() -> None:
    img = get_image_provider()
    for scene_id in SCENARIO["scene_order"]:
        await asyncio.to_thread(img.scene_card, scene_id)
    for npc_id in SCENARIO["npcs"]:
        await asyncio.to_thread(img.npc_portrait, npc_id)


async def _public_image(entity: str) -> str:
    img = get_image_provider()
    if img.name == "mock":
        return (
            img.scene_card(entity)
            if entity in SCENARIO["scenes"]
            else img.npc_portrait(entity) if entity in SCENARIO["npcs"] else ""
        )
    if entity in SCENARIO["scenes"]:
        return await asyncio.to_thread(img.scene_card, entity)
    return await asyncio.to_thread(img.npc_portrait, entity)


async def _public_session(sess) -> dict:
    """给前端用的会话快照,去掉超长历史,附上场景卡/NPC 画像(异步取图)。"""
    scene_id = sess.state.scene_id
    return {
        "id": sess.id,
        "title": sess.title,
        "scene": {"id": scene_id, "name": sess.state.scene_id, "image": await _public_image(scene_id)},
        "state": {
            "player": sess.state.player.name,
            "hp": sess.state.player.hp,
            "max_hp": sess.state.player.max_hp,
            "turn": sess.state.turn,
            "scene_id": scene_id,
            "npcs": [
                {
                    "id": n["npc_id"],
                    "name": n["name"],
                    "title": n["title"],
                    "relation": n.get("relation", 0),
                    "portrait": await _public_image(n["npc_id"]),
                }
                for n in sess.state.npcs.values()
            ],
            "flags": dict(sess.state.flags),
            "events": list(sess.state.events[-6:]),
        },
        "stats": dict(sess.stats),
        "providers": {"llm": get_llm_provider().name, "image": get_image_provider().name},
    }


def _sync_metrics(sess) -> None:
    """把会话统计同步写入 SQLite 遥测(session_metrics)。"""
    if config.TELEMETRY_ENABLED:
        st = sess.state
        try:
            storage.get_store().upsert_metrics(
                sess.id,
                {
                    "player": st.player.name,
                    "scene_id": st.scene_id,
                    "rolls": sess.stats.get("rolls", 0),
                    "checks": sess.stats.get("checks", 0),
                    "passed": sess.stats.get("checks_passed", 0),
                    "failed": sess.stats.get("checks_failed", 0),
                    "big_success": sess.stats.get("big_success", 0),
                    "big_failure": sess.stats.get("big_failure", 0),
                    "turns": st.turn,
                },
                created_at=sess.created_at,
                updated_at=sess.updated_at,
            )
        except Exception as exc:  # 遥测失败不影响主流程
            logger.warning("telemetry upsert failed: %s", exc)


# ---------------------------------------------------------------- 全局中间件
@app.middleware("http")
async def _rate_limit_and_error_handler(request: Request, call_next):
    # 频控
    if _limiter is not None and request.url.path.startswith("/api"):
        key = request.client.host if request.client else "unknown"
        ok, _remaining = _limiter.allow(key)
        if not ok:
            return JSONResponse({"error": "请求过于频繁,请稍后再试"}, status_code=429)
    try:
        return await call_next(request)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("unhandled error: %s", safety.guard_log(str(exc)))
        return JSONResponse({"error": "服务内部错误,请稍后重试"}, status_code=500)


# ---------------------------------------------------------------- REST 路由
@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "llm_provider": get_llm_provider().name,
        "image_provider": get_image_provider().name,
        "version": app.version,
        "model": config.DEEPSEEK_MODEL if config.DEEPSEEK_API_KEY else "(mock)",
        "telemetry": config.TELEMETRY_ENABLED,
    }


@app.get("/api/sessions")
async def list_sessions():
    return persistence.list_sessions()


@app.post("/api/sessions")
async def create_session(payload: dict):
    player_name = (payload or {}).get("player_name") or "无名调查员"
    player_name = safety.sanitize_input(player_name)[:20]
    session_id = persistence.new_id()
    sess = start_session(session_id, player_name)
    persistence.save_session(sess)
    _sync_metrics(sess)
    return await _public_session(sess)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    sess = persistence.load_session(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    return {"session": await _public_session(sess), "messages": [m.model_dump() for m in sess.messages]}


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    if not persistence.delete_session(session_id):
        raise HTTPException(404, "会话不存在")
    return {"ok": True}


@app.get("/api/scenario")
async def scenario_meta():
    """剧本元数据:场景清单 / NPC / 技能池。"""
    return {
        "id": SCENARIO["id"],
        "title": SCENARIO["title"],
        "genre": SCENARIO["genre"],
        "skills": SCENARIO["skills"],
        "npcs": [{"id": k, "name": v["name"], "title": v.get("title", "")} for k, v in SCENARIO["npcs"].items()],
        "scenes": [{"id": s["id"], "name": s["name"], "terminal": bool(s.get("is_terminal"))} for s in SCENARIO["scenes"].values()],
    }


@app.get("/api/scenario/branches")
async def scenario_branches():
    """剧情分支树(顶点 = 场景,边 = 推进链/捷径),供前端可视化。"""
    nodes = [
        {
            "id": s["id"],
            "name": s["name"],
            "terminal": bool(s.get("is_terminal")),
            "advance_on": SCENARIO["advance_on"].get(s["id"], []),
        }
        for s in SCENARIO["scenes"].values()
    ]
    edges = [{"from": k, "to": v, "kind": "chain"} for k, v in SCENARIO["scene_chain"].items()]
    for kw, sc in SCENARIO["scene_shortcut"].items():
        edges.append({"from": "prologue", "to": sc, "kind": "shortcut", "label": kw})
    return {"nodes": nodes, "edges": edges, "order": SCENARIO["scene_order"]}


@app.get("/api/images/{name}")
async def image_file(name: str):
    """远程生图缓存文件(disk cache)访问入口。"""
    safe = "".join(c for c in name if c.isalnum() or c in "-_.")
    path = config.IMAGE_CACHE_DIR / safe
    if not path.exists():
        raise HTTPException(404, "图片不存在")
    return FileResponse(str(path), media_type="image/png")


# ---------------------------------------------------------------- 指令 / 自由行动
def _append_player_msg(sess, text: str):
    add_message(sess, "player", "player", text)
    sess.state.turn += 1


@app.post("/api/sessions/{session_id}/command")
async def command(session_id: str, payload: dict):
    """斜杠指令(同步返回):/roll /check /scene /hp /help /restart"""
    sess = persistence.load_session(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    text = safety.sanitize_input((payload or {}).get("text", ""))
    _append_player_msg(sess, text)
    updated = apply_command(sess, text)
    if updated is None:
        raise HTTPException(422, "这不是指令,请走 /chat 自由行动")
    persistence.save_session(updated)
    _sync_metrics(updated)
    return {"session": await _public_session(updated), "new_messages": [m.model_dump() for m in updated.messages[-6:]]}


@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, payload: dict):
    """自由行动:SSE 流式返回 DM 叙述 + 可能的结构化检定 + 场景推进。"""
    sess = persistence.load_session(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    text = safety.sanitize_input((payload or {}).get("text", ""))
    guard = safety.scan_guardrails(text)
    _append_player_msg(sess, text)
    persistence.save_session(sess)  # 先存玩家发言,失败也不丢现场

    async def gen():
        if guard:
            # 提示词注入 → 角色内化解,流式输出,不触发 LLM
            yield f"event: token\ndata: {json.dumps({'token': guard}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            yield f"event: done\ndata: {json.dumps({'session': await _public_session(sess), 'new_messages': []}, ensure_ascii=False)}\n\n"
            return

        result = await propose_or_resolve(sess, text)
        dm_text = result["dm_text"]
        check = result.get("check")
        advanced = result.get("advanced", False)
        advance_text = result.get("advance_dm_text", "")

        # 主叙述持久化入库(前端走 token 流渲染)
        dm_msg_dict = {
            "id": f"story-{persistence.new_id()}",
            "kind": "story",
            "role": "dm",
            "content": dm_text,
            "meta": {"scene_id": sess.state.scene_id},
        }
        sess.messages.append(_from_dict(dm_msg_dict))

        new_messages: list[dict] = []

        # 1) 流式输出 DM 主叙述
        async for token in get_llm_provider().stream_text(dm_text):
            yield f"event: token\ndata: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.15)

        # 2) 结构化检定消息
        if check is not None:
            new_messages.append(
                {
                    "id": f"check-{persistence.new_id()}",
                    "kind": "check",
                    "role": "dm",
                    "content": f"「{check.skill}检定」DC={check.dc} → {check.roll.total}",
                    "meta": {
                        "degree": check.degree,
                        "dc": check.dc,
                        "total": check.roll.total,
                        "success": check.success,
                        "skill": check.skill,
                    },
                }
            )
            new_messages.append(
                {"id": f"story-{persistence.new_id()}", "kind": "story", "role": "dm", "content": check.narrative}
            )
            new_messages.append(
                {"id": f"roll-{persistence.new_id()}", "kind": "roll", "role": "dice", "content": roll_summary(check.roll)}
            )
            sess.messages = _append_messages(sess, new_messages)

        # 3) 场景推进 → 追加入场白
        if advanced and advance_text:
            adv = {
                "id": f"story-{persistence.new_id()}",
                "kind": "story",
                "role": "dm",
                "content": advance_text,
                "meta": {"scene_id": sess.state.scene_id},
            }
            new_messages.append(adv)
            sess.messages.append(_from_dict(adv))

        persistence.save_session(sess)
        _sync_metrics(sess)
        done = {
            "session": await _public_session(sess),
            "new_messages": new_messages,
            "scene_id": sess.state.scene_id,
        }
        yield f"event: done\ndata: {json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _from_dict(d: dict):
    from .models import Message

    return Message(**d)


def _append_messages(sess, messages: list[dict]):
    from .models import Message

    for d in messages:
        sess.messages.append(Message(**d))
    return sess.messages


def roll_summary(roll):
    from .dice import summarize

    return summarize(roll)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
