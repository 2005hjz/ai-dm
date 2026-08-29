"""骰子表达式解析与投掷。支持形如 1d20+3 / 2d6 / d10-1 的表达式。"""

from __future__ import annotations

import random
import re

from .models import DiceRoll

_TOKEN_RE = re.compile(r"(\d*)d(\d+)\s*([+-]\s*\d+)?")

# 常用技能术语(用于 /check 时智能解析)
KNOWN_SKILLS = [
    "侦查",
    "侦察",
    "搜索",
    "调查",
    "推理",
    "逻辑",
    "交涉",
    "说服",
    "欺骗",
    "恐吓",
    "表演",
    "潜行",
    "隐匿",
    "敏捷",
    "闪避",
    "运动",
    "体能",
    "力量",
    "强健",
    "搏斗",
    "格斗",
    "武器",
    "射击",
    "医疗",
    "急救",
    "机械",
    "破解",
    "电脑",
    "科技",
    "神秘学",
    "学识",
    "记忆",
]

_SKILL_ALIAS = {
    "侦察": "侦查",
    "调查": "侦查",
    "搜索": "侦查",
    "说服": "交涉",
    "欺骗": "交涉",
    "恐吓": "交涉",
    "表演": "交涉",
    "隐匿": "潜行",
    "敏捷": "潜行",
    "闪避": "潜行",
    "运动": "体能",
    "力量": "体能",
    "强健": "体能",
    "搏斗": "体能",
    "格斗": "体能",
    "急救": "医疗",
    "电脑": "科技",
    "破解": "科技",
    "推理": "推理",
}


class DiceFormatError(ValueError):
    pass


def parse_expression(expr: str) -> tuple[int, int, int]:
    """解析 'XdY±Z' 表达式,返回 (count, sides, modifier)。"""
    expr = expr.strip().replace(" ", "")
    if not expr:
        raise DiceFormatError("表达式为空")
    m = _TOKEN_RE.fullmatch(expr)
    if not m:
        raise DiceFormatError(f"无法解析骰子表达式: {expr!r} (示例: 2d6+3 / d20 / 4d4-1)")
    count_s, sides_s, mod_s = m.groups()
    count = int(count_s) if count_s else 1
    sides = int(sides_s)
    modifier = int(mod_s) if mod_s else 0
    if count < 1 or count > 100:
        raise DiceFormatError("骰子数量需在 1~100 之间")
    if sides < 1 or sides > 1000:
        raise DiceFormatError("骰子面数需在 1~1000 之间")
    return count, sides, modifier


def roll_expression(expr: str, seed: int | None = None) -> DiceRoll:
    """投掷并返回结果记录。seed 用于测试可控。"""
    count, sides, modifier = parse_expression(expr)
    rng = random.Random(seed) if seed is not None else random
    rolls = [rng.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier
    return DiceRoll(expression=expr, count=count, sides=sides, modifier=modifier, rolls=rolls, total=total)


def normalize_skill(text: str) -> str | None:
    """从一句话里提取技能名,做了别名归一。识别不到返回 None。"""
    if not text:
        return None
    for alias, canon in sorted(_SKILL_ALIAS.items(), key=lambda kv: -len(kv[0])):
        if alias in text:
            return canon
    for skill in sorted(KNOWN_SKILLS, key=len, reverse=True):
        if skill in text:
            return skill
    return None


def summarize(roll: DiceRoll) -> str:
    """人类可读的投掷摘要,如: 1d20+3 → [ 4,5,15 ] 合计 12"""
    die_parts = "+".join(str(r) for r in roll.rolls)
    if not die_parts:
        return "空投"
    mod = roll.modifier
    expr_head = f"{roll.expression}"
    maths = die_parts + (f"{mod:+d}" if mod else "")
    return f"{expr_head}  →  骰出 {maths}  =  {roll.total}"
