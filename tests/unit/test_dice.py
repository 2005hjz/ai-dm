"""骰子表达式解析与投掷的单元测试。"""

from __future__ import annotations

from app.dice import DiceFormatError, normalize_skill, parse_expression, roll_expression, summarize
from app.models import DiceRoll


def test_parse_basic():
    assert parse_expression("1d20+3") == (1, 20, 3)
    assert parse_expression("2d6") == (2, 6, 0)
    assert parse_expression("d10-1") == (1, 10, -1)
    assert parse_expression("4d4+1") == (4, 4, 1)


def test_parse_edge_spacing():
    assert parse_expression("1d20 + 3") == (1, 20, 3)


def test_parse_invalid():
    import pytest

    for bad in ["", "d", "2d3d4", "hello", "d0", "101d6", "2d1001", "abc+d"]:
        try:
            parse_expression(bad)
            pytest.fail(f"应拒绝非法表达式: {bad!r}")
        except DiceFormatError:
            pass


def test_roll_seeded_deterministic():
    a = roll_expression("1d20+3", seed=42)
    b = roll_expression("1d20+3", seed=42)
    assert a.total == b.total
    assert isinstance(a, DiceRoll)
    assert a.count == 1 and a.sides == 20 and a.modifier == 3


def test_roll_total_formula():
    r = roll_expression("3d6+2", seed=7)
    assert r.total == sum(r.rolls) + r.modifier
    assert len(r.rolls) == 3
    assert all(1 <= x <= 6 for x in r.rolls)


def test_normalize_skill_alias_and_canon():
    assert normalize_skill("我想搜索一下") == "侦查"
    assert normalize_skill("使用说服") == "交涉"
    assert normalize_skill("敏捷闪避") == "潜行"
    assert normalize_skill("完全没有技能词") is None


def test_summarize():
    r = roll_expression("2d6", seed=1)
    s = summarize(r)
    assert r.expression in s
    assert str(r.total) in s
