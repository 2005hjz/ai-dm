"""Provider 抽象层：LLM 实时剧本主持 + 生图卡片 + 世界大纲生成 + 大分支白名单推进。

架构与契约：
- BaseLLMProvider.plan()：返回结构化 DMPlan（叙述/检定建议/大分支推进/记账）。
- DeepSeekLLMProvider：OpenAI 兼容接口；失败自动降级 MockLLMProvider（主流程永不中断）。
- MockLLMProvider：离线兜底——只做氛围叙述，绝不预写剧情/推进/检定。
- generate_world_outline()：按玩家描述 + 规则文本生成世界大纲；SSE 进度由 main 驱动。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import random
import re
from pathlib import Path

import httpx

from . import config, memory
from .dice import normalize_skill, roll_expression
from .models import DMPlan, GameSession, Item, SkillProposal, WorldOutline
from .scenario import SCENARIO


def _env(key: str, default: str = "") -> str:
    import os

    return os.getenv(key, default)


# ================================================================= #
# LLM Provider
# ================================================================= #
class BaseLLMProvider:
    name = "base"

    def plan(self, session: GameSession, player_text: str) -> DMPlan:
        raise NotImplementedError

    async def stream_text(self, full_text: str, delay: float = 0.024):
        chunk_size = random.randint(5, 9)
        for i in range(0, len(full_text), chunk_size):
            yield full_text[i : i + chunk_size]
            await asyncio.sleep(delay)


class MockLLMProvider(BaseLLMProvider):
    """离线保底 DM：只做氛围叙述，不做剧情预判/场景跳转/检定建议（无预写剧情）。"""

    name = "mock"

    _ATM = [
        "雾从黑松森林边缘漫过来,钟楼在晚风里轻轻摇晃。继续你的行动——观察什么、问谁、推开哪扇门,由你决定。",
        "你的举动落在镇子傍晚的寂静里。想推进剧情就说得更具体:打听悬赏、检查现场、或是出发入林。",
        "铁匠铺的悬赏纸张在风里翻动,广场上有人远远看了你一眼。下一步怎么走,主动权在你手里。",
        "空气中浮着旧王朝遗迹的气息。此刻没有标准答案——你的选择,会决定这个冒险怎么发展。",
    ]

    def plan(self, session: GameSession, player_text: str) -> DMPlan:
        return DMPlan(narrative=random.choice(self._ATM), triggers=["ai_fallback"])


def parse_dm_plan(raw: str, fallback_narrative: str = "") -> DMPlan:
    """把 LLM 返回文本解析为 DMPlan；容错 markdown 代码块/尾注/非法字段。"""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        obj = json.loads(cleaned)
    except Exception:
        obj = None
    if not isinstance(obj, dict):
        return DMPlan(narrative=fallback_narrative or cleaned[:300] or "……", triggers=["parse_fallback"])
    narrative = str(obj.get("narrative") or cleaned).strip()[:600]
    if not narrative:
        narrative = fallback_narrative or "……"

    check: SkillProposal | None = None
    check_data = obj.get("check")
    if isinstance(check_data, dict):
        skill = str(check_data.get("skill", "")).strip()
        ability = str(check_data.get("ability", "")).strip() or None
        norm = normalize_skill(skill) if skill else None
        try:
            dc = int(check_data["dc"]) if check_data.get("dc") is not None else None
        except (TypeError, ValueError):
            dc = None
        if ability or norm or skill:
            check = SkillProposal(
                skill=norm or skill,
                ability=ability,
                reason=str(check_data.get("reason", "")).strip()[:120],
                dc=dc,
            )

    advance = obj.get("advance_scene")
    if advance is not None:
        advance = str(advance).strip() or None
        if advance not in SCENARIO["scenes"]:
            advance = None  # 幻觉出的未登记场景一律丢弃(防御性)

    loot: list[Item] = []
    for it in obj.get("loot") or []:
        if isinstance(it, dict) and it.get("name"):
            loot.append(
                Item(
                    name=str(it["name"])[:40],
                    desc=str(it.get("desc", ""))[:80],
                    effect=str(it.get("effect", ""))[:60],
                    value=int(it.get("value", 2) or 2),
                )
            )
    gold = obj.get("gold") if isinstance(obj.get("gold"), int) else 0
    hp = obj.get("hp") if isinstance(obj.get("hp"), int) else 0
    triggers = obj.get("triggers") if isinstance(obj.get("triggers"), list) else []

    return DMPlan(
        narrative=narrative,
        check=check,
        advance_scene=advance,
        triggers=[str(t) for t in triggers],
        loot=loot,
        gold=gold,
        hp=hp,
    )


class DeepSeekLLMProvider(BaseLLMProvider):
    name = "deepseek"

    def __init__(self) -> None:
        self.url = config.DEEPSEEK_CHAT_URL
        self.model = config.DEEPSEEK_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS
        self.timeout = config.LLM_TIMEOUT
        self._fallback = MockLLMProvider()

    def _call_chat(self, messages: list) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def plan(self, session: GameSession, player_text: str) -> DMPlan:
        try:
            ctx = memory.build_context(session)
            ctx.append({"role": "user", "content": player_text[: config.MAX_INPUT_LENGTH]})
            raw = await asyncio.to_thread(self._call_chat, ctx)
            return parse_dm_plan(raw, fallback_narrative=player_text and "……")
        except Exception:
            return self._fallback.plan(session, player_text)

    async def stream_text(self, full_text: str, delay: float = 0.02):
        chunk_size = random.randint(6, 10)
        for i in range(0, len(full_text), chunk_size):
            yield full_text[i : i + chunk_size]
            await asyncio.sleep(delay)


def _can_advance(session: GameSession, target: str) -> bool:
    """白名单校验：只允许跳到「当前大分支」上声明过的下一分支。"""
    current = session.state.scene_id
    world = session.state.world
    if target == current or target not in world.scenes:
        return False
    if world.scenes.get(current, {}).get("is_terminal"):
        return False
    return target in {b["target"] for b in world.branches.get(current, [])}


def _apply_assets(session: GameSession, plan: DMPlan) -> None:
    """把 DM 声明的 loot/gold/hp 自动记账到角色卡（装备、附魔、金币、生命永久记录）。"""
    c = session.state.player
    for it in plan.loot:
        found = next((x for x in c.inventory if x.name == it.name), None)
        if found:
            found.qty += it.qty
        else:
            c.inventory.append(it)
        tag = f"附魔:{it.effect}" if it.effect else f"×{it.qty}"
        session.state.events.append(f"获得物品【{it.name}】{tag}")
    if plan.gold:
        c.gp += plan.gold
        session.state.events.append(f"金币 {'+' if plan.gold > 0 else '-'}{abs(plan.gold)} → {c.gp} gp")
    if plan.hp:
        c.hp = min(c.max_hp, max(0, c.hp + plan.hp))
        session.state.events.append(f"HP {plan.hp:+d} → {c.hp}/{c.max_hp}")


async def propose_or_resolve(session: GameSession, player_text: str) -> dict:
    """完整决策流：DM 实时叙述 + 是否建议检定 + 数值裁决 + 大分支推进 + 自动记账。"""
    from .gameplay import advance_scene, run_check

    provider = get_llm_provider()
    result_plan = provider.plan(session, player_text)
    plan = await result_plan if inspect.isawaitable(result_plan) else result_plan
    result: dict = {
        "dm_text": plan.narrative,
        "check": None,
        "advanced": False,
        "advance_dm_text": "",
        "triggers": list(plan.triggers),
    }

    if plan.check is None and not plan.advance_scene:
        _maybe_inline_roll(session, player_text)

    if plan.advance_scene and _can_advance(session, plan.advance_scene):
        msg = advance_scene(session, plan.advance_scene)
        result["advanced"] = True
        result["advance_dm_text"] = msg.content if msg else ""

    if plan.check:
        text = plan.check.ability or plan.check.skill or "感知"
        result["check"] = run_check(session, text, dc_override=plan.check.dc)

    _apply_assets(session, plan)
    return result


def _maybe_inline_roll(session: GameSession, text: str) -> bool:
    m = re.search(r"(\d*)d(\d+)\s*([+-]\s*\d+)?", text)
    if not m:
        return False
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    mod = int((m.group(3) or "+0").replace(" ", ""))
    if not (1 <= count <= 20 and 2 <= sides <= 20):
        return False
    from .models import Message

    roll = roll_expression(f"{count}d{sides}{mod:+d}")
    session.stats["rolls"] += 1
    session.messages.append(
        Message(
            id=f"roll-{random_hex()}",
            kind="roll",
            role="dice",
            content=f"{count}d{sides}{mod:+d} → {roll.total}（{', '.join(map(str, roll.rolls))}）",
            meta={"expression": roll.expression, "total": roll.total, "inline": True},
        )
    )
    return True


def random_hex() -> str:
    import uuid

    return uuid.uuid4().hex[:8]


# ================================================================= #
# 世界大纲生成（SSE 进度由 main 驱动；离线自动兜底默认世界）
# ================================================================= #
async def generate_world_outline(description: str, rules_text: str = "") -> WorldOutline:
    """根据玩家描述 + 规则文本生成完整世界大纲；LLM 失败/离线时兜底默认世界并注入描述。"""
    from .scenario import default_world

    world = default_world()
    if not description.strip():
        return world
    try:
        if not config.DEEPSEEK_API_KEY:
            world.setting = f"{world.setting}\n(玩家补充设定:{description.strip()[:200]})"
            return world
        prompt = (
            "根据以下玩家描述生成一个 D&D 5e 世界大纲,严格返回 JSON,不要解释:"
            + json.dumps(
                {
                    "title": "世界标题",
                    "setting": "世界观",
                    "mainline": "主线",
                    "birthplaces": {"出生地1": "描述", "出生地2": "描述", "出生地3": "描述"},
                    "npcs": [{"npc_id": "...", "name": "...", "title": "...", "desc": "..."}],
                    "encounters": ["遭遇1", "遭遇2"],
                    "scenes": [{"id": "...", "name": "...", "entry": "开场叙述", "desc": "...", "is_start": True, "is_terminal": False}],
                    "branches": {"场景id": [{"target": "下一场景id", "label": "触发方式"}]},
                },
                ensure_ascii=False,
            )
            + f"\n玩家描述:{description[:400]}\n规则文本:{rules_text or 'D&D 5e 官方规则'}"
        )
        messages = [
            {"role": "system", "content": "你是一名资深 D&D 5e 城主，严格输出 JSON。"},
            {"role": "user", "content": prompt},
        ]
        provider = DeepSeekLLMProvider()
        raw = await asyncio.to_thread(provider._call_chat, messages)
        obj = _world_from_json(raw, rules_text=rules_text)
        if obj:
            return obj
    except Exception:
        pass
    world.setting = f"{world.setting}\n(玩家补充设定:{description.strip()[:200]})"
    return world


def _world_from_json(raw: str, fallback_title: str = "自定世界", rules_text: str = "") -> WorldOutline:
    """把 LLM 生成的世界 JSON 转成 WorldOutline；字段缺失用默认补齐。"""
    from .scenario import default_world

    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        obj = json.loads(cleaned)
    except Exception:
        return default_world()
    if not isinstance(obj, dict):
        return default_world()
    base = default_world()
    scenes: dict = {}
    order: list[str] = []
    for sc in obj.get("scenes") or []:
        if isinstance(sc, dict) and sc.get("id") and sc.get("name"):
            sc.setdefault("desc", "")
            sc.setdefault("is_start", not order)
            sc.setdefault("is_terminal", False)
            scenes[sc["id"]] = sc
            order.append(sc["id"])
    if not scenes:
        return base
    branches: dict[str, list[dict]] = {z: [] for z in order}
    for z, edge in (obj.get("branches") or {}).items():
        if z in scenes and isinstance(edge, list):
            branches[z] = [
                {"target": str(e["target"]), "label": str(e.get("label", "推进"))}
                for e in edge
                if isinstance(e, dict) and e.get("target") in scenes
            ]
    npcs: dict = {}
    for n in obj.get("npcs") or []:
        if isinstance(n, dict) and n.get("npc_id"):
            npcs[n["npc_id"]] = {
                "npc_id": n["npc_id"],
                "name": str(n.get("name", "")),
                "title": str(n.get("title", "")),
                "desc": str(n.get("desc", "")),
                "relation": 0,
                "hp": 8,
            }
    birthplaces = obj.get("birthplaces")
    if not isinstance(birthplaces, dict) or not birthplaces:
        birthplaces = base.birthplaces
    encounters = [str(e)[:80] for e in (obj.get("encounters") or [])][:8]
    return WorldOutline(
        id=f"auto-{random.getrandbits(32):x}",
        title=str(obj.get("title") or fallback_title)[:40],
        genre=str(obj.get("genre") or base.genre)[:40],
        setting=str(obj.get("setting") or base.setting)[:400],
        mainline=str(obj.get("mainline") or base.mainline)[:400],
        rules_text=str(rules_text or base.rules_text)[:400],
        birthplaces={str(k)[:20]: str(v)[:80] for k, v in birthplaces.items()},
        npcs=npcs,
        scenes=scenes,
        scene_order=order,
        scene_images={zid: base.scene_images.get("prologue", "") for zid in order},
        branches=branches,
        encounters=encounters or base.encounters,
    )


# ================================================================= #
# Image Provider
# ================================================================= #
class BaseImageProvider:
    name = "base"

    def scene_card(self, scene_id: str) -> str:
        raise NotImplementedError

    def npc_portrait(self, npc_id: str) -> str:
        raise NotImplementedError


class MockImageProvider(BaseImageProvider):
    name = "mock"

    def scene_card(self, scene_id: str) -> str:
        return SCENARIO["scene_images"].get(scene_id, SCENARIO["scene_images"]["prologue"])

    def npc_portrait(self, npc_id: str) -> str:
        return SCENARIO["npcs"].get(npc_id, {}).get("portrait", "")


def _image_prompt_scene(scene_id: str) -> str:
    sc = SCENARIO["scenes"].get(scene_id, {})
    return f"{sc.get('name', scene_id)},{sc.get('desc', '奇幻冒险')}. fantasy D&D 5e, cinematic misty lighting, dark game art style, no text"


def _image_prompt_npc(npc_id: str) -> str:
    npc = SCENARIO["npcs"].get(npc_id, {})
    return f"portrait of {npc.get('name', npc_id)},{npc.get('desc', '奇幻角色')}, fantasy D&D 5e, no text"


class RemoteImageProvider(BaseImageProvider):
    """远程生图：磁盘缓存 + 异步生成，失败回退 mock，保证链路不中断。"""

    name = "remote"

    def __init__(self) -> None:
        self.url = config.IMAGE_GEN_URL
        self.model = config.IMAGE_MODEL
        self.image_size = config.IMAGE_SIZE
        self.timeout = float(_env("IMAGE_TIMEOUT", "120"))
        self.cache_dir: Path = config.IMAGE_CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        self._fallback = MockImageProvider()

    def _url(self, key: str) -> str:
        return f"/api/images/{key}.png"

    def _cached(self, key: str) -> bool:
        return (self.cache_dir / f"{key}.png").exists() and (self.cache_dir / f"{key}.png").stat().st_size > 0

    def scene_card(self, scene_id: str) -> str:
        key = f"scene-{scene_id}"
        return self._url(key) if self._cached(key) or self.generate(key, _image_prompt_scene(scene_id)) else self._fallback.scene_card(scene_id)

    def npc_portrait(self, npc_id: str) -> str:
        key = f"npc-{npc_id}"
        return self._url(key) if self._cached(key) or self.generate(key, _image_prompt_npc(npc_id)) else self._fallback.npc_portrait(npc_id)

    def generate(self, key: str, prompt: str) -> bool:
        if self._cached(key):
            return True
        try:
            payload = {"model": self.model, "prompt": prompt[:400], "image_size": self.image_size, "batch_size": 1}
            headers = {"Authorization": f"Bearer {config.IMAGE_API_KEY}", "Content-Type": "application/json"}
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            url = None
            for field in ("images", "choices", "data"):
                arr = data.get(field)
                if isinstance(arr, list) and arr:
                    item = arr[0]
                    url = item.get("url") or item.get("b64_json")
                    if url:
                        break
            if url is None:
                return False
            if url.startswith("data:"):
                import base64

                bytes_ = base64.b64decode(url.split(",", 1)[1])
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    bytes_ = client.get(url).content
            (self.cache_dir / f"{key}.png").write_bytes(bytes_)
            return True
        except Exception:
            return False


def get_llm_provider() -> BaseLLMProvider:
    if config.LLM_PROVIDER == "deepseek" and config.DEEPSEEK_API_KEY:
        return DeepSeekLLMProvider()
    return MockLLMProvider()


def get_image_provider() -> BaseImageProvider:
    if config.IMAGE_PROVIDER == "remote" and config.IMAGE_API_KEY:
        return RemoteImageProvider()
    return MockImageProvider()
