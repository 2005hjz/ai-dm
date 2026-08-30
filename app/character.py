"""角色卡向导:D&D 5e 创建流程(全部选项编号展示,禁止替玩家跳过) + 角色卡渲染。

流程:init → race → class → background → ability(标准数组分配) → birthplace → spells(施法者) → done。
一切选择由引擎确定性裁决;种族含拓展,法术池供编号选择。
"""

from __future__ import annotations

from . import dnd
from .models import AbilityScores, Character, Item, SessionState, Spell

# 职业主属性(用于熟练豁免)
class_primary = {
    "战士": "力量",
    "游侠": "感知",
    "盗贼": "敏捷",
    "吟游诗人": "魅力",
    "牧师": "感知",
    "德鲁伊": "感知",
    "武僧": "敏捷",
    "圣武士": "感知",
    "法师": "智力",
    "术士": "魅力",
    "邪术师": "魅力",
    "野蛮人": "力量",
}

_pack_value = {"冒险者包": 5, "追踪者包": 5, "行囊": 3, "盗贼工具": 10}

_AB_FIELDS = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def _numbered(items: list[dict]) -> str:
    return "\n".join(f"{i}. {it['name']} —— {it.get('note', it.get('perk', ''))}" for i, it in enumerate(items, 1))


def _main_menu() -> str:
    return "冒险者公会欢迎你!请选择:\n1. 创建新角色\n2. 查看角色卡\n3. 重置角色重新创建\n4. 给角色改名(例:/char 4 阿格)"


def _ability_menu() -> str:
    return (
        f"把标准数组 {dnd.STANDARD_ARRAY} 分配到六维:1力量 2敏捷 3体质 4智力 5感知 6魅力。\n"
        "请回复: /char 15,14,13,8,12,10(六个数字按上述顺序填写你自己的分配)"
    )


def _eligible_spells(c: Character) -> list[tuple[str, int]]:
    slots = dnd.spell_slots(c.klass, c.level)
    max_lv = max(slots) if slots else 0
    already = {s.name for s in c.spells}
    return [s for s in dnd.SPELL_POOL if 0 < s[1] <= max_lv and s[0] not in already]


def _spell_menu(c: Character) -> str:
    pool = _eligible_spells(c)
    lines = [f"{i}. {name}({lv}环)" for i, (name, lv) in enumerate(pool, 1)]
    return "可准备的法术(0=跳过本步):\n" + "\n".join(lines) + "\n请回复: /char 1,3,5(逗号分隔编号)"


def _reset(c: Character) -> Character:
    for f in ("race", "klass", "background", "birthplace"):
        setattr(c, f, "")
    c.level, c.xp, c.hp, c.max_hp, c.gp = 1, 0, 10, 10, 10
    c.abilities = AbilityScores()
    c.skills, c.sav_throws, c.spells, c.inventory = [], [], [], []
    c.spell_slots = {}
    c.prof_bonus = dnd.prof_bonus(1)
    return c


def _starting_items(pack: str) -> list[dict]:
    items = []
    for name in (x.strip() for x in pack.split("、") if x.strip()):
        items.append({"name": name, "desc": "起始装备", "effect": "", "qty": 1, "value": _pack_value.get(name, 15)})
    return items


def choose(state: SessionState, rest: str) -> list[str]:
    """处理 /char 及向导阶段选择;返回要展示给玩家的消息列表。"""
    c = state.player
    phase = state.phase or "init"
    msgs: list[str] = []

    if phase == "init":
        if rest == "1":
            state.phase = "race"
            return ["请选择种族(编号,含拓展种族):", _numbered(dnd.RACES)]
        if rest == "2":
            return [sheet_text(state)]
        if rest == "3":
            _reset(c)
            state.phase = "race"
            return ["角色已重置。请选择种族(编号,含拓展种族):", _numbered(dnd.RACES)]
        if rest.startswith("4 "):
            c.name = rest[2:].strip()[:12] or c.name
            state.phase = "done"
            return [f"冒险者,从此你叫「{c.name}」。"]
        return [_main_menu()]

    if phase == "race":
        idx = _pick(rest, len(dnd.RACES))
        if idx is None:
            return ["请选择种族(编号,含拓展种族):", _numbered(dnd.RACES)]
        c.race = dnd.RACES[idx - 1]["name"]
        state.phase = "class"
        msgs.append(f"种族【{c.race}】→ {dnd.race_info(c.race).get('note', '')}")
        msgs.append("请选择职业(编号):")
        msgs.append(" ".join(f"{i}.{_name(it)}" for i, it in enumerate(dnd.CLASSES, 1)))
        return msgs

    if phase == "class":
        idx = _pick(rest, len(dnd.CLASSES))
        if idx is None:
            return ["请选择职业(编号):", " ".join(f"{i}.{_name(it)}" for i, it in enumerate(dnd.CLASSES, 1))]
        c.klass = dnd.CLASSES[idx - 1]["name"]
        state.phase = "background"
        msgs.append(f"职业【{c.klass}】")
        msgs.append("请选择背景(编号):")
        msgs.append(_numbered(dnd.BACKGROUNDS))
        return msgs

    if phase == "background":
        idx = _pick(rest, len(dnd.BACKGROUNDS))
        if idx is None:
            return ["请选择背景(编号):", _numbered(dnd.BACKGROUNDS)]
        c.background = dnd.BACKGROUNDS[idx - 1]["name"]
        state.phase = "ability"
        msgs.append(f"背景【{c.background}】→ {dnd.background_info(c.background).get('perk', '')}")
        msgs.append(_ability_menu())
        return msgs

    if phase == "ability":
        nums = dnd.parse_ability_input(rest)
        if nums is None:
            return [_ability_menu()]
        for f, v in zip(["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"], nums, strict=True):
            setattr(c.abilities, f, v)
        state.phase = "birthplace"
        msgs.append(f"属性已分配: {sheet_inline(c)}")
        msgs.append("请选择出生地(编号):")
        msgs.append("\n".join(f"{i}. {k} —— {v}" for i, (k, v) in enumerate(state.world.birthplaces.items(), 1)))
        return msgs

    if phase == "birthplace":
        options = list(state.world.birthplaces)
        idx = _pick(rest, len(options))
        if idx is None:
            return ["请选择出生地(编号):"]
        c.birthplace = options[idx - 1]
        msgs.append(f"你出身于【{c.birthplace}】——{state.world.birthplaces[c.birthplace]}")
        if dnd.spell_slots(c.klass, c.level):
            state.phase = "spells"
            msgs.append(_spell_menu(c))
        else:
            msgs.append(_finalize(state))
        return msgs

    if phase == "spells":
        pool = _eligible_spells(c)
        chosen = _pick_many(rest, len(pool))
        if chosen is None:
            return [_spell_menu(c)]
        for i in chosen:
            name, lv = pool[i - 1]
            if name not in {s.name for s in c.spells}:
                c.spells.append(Spell(name=name, level=lv, prepared=True))
        msgs.append(f"已准备法术: {', '.join(s.name for s in c.spells if s.prepared) or '无'}。")
        msgs.append(_finalize(state))
        return msgs

    return [_main_menu()]


def _name(it: dict) -> str:
    return it.get("name", "")


def _pick(rest: str, n: int) -> int | None:
    try:
        i = int(rest.strip())
    except (TypeError, ValueError):
        return None
    return i if 1 <= i <= n else None


def _pick_many(rest: str, n: int) -> list[int] | None:
    if not rest.strip():
        return None
    try:
        idxs = [int(x) for x in rest.split(",") if x.strip()]
    except ValueError:
        return None
    return [i for i in idxs if 1 <= i <= n] or None


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_from_form(form: dict | None, birthplaces: dict[str, str] | None = None) -> Character | None:
    """从前端角色创建表单构建并结算 D&D 5e 角色卡(身份/初始属性/技能/法术/背包)。

    表单属性值为「种族加成前」的基础值;本函数按 D&D 5e 规则结算种族加成、生命、
    熟练加值、法术位与起始装备。表单含未知种族/职业/背景时对应字段留空——角色卡
    仍可保存与使用,但规则引擎相关能力(检定/升级/法术位)按默认值工作。
    """
    form = form or {}
    options = {r["name"]: r for r in dnd.RACES}
    info = {k["name"]: k for k in dnd.CLASSES}
    bginfo = {b["name"]: b for b in dnd.BACKGROUNDS}

    name = str(form.get("name") or "").strip()[:12] or "无名冒险者"
    race = str(form.get("race") or "").strip()
    klass = str(form.get("klass") or "").strip()
    background = str(form.get("background") or "").strip()

    c = Character(name=name)
    if race in options:
        c.race = race
    if klass in info:
        c.klass = klass
    if background in bginfo:
        c.background = background

    abi = form.get("abilities") or {}
    scores = {f: _int(abi.get(f), 10) for f in _AB_FIELDS}
    c.abilities = AbilityScores(**{f: max(1, min(30, v)) for f, v in scores.items()})
    dnd.apply_race_bonus(c)

    birthplace = str(form.get("birthplace") or "").strip()
    if birthplaces is None:
        birthplaces = {}
    if birthplace in birthplaces:
        c.birthplace = birthplace

    c.level = max(1, min(20, _int(form.get("level"), 1)))
    c.xp = max(0, _int(form.get("xp")))
    c.prof_bonus = dnd.prof_bonus(c.level)
    ci = info.get(c.klass, {})
    c.spell_slots = dnd.spell_slots(c.klass, c.level)

    max_hp = _int(form.get("max_hp"))
    c.max_hp = max_hp if max_hp > 0 else max(1, ci.get("hp", 5) + dnd.mod(c.abilities.constitution))
    hp = _int(form.get("hp"))
    c.hp = min(c.max_hp, hp) if hp > 0 else c.max_hp

    gp = form.get("gp")
    if gp is None or gp == "" or (isinstance(gp, int) and gp == 0 and "gp" not in form):
        gp = ci.get("gp", 20) + bginfo.get(c.background, {}).get("gp", 0)
    c.gp = max(0, _int(gp))

    skills = list(bginfo.get(c.background, {}).get("skills", []))
    for s in form.get("skills") or []:
        s = str(s).strip()
        if s in dnd.SKILL_ABILITY and s not in skills:
            skills.append(s)
    c.skills = skills

    savs = [class_primary.get(c.klass, "体质")]
    for s in form.get("sav_throws") or []:
        s = str(s).strip()
        if s in dnd.ABILITY_ORDER and s not in savs:
            savs.append(s)
    c.sav_throws = savs

    if c.spell_slots:
        max_lv = max(c.spell_slots)
        for name in form.get("spells") or []:
            name = str(name).strip()
            lv = next((lv for n, lv in dnd.SPELL_POOL if n == name), None)
            if lv is not None and 0 < lv <= max_lv and name not in {s.name for s in c.spells}:
                c.spells.append(Spell(name=name, level=lv, prepared=True))
        for name, lv in [s for s in dnd.SPELL_POOL if s[1] == 0][:2]:
            if name not in {s.name for s in c.spells}:
                c.spells.append(Spell(name=name, level=lv, prepared=True))

    for row in form.get("inventory") or []:
        if not isinstance(row, dict) or not (row.get("name") or "").strip():
            continue
        value = max(0, _int(row.get("value"), 2))
        c.inventory.append(
            Item(
                name=str(row.get("name"))[:40],
                qty=max(1, _int(row.get("qty"), 1)),
                desc=str(row.get("desc") or "")[:80],
                effect=str(row.get("effect") or "")[:60],
                value=value,
            )
        )
    if not c.inventory:
        for it in _starting_items(ci.get("pack", "")):
            c.inventory.append(Item(**it))
    return c


def character_options(birthplaces: dict[str, str] | None = None) -> dict:
    """角色创建表单所需选项(种族/职业/背景/出生地/技能/豁免/法术)。"""
    races = [
        {"name": r["name"], "note": r.get("note", ""), "bonus": {dnd.AB_CN.get(f, f): v for f, v in r.get("bonus", {}).items()}}
        for r in dnd.RACES
    ]
    birthplaces = birthplaces or {}
    return {
        "races": races,
        "classes": [{"name": c["name"], "gp": c.get("gp", 20), "pack": c.get("pack", "")} for c in dnd.CLASSES],
        "backgrounds": [{"name": b["name"], "perk": b.get("perk", "")} for b in dnd.BACKGROUNDS],
        "birthplaces": [{"key": k, "desc": v} for k, v in birthplaces.items()],
        "abilities": [{"key": dnd.AB_FIELD[f], "name": f} for f in dnd.ABILITY_ORDER],
        "skills": [{"name": n, "ability": dnd.SKILL_ABILITY[n]} for n in sorted(dnd.SKILL_ABILITY)],
        "sav_throws": [{"key": f, "name": f} for f in dnd.ABILITY_ORDER],
        "spells": [{"name": n, "level": lv} for n, lv in dnd.SPELL_POOL],
    }


def _finalize(state: SessionState) -> str:
    c = state.player
    dnd.apply_race_bonus(c)
    info = dnd.class_info(c.klass)
    c.max_hp = info.get("hp", 5) + dnd.mod(c.abilities.constitution)
    c.hp = c.max_hp
    c.prof_bonus = dnd.prof_bonus(c.level)
    c.skills = dnd.background_info(c.background).get("skills", [])
    c.sav_throws = [class_primary.get(c.klass, "体质")]
    c.gp += info.get("gp", 20) + dnd.background_info(c.background).get("gp", 0)
    for it in _starting_items(info.get("pack", "")):
        if it["name"] not in {x.name for x in c.inventory}:
            c.inventory.append(Item(**it))
    c.spell_slots = dnd.spell_slots(c.klass, c.level)
    for n, lv in [s for s in dnd.SPELL_POOL if s[1] == 0][:2]:
        if n not in {s.name for s in c.spells}:
            c.spells.append(Spell(name=n, level=lv, prepared=True))
    state.phase = "done"
    return f"角色卡已建立!\n{sheet_text(state)}\n你现在可以自由行动了(直接描写动作开始冒险)。"


def sheet_inline(c: Character) -> str:
    ab = " ".join(f"{dnd.AB_CN[field]}={getattr(c.abilities, field)}({dnd.mod(getattr(c.abilities, field)):+d})" for field in dnd.AB_FIELD.values())
    return f"{c.name} L{c.level} {c.race}/{c.klass} | {ab}"


def sheet_text(state: SessionState) -> str:
    c = state.player
    ab = "\n".join(
        f"  {dnd.AB_CN[field]} {getattr(c.abilities, field)} (修正{dnd.mod(getattr(c.abilities, field)):+d})"
        for field in dnd.AB_FIELD.values()
    )
    xp_line = "已满级" if c.level >= 20 else f"还需 {dnd.XP_TABLE[c.level] - c.xp} XP 升到 L{c.level + 1}"
    slots = " ".join(f"{lvl}环×{n}" for lvl, n in sorted(c.spell_slots.items())) or "无"
    spells = "、".join(s.name for s in c.spells if s.prepared) or "无"
    inv = "\n".join(
        f"  - {it.name}×{it.qty}(价值{it.value}gp){(' [' + it.effect + ']') if it.effect else ''}" for it in c.inventory
    ) or "  空"
    return (
        f"══ {c.name} · L{c.level} ══\n种族:{c.race} 职业:{c.klass} 背景:{c.background} 出生:{c.birthplace}\n"
        f"XP:{c.xp} {xp_line} | 熟练加值 +{c.prof_bonus}\nHP:{c.hp}/{c.max_hp} 金币:{c.gp}gp\n能力:\n{ab}\n"
        f"熟练技能:{'、'.join(c.skills) or '无'} 熟练豁免:{'、'.join(c.sav_throws)}\n"
        f"法术位:{slots} 已准备法术:{spells}\n背包:\n{inv}"
    )
