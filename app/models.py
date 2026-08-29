"""Pydantic 核心数据模型:会话、消息、骰子检定、检查结果。"""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class DiceRoll(BaseModel):
    """一次骰子投掷的完整记录。"""

    expression: str = Field(..., description="原始表达式,如 1d20+3")
    count: int
    sides: int
    modifier: int
    rolls: list[int] = Field(default_factory=list, description="每颗骰子的点数")
    total: int


class CheckResult(BaseModel):
    """一次技能检定(数值判定)的结果。"""

    skill: str
    dc: int
    advantage: bool = False
    roll: DiceRoll
    success: bool
    margin: int = 0  # 成功/失败幅度,正值越高越出色
    degree: str = "普通"  # 大成功 / 成功 / 失败 / 大失败
    narrative: str = ""

    @property
    def total(self) -> int:
        """便捷属性:检定掷骰总点。"""
        return self.roll.total


class Message(BaseModel):
    """对话消息。kind 决定前端怎么渲染。"""

    id: str
    kind: str = "story"  # story | player | system | roll | check | card
    role: str
    content: str
    ts: float = Field(default_factory=time.time)
    meta: dict[str, Any] | None = None

    # 只存内容,按需组装
    id_by_ts: str = ""


class PlayerState(BaseModel):
    name: str = "无名调查员"
    hp: int = 5
    max_hp: int = 5
    hp_labels: list[str] = Field(default_factory=lambda: ["完整", "轻伤", "受伤", "重伤", "濒死", "生命垂危"])


class CharacterMeta(BaseModel):
    """NPC / 关键物件信息,前端用于渲染角色卡。"""

    npc_id: str
    name: str
    title: str = ""
    alive: bool = True
    relation: int = 0  # -100 ~ 100
    hp: int = 3
    max_hp: int = 3
    portrait: str | None = None  # 图片 data url
    desc: str = ""


class SceneInfo(BaseModel):
    scene_id: str
    name: str
    entry_text: str
    is_terminal: bool = False


class SessionState(BaseModel):
    """会话的动态世界状态。"""

    scene_id: str = "prologue"
    turn: int = 0
    player: PlayerState = Field(default_factory=PlayerState)
    # 用宽松 dict 而非 CharacterMeta:保持 JSON 往返原样,避免反序列化变成对象后按下标取报错
    npcs: dict[str, Any] = {}
    flags: dict[str, Any] = {}
    discovered: list[str] = []
    skill_list: list[str] = []
    events: list[str] = []  # 游戏内重大事件记录


class SkillProposal(BaseModel):
    """LLM 建议的一次数值检定(结构化输出契约)。"""

    skill: str = Field(..., description="建议检定的技能名,如:侦查/推理/交涉")
    reason: str = Field("", description="为何发起这次检定的简短理由")
    dc: int | None = Field(None, description="可选:由 LLM 直接建议 DC,缺省时引擎按场景自动计算")


class DMPlan(BaseModel):
    """一次自由行动中 DM 的结构化决策输出(Pydantic 数值检定契约)。"""

    narrative: str = Field(..., min_length=1, description="DM 对玩家行动的主叙述")
    check: SkillProposal | None = Field(None, description="是否附带一次技能检定")
    advance_scene: str | None = Field(None, description="可选:直接推进到的场景 id")
    triggers: list[str] = Field(default_factory=list, description="本轮触发的事件/状态变更标签")


class GameSession(BaseModel):
    """一次跑团会话(持久化单元)。"""

    id: str
    title: str
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    state: SessionState = Field(default_factory=SessionState)
    messages: list[Message] = []
    stats: dict[str, Any] = Field(
        default_factory=lambda: {
            "rolls": 0,
            "checks": 0,
            "checks_passed": 0,
            "checks_failed": 0,
            "big_success": 0,
            "big_failure": 0,
        }
    )
