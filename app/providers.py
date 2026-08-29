"""Provider 抽象层：LLM 实时剧本主持 + 生图卡片 + 剧情分支判决。

架构：
- BaseLLMProvider        ：统一决策入口，返回结构化 DMPlan（Pydantic 数值检定契约）。
- DeepSeekLLMProvider    ：OpenAI 兼容接口（DeepSeek 官方 / 硅基流动 deepseek-ai/DeepSeek-V4-Flash），
                           由模型按玩家自由指令**实时判决**剧情推进与检定建议；调用失败自动降级 mock。
- MockLLMProvider        ：离线保底。只做氛围兜底叙述，**不预写任何剧情台词/推进判断**——
                           保证无 Key 时全链路可跑，但真正的剧情演进必须由真实 LLM 完成。
- MockImageProvider      ：本地 SVG 生成场景卡 / NPC 画像（data URL）。
- RemoteImageProvider    ：远程生图 API，异步生成 + 磁盘缓存，失败回退 mock。
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path

import httpx

from . import config, memory
from .dice import normalize_skill, roll_expression
from .models import DMPlan, GameSession, SkillProposal
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
        """决策入口：返回结构化 DMPlan。真实实现为 LLM 调用 + JSON 契约解析。"""
        raise NotImplementedError

    async def stream_text(self, full_text: str, delay: float = 0.024):
        """把完整文本切成小块异步流出（SSE token 流）。"""
        chunk_size = random.randint(5, 9)
        for i in range(0, len(full_text), chunk_size):
            yield full_text[i : i + chunk_size]
            await asyncio.sleep(delay)


class MockLLMProvider(BaseLLMProvider):
    """离线保底 DM：只给氛围叙述，不做剧情预判/场景跳转/检定建议。"""

    name = "mock"

    _ATM = [
        "雾气在昏黄的灯光里缓慢游动。你感到这里的每一寸都被刻意藏起了什么——继续你的行动，剩下的交给雾和你自己。",
        "你的举动在空旷的静默里落了下去。想推进真相，可以描述得更具体：观察什么、问谁、打开哪扇门。",
        "空气里浮着潮湿的霉味。你感觉到一种被注视的重量，像有什么东西在雾里安静地等你下一步动作。",
        "你站在原地想了想。此刻没有绝对的答案——你的选择会决定雾里故事的走向。",
    ]

    def plan(self, session: GameSession, player_text: str) -> DMPlan:
        return DMPlan(narrative=random.choice(self._ATM), triggers=["ai_fallback"])


def parse_dm_plan(raw: str, fallback_narrative: str = "") -> DMPlan:
    """把 LLM 返回文本解析为 DMPlan；容错处理 markdown 代码块 / 尾注 / 非法字段。"""
    cleaned = raw.strip()
    cleaned = re_strip_fence(cleaned)
    try:
        obj = json.loads(cleaned)
    except Exception:
        obj = None
    if not isinstance(obj, dict):
        return DMPlan(narrative=fallback_narrative or cleaned[:300] or "……", triggers=["parse_fallback"])
    narrative = str(obj.get("narrative") or cleaned).strip()[:600]
    if not narrative:
        narrative = fallback_narrative or "……"
    check_data = obj.get("check")
    check: SkillProposal | None = None
    if isinstance(check_data, dict):
        skill = str(check_data.get("skill", "")).strip()
        norm = normalize_skill(skill)
        if norm or skill:
            try:
                dc = int(check_data.get("dc")) if check_data.get("dc") is not None else None
            except (TypeError, ValueError):
                dc = None
            check = SkillProposal(
                skill=norm or skill,
                reason=str(check_data.get("reason", "")).strip()[:120],
                dc=dc,
            )
    advance = obj.get("advance_scene")
    if advance is not None:
        advance = str(advance).strip()
        if advance not in SCENARIO["scenes"]:
            advance = None
    triggers = obj.get("triggers") if isinstance(obj.get("triggers"), list) else []
    return DMPlan(narrative=narrative, check=check, advance_scene=advance, triggers=[str(t) for t in triggers])


def re_strip_fence(text: str) -> str:
    import re

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*$", "", text)
    return text.strip()


class DeepSeekLLMProvider(BaseLLMProvider):
    name = "deepseek"

    def __init__(self) -> None:
        self.url = config.DEEPSEEK_CHAT_URL
        self.model = config.DEEPSEEK_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS
        self.timeout = config.LLM_TIMEOUT
        self._fallback = MockLLMProvider()

    # -- 同步 HTTP 调用，外层用 asyncio.to_thread 包住，避免阻塞事件循环 --
    def _call_chat(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def plan(self, session: GameSession, player_text: str) -> DMPlan:
        """真实 LLM 实时判决 + Pydantic 结构化检定契约；失败自动降级 mock。"""
        try:
            ctx = memory.build_context(session)
            ctx.append({"role": "user", "content": player_text[: config.MAX_INPUT_LENGTH]})
            raw = await asyncio.to_thread(self._call_chat, ctx)
            return parse_dm_plan(raw, fallback_narrative=player_text and "……")
        except Exception:
            # 防御性降级：任何网络/解析失败都回退到离线 DM，保证流程不中断
            return self._fallback.plan(session, player_text)

    async def stream_text(self, full_text: str, delay: float = 0.02):
        chunk_size = random.randint(6, 10)
        for i in range(0, len(full_text), chunk_size):
            yield full_text[i : i + chunk_size]
            await asyncio.sleep(delay)


def _can_advance(session: GameSession, target: str) -> bool:
    """白名单校验：只允许跳到「当前大剧情分支」上声明过的下一分支。"""
    current = session.state.scene_id
    trunk = SCENARIO["scenes"]
    if target == current or target not in trunk:
        return False
    if trunk.get(current, {}).get("is_terminal"):
        return False
    declared = {b["target"] for b in SCENARIO["branches"].get(current, [])}
    return target in declared


async def propose_or_resolve(session: GameSession, player_text: str) -> dict:
    """完整决策流：DM 实时叙述 + 是否建议检定 + 数值裁决 + 大分支推进。

    引擎只负责「骰子裁决」与「白名单推进」；剧情方向完全由 LLM 当轮判决。
    """
    from .gameplay import run_check

    provider = get_llm_provider()
    plan = provider.plan(session, player_text)
    result: dict = {
        "dm_text": plan.narrative,
        "check": None,
        "advanced": False,
        "advance_dm_text": "",
        "triggers": list(plan.triggers),
    }

    # 玩家话里带骰子表达式 → 自动执行自由掷骰展示
    if plan.check is None and not plan.advance_scene:
        _maybe_inline_roll(session, player_text)

    # 1) LLM 明确指向某个大剧情分支（引擎做白名单校验后推进）
    if plan.advance_scene and _can_advance(session, plan.advance_scene):
        sess_scene = SCENARIO["scenes"][plan.advance_scene]
        session.state.scene_id = plan.advance_scene
        session.state.events.append(f"推进到「{sess_scene['name']}」大分支")
        result["advanced"] = True
        result["advance_dm_text"] = sess_scene.get("entry", "")

    # 2) LLM 建议检定 → 引擎负责结构化数值裁决（成功与否都不由引擎强行推剧情）
    if plan.check:
        res = run_check(session, plan.check.skill, dc_override=plan.check.dc)
        result["check"] = res
    return result


def _maybe_inline_roll(session: GameSession, text: str) -> bool:
    import re
    import uuid

    from .models import Message

    m = re.search(r"(\d*)[dD](\d+)([+-]\s*\d+)?", text)
    if not m:
        return False
    count = int(m.group(1) or 1)
    sides = int(m.group(2))
    mod = int((m.group(3) or "+0").replace(" ", ""))
    if not (1 <= count <= 20 and 2 <= sides <= 20):
        return False
    roll = roll_expression(f"{count}d{sides}{mod:+d}")
    session.stats["rolls"] += 1
    session.messages.append(
        Message(
            id=f"roll-{uuid.uuid4().hex[:8]}",
            kind="roll",
            role="dice",
            content=f"{count}d{sides}{mod:+d} → {roll.total}（{', '.join(map(str, roll.rolls))}）",
            meta={"expression": roll.expression, "total": roll.total, "inline": True},
        )
    )
    return True


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
        return SCENARIO["scene_images"].get(scene_id, SCENARIO["scene_images"]["hallway"])

    def npc_portrait(self, npc_id: str) -> str:
        npc = SCENARIO["npcs"].get(npc_id, {})
        return npc.get("portrait", "")


def _image_prompt_scene(scene_id: str) -> str:
    sc = SCENARIO["scenes"].get(scene_id, {})
    return f"{sc.get('name', scene_id)},{sc.get('desc', '悬疑微恐怖氛围')}. cinematic misty lighting, dark mystery game art style, no text"


def _image_prompt_npc(npc_id: str) -> str:
    npc = SCENARIO["npcs"].get(npc_id, {})
    return f"portrait of {npc.get('name', npc_id)}, {npc.get('desc', '孤寂诡异氛围')}, dark mystery game art style, no text"


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

    @staticmethod
    def _url(key: str) -> str:
        return f"/api/images/{key}.png"

    def scene_card(self, scene_id: str) -> str:
        key = f"scene-{scene_id}"
        if self._cached(key):
            return self._url(key)
        ok = self.generate(key, _image_prompt_scene(scene_id))
        return self._url(key) if ok else self._fallback.scene_card(scene_id)

    def npc_portrait(self, npc_id: str) -> str:
        key = f"npc-{npc_id}"
        if self._cached(key):
            return self._url(key)
        ok = self.generate(key, _image_prompt_npc(npc_id))
        return self._url(key) if ok else self._fallback.npc_portrait(npc_id)

    def _cached(self, key: str) -> bool:
        return (self.cache_dir / f"{key}.png").exists() and (self.cache_dir / f"{key}.png").stat().st_size > 0

    def generate(self, key: str, prompt: str) -> bool:
        """同步生成并落盘缓存（png）。结构：{images:[{url}], choices:[{url}], data:[{url}]} 兼容多形态。"""
        if self._cached(key):
            return True
        try:
            payload = {
                "model": self.model,
                "prompt": prompt[:400],
                "image_size": self.image_size,
                "batch_size": 1,
            }
            headers = {
                "Authorization": f"Bearer {config.IMAGE_API_KEY}",
                "Content-Type": "application/json",
            }
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

                b64 = url.split(",", 1)[1]
                bytes_ = base64.b64decode(b64)
            else:
                with httpx.Client(timeout=self.timeout) as client:
                    bytes_ = client.get(url).content
            (self.cache_dir / f"{key}.png").write_bytes(bytes_)
            return True
        except Exception:
            return False


# ================================================================= #
# Factory
# ================================================================= #
def get_llm_provider() -> BaseLLMProvider:
    if config.LLM_PROVIDER == "deepseek" and config.DEEPSEEK_API_KEY:
        return DeepSeekLLMProvider()
    return MockLLMProvider()


def get_image_provider() -> BaseImageProvider:
    if config.IMAGE_PROVIDER == "remote" and config.IMAGE_API_KEY:
        return RemoteImageProvider()
    return MockImageProvider()
