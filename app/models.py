"""Pydantic 核心数据模型：D&D 5e 角色卡 / 剧本世界 / 骰子与检定（结构化数值契约）。"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class AbilityScores(BaseModel):
    """D&D 5e 六维属性。"""

    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10


class Item(BaseModel):
    """一件真实记录在案的物品；effect 为附魔描述（如「火焰+1d4伤害」）。"""

    name: str
    desc: str = ""
    effect: str = ""
    qty: int = 1
    value: int = 2  # 金币估价 gp
    equipped: bool = False


class Spell(BaseModel):
    """法术：0 级=戏法，1-9 级需法术位。"""

    name: str
    level: int = 0
    desc: str = ""
    prepared: bool = False


class Character(BaseModel):
    """D&D 5e 玩家角色卡：属性/职业升级/经验/金钱/法术位/背包全部结构化。"""

    name: str = "无名冒险者"
    race: str = ""
    klass: str = ""
    background: str = ""
    level: int = 1
    xp: int = 0
    hp: int = 10
    max_hp: int = 10
    gp: int = 10
    birthplace: str = ""
    abilities: AbilityScores = Field(default_factory=AbilityScores)
    prof_bonus: int = 2
    skills: list[str] = Field(default_factory=list)  # 熟练技能
    sav_throws: list[str] = Field(default_factory=list)  # 熟练豁免(属性中文名)
    spells: list[Spell] = Field(default_factory=list)
    spell_slots: dict[int, int] = Field(default_factory=dict)  # {法术环: 剩余位}
    inventory: list[Item] = Field(default_factory=list)


class WorldOutline(BaseModel):
    """剧本（世界大纲）：与角色互不绑定，玩家可提供规则文本，DM 据此主持。"""

    id: str = "default"
    title: str = "未命名世界"
    genre: str = "奇幻 · 剑与魔法"
    setting: str = ""  # 世界观
    mainline: str = ""  # 主线
    rules_text: str = ""  # 玩家提供的规则文本（D&D 5e 缺省）
    birthplaces: dict[str, str] = Field(default_factory=dict)  # 出生地: 描述
    npcs: dict[str, Any] = Field(default_factory=dict)
    scenes: dict[str, Any] = Field(default_factory=dict)  # 大分支 zone
    scene_order: list[str] = Field(default_factory=list)
    scene_images: dict[str, str] = Field(default_factory=dict)
    branches: dict[str, list[dict]] = Field(default_factory=dict)  # {zone: [{target,label}]}
    encounters: list[str] = Field(default_factory=list)


class DiceRoll(BaseModel):
    """一次骰子投掷的完整记录（AI 代投）。"""

    expression: str
    count: int
    sides: int
    modifier: int
    rolls: list[int] = Field(default_factory=list)
    total: int


class CheckResult(BaseModel):
    """一次 d20 属性检定结果：显式展示能力名/属性值/加值/DC，方便玩家判断。"""

    ability: str  # 中文能力名，如 感知
    value: int  # 属性值
    modifier: int  # 属性修正(+熟练加值)
    proficient: bool = False
    dc: int
    advice: str = "普通"  # 优势/劣势/普通
    roll: DiceRoll
    success: bool
    margin: int
    degree: str = "失败"  # 大成功/成功/失败/大失败
    xp: int = 0  # 成功检定奖励经验
    narrative: str = ""

    @property
    def total(self) -> int:
        return self.roll.total


class Message(BaseModel):
    """对话消息。kind 决定前端渲染：story|player|system|roll|check|card|menu。"""

    id: str
    kind: str = "story"
    role: str
    content: str
    ts: float = Field(default_factory=time.time)
    meta: dict[str, Any] | None = None


class SkillProposal(BaseModel):
    """LLM 建议的一次数值检定：能力名或技能名 + 可选 DC。"""

    skill: str = ""
    ability: str | None = Field(None, description="直接指定能力，如 感知；优先于 skill")
    reason: str = ""
    dc: int | None = None


class DMPlan(BaseModel):
    """一次自由行动中 DM 的结构化决策输出：叙述/检定/推进/记账。"""

    narrative: str = Field(..., min_length=1)
    check: SkillProposal | None = None
    advance_scene: str | None = None
    triggers: list[str] = Field(default_factory=list)
    loot: list[Item] = Field(default_factory=list)  # 获得物品（自动入库）
    gold: int = 0  # 金币增减
    hp: int = 0  # HP 增减（负为伤害）


class SessionState(BaseModel):
    """会话动态世界状态：场景/角色/世界/旗标/大事记。"""

    scene_id: str = "prologue"
    turn: int = 0
    phase: str = ""  # 角色创建向导阶段
    player: Character = Field(default_factory=Character)
    world: WorldOutline = Field(default_factory=WorldOutline)
    npcs: dict[str, Any] = Field(default_factory=dict)
    flags: dict[str, Any] = Field(default_factory=dict)
    events: list[str] = Field(default_factory=list)
    pending: dict[str, Any] = Field(default_factory=dict)


class GameSession(BaseModel):
    """一次跑团会话（持久化单元）。"""

    id: str
    title: str
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    state: SessionState = Field(default_factory=SessionState)
    messages: list[Message] = Field(default_factory=list)
    stats: dict[str, Any] = Field(
        default_factory=lambda: {
            "rolls": 0,
            "checks": 0,
            "checks_passed": 0,
            "checks_failed": 0,
            "big_success": 0,
            "big_failure": 0,
            "xp": 0,
        }
    )
