"""FastAPI 入口:会话管理 + REST 指令 + SSE 流式 DM 剧情 + 世界大纲(SSE 进度)+ 大分支树端点。

启动:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

防御性编程落点:
- 全局异常处理(500 → 结构化 JSON,日志脱敏)
- 输入校验(safety.sanitize_input)+ 提示词防护(safety.scan_guardrails)
- 滑动窗口频控(rate_limit.SlidingWindowRateLimiter)
- LLM/生图失败自动回退 mock,主流程永不中断
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
from .models import WorldOutline
from .providers import generate_world_outline, get_image_provider, get_llm_provider, propose_or_resolve
from .rate_limit import SlidingWindowRateLimiter
from .safety import InputValidationError
from .scenario import SCENARIO

logger = logging.getLogger("ai_dm")

BASE_DIR = config.BASE_DIR
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="AI-DM · D&D 5e 单人 TRPG 智能主持", version="2.0.0")
_limiter: SlidingWindowRateLimiter | None = None


@app.on_event("startup")
async def _startup() -> None:
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowRateLimiter()
    img = get_image_provider()
    if img.name == "remote":
        asyncio.get_running_loop().create_task(_prewarm_images())


@app.exception_handler(InputValidationError)
async def _input_validation_handler(request: Request, exc: Exception) -> JSONResponse:
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
            else img.npc_portrait(entity)
            if entity in SCENARIO["npcs"]
            else ""
        )
    if entity in SCENARIO["scenes"]:
        return await asyncio.to_thread(img.scene_card, entity)
    return await asyncio.to_thread(img.npc_portrait, entity)


def _char_brief(sess) -> dict:
    p = sess.state.player
    return {
        "player": p.name,
        "race": p.race,
        "klass": p.klass,
        "background": p.background,
        "birthplace": p.birthplace,
        "level": p.level,
        "xp": p.xp,
        "hp": p.hp,
        "max_hp": p.max_hp,
        "gp": p.gp,
        "prof_bonus": p.prof_bonus,
        "abilities": {k: getattr(p.abilities, k) for k in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")},
        "skills": list(p.skills),
        "sav_throws": list(p.sav_throws),
        "spell_slots": dict(p.spell_slots),
        "spells": [s.model_dump() for s in p.spells],
        "inventory": [i.model_dump() for i in p.inventory],
    }


async def _public_session(sess) -> dict:
    """给前端用的会话快照:角色卡摘要 + 场景卡/NPC 画像。"""
    scene_id = sess.state.scene_id
    scene_name = sess.state.world.scenes.get(scene_id, {}).get("name", scene_id)
    base = _char_brief(sess)
    base.update(
        {
            "turn": sess.state.turn,
            "scene_id": scene_id,
            "phase": sess.state.phase or "",
            "npcs": [
                {
                    "id": n["npc_id"],
                    "name": n["name"],
                    "title": n.get("title", ""),
                    "relation": n.get("relation", 0),
                    "portrait": await _public_image(n["npc_id"]),
                }
                for n in sess.state.npcs.values()
            ],
            "flags": dict(sess.state.flags),
            "events": list(sess.state.events[-8:]),
        }
    )
    return {
        "id": sess.id,
        "title": sess.title,
        "scene": {"id": scene_id, "name": scene_name, "image": await _public_image(scene_id)},
        "state": base,
        "stats": dict(sess.stats),
        "providers": {"llm": get_llm_provider().name, "image": get_image_provider().name},
    }


def _sync_metrics(sess) -> None:
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
        except Exception as exc:
            logger.warning("telemetry upsert failed: %s", exc)


@app.middleware("http")
async def _rate_limit_and_error_handler(request: Request, call_next):
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


# ---------------------------------------------------------------- 静态页 & 健康检查
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


# ---------------------------------------------------------------- 世界大纲(剧本)
WORLD_STAGES = ["解析玩家描述", "构思世界观", "编排主线", "塑造NPC", "设计遭遇与场景", "合成世界大纲"]


@app.get("/api/worlds")
async def list_worlds():
    return [w.get("id") and {"id": w.id, "title": w.title, "genre": w.genre} for w in persistence.list_worlds()]


@app.post("/api/worlds")
async def create_world(payload: dict):
    """导入/自建剧本:规则文本由玩家提供,角色与剧本互不绑定。"""
    title = safety.sanitize_input((payload or {}).get("title") or "")[:40]
    setting = safety.sanitize_input((payload or {}).get("setting") or "")[:400]
    rules_text = safety.sanitize_input((payload or {}).get("rules_text") or "")[:1000]
    world = WorldOutline(id=persistence.new_id(), title=title or "自定世界", setting=setting, rules_text=rules_text)
    persistence.save_world(world)
    return world.model_dump()


@app.get("/api/worlds/{world_id}")
async def get_world(world_id: str):
    world = persistence.load_world(world_id)
    if not world:
        if world_id == "default":
            from .scenario import default_world

            world = default_world()
        else:
            raise HTTPException(404, "世界不存在")
    return world.model_dump()


@app.post("/api/worlds/generate")
async def generate_world(payload: dict):
    """SSE 流式生成世界大纲:按阶段推进度,完成后返回完整 WorldOutline。"""
    description = safety.sanitize_input((payload or {}).get("description") or "")
    rules_text = safety.sanitize_input((payload or {}).get("rules_text") or "")[:1000]

    async def gen():
        for i, stage in enumerate(WORLD_STAGES, 1):
            yield f"event: progress\ndata: {json.dumps({'step': i, 'total': len(WORLD_STAGES), 'stage': stage}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.12)
        world = await generate_world_outline(description, rules_text)
        persistence.save_world(world)
        yield f"event: done\ndata: {json.dumps({'world': world.model_dump()}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ---------------------------------------------------------------- 会话
@app.get("/api/sessions")
async def list_sessions():
    return persistence.list_sessions()


@app.post("/api/sessions")
async def create_session(payload: dict):
    player_name = safety.sanitize_input((payload or {}).get("player_name") or "")[:20]
    world_id = (payload or {}).get("world_id") or "default"
    session_id = persistence.new_id()
    sess = start_session(session_id, player_name)
    if world_id != "default":
        world = persistence.load_world(world_id)
        if world:
            sess.state.world = world
            sess.title = world.title
            for npc_id, npc in world.npcs.items():
                sess.state.npcs[npc_id] = dict(npc)
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


# ---------------------------------------------------------------- 剧本元数据(默认世界)
@app.get("/api/scenario")
async def scenario_meta():
    return {
        "id": SCENARIO["id"],
        "title": SCENARIO["title"],
        "genre": SCENARIO["genre"],
        "settings": SCENARIO["setting"],
        "mainline": SCENARIO["mainline"],
        "birthplaces": [{i + 1: k} for i, k in enumerate(SCENARIO["birthplaces"])],
        "npcs": [{"id": k, "name": v["name"], "title": v.get("title", "")} for k, v in SCENARIO["npcs"].items()],
        "scenes": [
            {"id": s["id"], "name": s["name"], "terminal": bool(s.get("is_terminal"))}
            for s in SCENARIO["scenes"].values()
        ],
        "encounters": SCENARIO["encounters"],
    }


@app.get("/api/scenario/branches")
async def scenario_branches():
    nodes = [
        {
            "id": s["id"],
            "name": s["name"],
            "terminal": bool(s.get("is_terminal")),
            "start": bool(s.get("is_start")),
        }
        for s in SCENARIO["scenes"].values()
    ]
    edges = [
        {"from": zid, "to": b["target"], "kind": "branch", "label": b["label"]}
        for zid, branches in SCENARIO["branches"].items()
        for b in branches
    ]
    return {"nodes": nodes, "edges": edges, "order": SCENARIO["scene_order"]}


@app.get("/api/images/{name}")
async def image_file(name: str):
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
    """斜杠指令(同步返回):/char /check /roll /hp /gp /inv /spells /sell /rest /scene /help /restart"""
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
    return {"session": await _public_session(updated), "new_messages": [m.model_dump() for m in updated.messages[-8:]]}


@app.post("/api/sessions/{session_id}/chat")
async def chat(session_id: str, payload: dict):
    """自由行动:SSE 流式返回 DM 叙述 + 结构化检定 + 场景推进 + 记账。"""
    sess = persistence.load_session(session_id)
    if not sess:
        raise HTTPException(404, "会话不存在")
    text = safety.sanitize_input((payload or {}).get("text", ""))
    guard = safety.scan_guardrails(text)
    _append_player_msg(sess, text)
    persistence.save_session(sess)

    async def gen():
        if guard:
            yield f"event: token\ndata: {json.dumps({'token': guard}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
            yield f"event: done\ndata: {json.dumps({'session': await _public_session(sess), 'new_messages': []}, ensure_ascii=False)}\n\n"
            return

        result = await propose_or_resolve(sess, text)
        dm_text = result["dm_text"]
        check = result.get("check")
        new_messages: list[dict] = []

        dm_msg = {
            "id": f"story-{persistence.new_id()}",
            "kind": "story",
            "role": "dm",
            "content": dm_text,
            "meta": {"scene_id": sess.state.scene_id},
        }
        sess.messages.append(_from_dict(dm_msg))
        new_messages.append(dm_msg)

        async for token in get_llm_provider().stream_text(dm_text):
            yield f"event: token\ndata: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.15)

        if check is not None:
            new_messages.append(
                {
                    "id": f"check-{persistence.new_id()}",
                    "kind": "check",
                    "role": "dm",
                    "content": check.narrative,
                    "meta": {
                        "ability": check.ability,
                        "value": check.value,
                        "modifier": check.modifier,
                        "dc": check.dc,
                        "total": check.roll.total + check.modifier,
                        "degree": check.degree,
                        "success": check.success,
                        "xp": check.xp,
                    },
                }
            )
            new_messages.append(
                {
                    "id": f"roll-{persistence.new_id()}",
                    "kind": "roll",
                    "role": "dice",
                    "content": dice_summary(check.roll),
                }
            )
            sess.messages = _append_messages(sess, new_messages[-2:])

        if result.get("advanced") and result.get("advance_dm_text"):
            adv = {
                "id": f"story-{persistence.new_id()}",
                "kind": "story",
                "role": "dm",
                "content": result["advance_dm_text"],
                "meta": {"scene_id": sess.state.scene_id},
            }
            new_messages.append(adv)
            sess.messages.append(_from_dict(adv))

        persistence.save_session(sess)
        _sync_metrics(sess)
        done = {"session": await _public_session(sess), "new_messages": new_messages, "scene_id": sess.state.scene_id}
        yield f"event: done\ndata: {json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def _from_dict(d: dict):
    from .models import Message

    return Message(**d)


def _append_messages(sess, messages: list[dict]):
    from .models import Message

    for d in messages:
        sess.messages.append(Message(**d))
    return sess.messages


def dice_summary(roll):
    from .dice import summarize

    return summarize(roll)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
