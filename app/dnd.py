"""D&D 5e 领域规则表与纯函数：六维属性/种族(含拓展)/职业/背景/法术池/法术位/经验表/经济。

本层只提供「规则」本身，不依赖 LLM 与持久化；检定解析与升级结算由此层完成。
"""

from __future__ import annotations

from .dice import normalize_skill
from .models import Character, Item

ABILITY_ORDER = ["力量", "敏捷", "体质", "智力", "感知", "魅力"]
AB_FIELD = {
    "力量": "strength",
    "敏捷": "dexterity",
    "体质": "constitution",
    "智力": "intelligence",
    "感知": "wisdom",
    "魅力": "charisma",
}
AB_CN = {v: k for k, v in AB_FIELD.items()}
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

# 技能 → 关联能力（D&D 5e 映射）
SKILL_ABILITY = {
    "运动": "力量", "隐匿": "敏捷", "手上功夫": "敏捷", "开锁": "敏捷",
    "奥秘": "智力", "历史": "智力", "自然": "智力", "宗教": "智力", "调查": "智力",
    "动物驯化": "感知", "洞察": "感知", "医疗": "感知", "侦查": "感知", "生存": "感知",
    "欺瞒": "魅力", "表演": "魅力", "威吓": "魅力", "说服": "魅力",
}
# 旧词归一（兼容已有输入习惯）
_SKILL_ALIAS = {"侦察": "侦查", "搜索": "侦查", "调查": "调查", "交涉": "说服", "潜行": "隐匿", "体能": "运动", "科技": "奥秘"}

# 种族列表（含拓展种族）：bonus 为属性修正，note 为特性说明
RACES = [
    {"name": "人类", "bonus": {k: 1 for k in AB_FIELD.values()}, "note": "全属性+1"},
    {"name": "精灵", "bonus": {"dexterity": 2}, "note": "敏捷+2，黑暗视觉，精灵之敏"},
    {"name": "矮人", "bonus": {"constitution": 2}, "note": "体质+2，石中技艺，黑暗视觉"},
    {"name": "半身人", "bonus": {"dexterity": 2}, "note": "敏捷+2，好运，体型小巧"},
    {"name": "半精灵", "bonus": {"charisma": 2, "dexterity": 1, "intelligence": 1}, "note": "魅力+2，敏捷/智力+1"},
    {"name": "半兽人", "bonus": {"strength": 2, "constitution": 1}, "note": "力量+2 体质+1，蛮力"},
    {"name": "龙裔", "bonus": {"strength": 2, "charisma": 1}, "note": "力量+2 魅力+1，吐息武器"},
    {"name": "侏儒", "bonus": {"intelligence": 2}, "note": "智力+2，巧思，黑暗视觉"},
    {"name": "提夫林", "bonus": {"charisma": 2, "intelligence": 1}, "note": "魅力+2 智力+1，地狱遗赠"},
    {"name": "半巨人", "bonus": {"strength": 2, "constitution": 1}, "note": "力量+2 体质+1，山峦之力（拓展）"},
    {"name": "仙灵", "bonus": {"charisma": 1, "dexterity": 1}, "note": "魅力/敏捷+1，天生飞行（拓展）"},
    {"name": "羽族", "bonus": {"dexterity": 2, "wisdom": 1}, "note": "敏捷+2 感知+1，天生飞行（拓展）"},
    {"name": "变形者", "bonus": {"charisma": 2}, "note": "魅力+2，任意换貌（拓展）"},
    {"name": "猫人", "bonus": {"charisma": 2, "intelligence": 1}, "note": "魅力+2 智力+1，利爪与夜视（拓展）"},
]

# 职业列表：hp=每级生命骰均值, caster=0无/1全施法者/2半施法者, pack=起始装备, gp=起始金币
CLASSES = [
    {"name": "战士", "hp": 7, "caster": 0, "pack": "长剑、盾牌、皮甲、冒险者包", "gp": 40},
    {"name": "游侠", "hp": 6, "caster": 2, "pack": "长弓、双短剑、皮甲、追踪者包", "gp": 30},
    {"name": "盗贼", "hp": 5, "caster": 0, "pack": "两把细剑、皮甲、盗贼工具", "gp": 50},
    {"name": "吟游诗人", "hp": 5, "caster": 1, "pack": "长剑、皮甲、小型乐器", "gp": 40},
    {"name": "牧师", "hp": 5, "caster": 1, "pack": "钉头锤、硬皮甲、圣徽、祈祷书", "gp": 30},
    {"name": "德鲁伊", "hp": 5, "caster": 1, "pack": "弯刀、木盾、皮甲、自然法器", "gp": 30},
    {"name": "武僧", "hp": 5, "caster": 0, "pack": "双手短棒、冒险者包", "gp": 20},
    {"name": "圣武士", "hp": 6, "caster": 2, "pack": "长剑、盾牌、硬皮甲、圣徽", "gp": 40},
    {"name": "法师", "hp": 4, "caster": 1, "pack": "法杖、法术书、冒险者包", "gp": 20},
    {"name": "术士", "hp": 4, "caster": 1, "pack": "法杖、轻弩、冒险者包", "gp": 20},
    {"name": "邪术师", "hp": 4, "caster": 1, "pack": "法杖、皮甲、秘契物", "gp": 20},
    {"name": "野蛮人", "hp": 7, "caster": 0, "pack": "巨斧、皮甲、行囊", "gp": 20},
]

# 背景列表
BACKGROUNDS = [
    {"name": "平民", "perk": "城镇熟识，食宿有折扣", "skills": ["说服"], "gp": 10},
    {"name": "士兵", "perk": "军旅出身，懂战术", "skills": ["运动"], "gp": 10},
    {"name": "贵族", "perk": "头衔开路", "skills": ["说服"], "gp": 100},
    {"name": "艺人", "perk": "才艺谋生，得民众好感", "skills": ["表演"], "gp": 20},
    {"name": "农夫", "perk": "熟悉乡土与荒野", "skills": ["生存"], "gp": 10},
    {"name": "学者", "perk": "博览群书", "skills": ["奥秘"], "gp": 30},
    {"name": "流浪者", "perk": "四海为家，消息灵通", "skills": ["生存"], "gp": 5},
    {"name": "神殿孤儿", "perk": "教会庇护", "skills": ["医疗"], "gp": 0},
]

# 法术池（第0级=戏法；1-3级为主）：curated 常见 5e 法术，供选择与规则校验
SPELL_POOL = [
    ("神导术", 0), ("火钳术", 0), ("戏法·法师之手", 0), ("戏法·光亮术", 0), ("戏法·舞蹈术", 0),
    ("燃烧之手", 1), ("法师护甲", 1), ("睡眠术", 1), ("魔法飞弹", 1), ("侦测魔法", 1), ("护盾术", 1),
    ("不谐低语", 1), ("命令术", 1), ("治愈伤处", 1), ("祝福术", 1), ("圣火术", 1), ("橡木之心", 1),
    ("火球术", 3), ("闪电束", 3), ("群体治愈", 3), ("飞行术", 3), ("放逐术", 4),
]
SPELL_CN = {"治愈伤处": "医疗咒", "火球术": "火焰爆发"}

# 施法者等级 → 法术位表（1-9环数量）
SLOT_TABLE = {
    0: {}, 1: {1: 2}, 2: {1: 3}, 3: {1: 4, 2: 2}, 4: {1: 4, 2: 3},
    5: {1: 4, 2: 3, 3: 2}, 6: {1: 4, 2: 3, 3: 3}, 7: {1: 4, 2: 3, 3: 3, 4: 1},
    8: {1: 4, 2: 3, 3: 3, 4: 2}, 9: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}, 11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1}, 13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1}, 15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1}, 17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
}
SLOT_TABLE[18] = SLOT_TABLE[19] = SLOT_TABLE[20] = SLOT_TABLE[17]

# 升级所需累计经验表（L1=0 … L20）
XP_TABLE = [
    0, 300, 900, 2700, 6500, 14000, 23000, 34000, 48000, 64000,
    85000, 100000, 120000, 140000, 165000, 195000, 225000, 265000, 305000, 355000,
]


def mod(score: int) -> int:
    return (score - 10) // 2


def prof_bonus(level: int) -> int:
    return 2 + (level - 1) // 4


def ability_value(c: Character, cn: str) -> int:
    return getattr(c.abilities, AB_FIELD[cn])


def xp_to_level(xp: int) -> int:
    for lv in range(20, 0, -1):
        if xp >= XP_TABLE[lv - 1]:
            return lv
    return 1


def spell_slots(klass: str, level: int) -> dict[int, int]:
    for ci in CLASSES:
        if ci["name"] == klass:
            cl = level if ci["caster"] == 1 else level // 2
            return dict(SLOT_TABLE.get(min(cl, 20), {}))
    return {}


def class_info(klass: str) -> dict:
    return next((c for c in CLASSES if c["name"] == klass), {})


def race_info(name: str) -> dict:
    return next((r for r in RACES if r["name"] == name), {})


def background_info(name: str) -> dict:
    return next((b for b in BACKGROUNDS if b["name"] == name), {})


def resolve_ability(text: str) -> str:
    """从玩家/LLM 文本解析出用于检定的能力名（感知兜底）。"""
    t = (text or "").strip()
    if not t:
        return "感知"
    if t in ABILITY_ORDER or t in AB_CN.values():
        return AB_CN.get(t, t) if t in AB_CN else t
    skill = _SKILL_ALIAS.get(t, t)
    norm = normalize_skill(skill) or skill
    return SKILL_ABILITY.get(norm, "感知")


def parse_ability_input(text: str) -> list[int] | None:
    """解析标准数组分配输入（六个数，能力顺序 力量…魅力），非法返回 None。"""
    nums = [int(x) for x in str(text or "").split(",") if x.strip().isdigit()]
    if len(nums) != 6 or sorted(nums) != sorted(STANDARD_ARRAY):
        return None
    return nums


def apply_race_bonus(c: Character) -> Character:
    for field, bonus in race_info(c.race).get("bonus", {}).items():
        setattr(c.abilities, field, getattr(c.abilities, field) + bonus)
    return c


def award_xp(c: Character, amount: int) -> bool:
    """给角色加经验并结算升级；返回是否升级。"""  # noqa: B018
    c.xp += amount
    new_level = xp_to_level(c.xp)
    if new_level > c.level:
        c.level = new_level
        c.max_hp += class_info(c.klass).get("hp", 5) + mod(c.abilities.constitution)
        c.hp = c.max_hp
        c.prof_bonus = prof_bonus(c.level)
        return True
    return False


def item_value(item: Item, charisma: int) -> int:
    """出售价：价值折半 + 魅力加成（魅力游说折扣）。"""  # noqa: B018
    return max(0, item.value // 2 + max(0, mod(charisma)))
