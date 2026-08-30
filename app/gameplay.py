"""玩法引擎(application层):指令解析、d20 属性检定数值裁决、状态推进。

- 检定严格 D&D 5e:d20 + 属性修正(+熟练加值) vs DC;展示属性值/加值/DC 供玩家判断;
- 成功检定奖励 XP,引擎自动结算升级(属性/生命/熟练加值随等级成长);
- 剧情推进只走「世界声明的大分支」白名单,防 LLM 幻觉乱跳。
"""

from __future__ import annotations

import re

from . import character, dice, dnd
from .models import CheckResult, GameSession, Message
from .persistence import new_id


def add_message(session: GameSession, kind: str, role: str, content: str, meta: dict | None = None) -> Message:
    msg = Message(id=f"{kind}-{new_id()}", kind=kind, role=role, content=content, meta=meta)
    session.messages.append(msg)
    return msg


def start_session(session_id: str, player_name: str = "无名冒险者") -> GameSession:
    """创建新会话:注入默认世界与开场剧情;角色由 /char 向导创建(与剧本互不绑定)。"""
    sess = GameSession(id=session_id, title=dnd_default().title)
    st = sess.state
    st.player.name = player_name
    st.world = dnd_default()
    for npc_id, npc in st.world.npcs.items():
        st.npcs[npc_id] = dict(npc)
    prologue = st.world.scenes["prologue"]
    sess.messages = [
        Message(
            id=f"story-{new_id()}",
            kind="story",
            role="dm",
            content=prologue["entry"],
            meta={"scene_id": "prologue"},
        ),
        Message(
            id=f"system-{new_id()}",
            kind="system",
            role="system",
            content=(
                "· /char            创建角色(种族/职业/背景/属性/出生地,编号选择)\n"
                "· 自由行动         直接描写动作,DM 实时裁决\n"
                "· /check 感知      属性检定(显示属性值/加值/DC)\n"
                "· /roll 1d20+3     掷骰\n"
                "· /inv /hp /gp /spells 查看物资\n"
                "· /sell 1          出售物品 · /rest 长休 · /damage 3 扣血\n"
                "· /scene 场景卡 /help 指令 /restart 重新开始\n"
                "先输入 /char 1 创建你的角色,再开始冒险。"
            ),
        ),
    ]
    return sess


def dnd_default():
    from .scenario import default_world

    return default_world()


def run_check(session: GameSession, text: str, dc_override: int | None = None, seed: int | None = None) -> CheckResult:
    """执行一次 d20 属性检定:能力/属性值/加值/DC 全部显式化,成功奖励 XP。"""
    c = session.state.player
    ability = dnd.resolve_ability(text)
    value = dnd.ability_value(c, ability)
    proficient = _is_proficient(session, text, ability)
    prof = c.prof_bonus if proficient else 0
    mod = dnd.mod(value) + prof
    dc = dc_override if dc_override is not None else _default_dc(session)

    roll = dice.roll_expression("1d20", seed=seed)
    d20 = roll.total
    total = d20 + mod
    if d20 == 20:  # 大成功:无论加值/DC 一律成功
        success, degree = True, "大成功"
    elif d20 == 1:  # 大失败:无论加值/DC 一律失败
        success, degree = False, "大失败"
    else:
        success = total >= dc
        degree = "成功" if success else "失败"
    margin = total - dc

    xp = (dc * 3 + (dc if degree == "大成功" else 0)) if success else 0
    if xp:
        leveled = dnd.award_xp(c, xp)
        session.stats["xp"] += xp
        if leveled:
            session.state.events.append(f"升级!你的等级已提升至 L{c.level}(HP上限 {c.max_hp})")

    res = CheckResult(
        ability=ability,
        value=value,
        modifier=mod,
        proficient=proficient,
        dc=dc,
        roll=roll,
        success=success,
        margin=margin,
        degree=degree,
        xp=xp,
        narrative=_narrative(session, ability, value, mod, dc, roll.total, success, degree, xp),
    )

    s = session.stats
    s["checks"] += 1
    s["checks_passed" if success else "checks_failed"] += 1
    s["big_success"] += degree == "大成功"
    s["big_failure"] += degree == "大失败"
    s["rolls"] += 1

    _log_check(session, res)
    return res


def _is_proficient(session: GameSession, text: str, ability: str) -> bool:
    c = session.state.player
    if ability in c.sav_throws:
        return True
    skill = dice.normalize_skill(text) or text.strip()
    return skill in c.skills and dnd.SKILL_ABILITY.get(skill) == ability



def _default_dc(session: GameSession) -> int:
    scene = session.state.scene_id
    return 14 if scene in ("tomb", "sanctum") else 12


def _narrative(session, ability, value, mod, dc, d20, success, degree, xp) -> str:
    prof_note = "(含熟练加值)" if mod != dnd.mod(value) else ""
    head = "成功" if success else "失败"
    extra = f" 获得 {xp} XP!" if xp else " 未获得经验。"
    return (
        f"【{ability}检定】你的{ability}={value},修正{mod:+d}{prof_note},难度 DC {dc}。\n"
        f"DM 已代你投出 d20={d20},合计 {d20 + mod} → {degree}/{head}{extra}"
    )


def _log_check(session: GameSession, res: CheckResult) -> None:
    try:
        from . import storage

        if storage.telemetry_enabled():
            storage.get_store().log_check(
                session_id=session.id,
                turn=session.state.turn,
                scene_id=session.state.scene_id,
                skill=res.ability,
                dc=res.dc,
                total=res.roll.total + res.modifier,
                success=res.success,
                degree=res.degree,
                expression=res.roll.expression,
            )
    except Exception:
        pass


def _cmd(args: str) -> tuple[str, str]:
    parts = (args or "").strip().split(maxsplit=1)
    return (parts[0] if parts else "", parts[1].strip() if len(parts) > 1 else "")


def apply_command(session: GameSession, text: str) -> GameSession | None:
    """处理斜杠指令;返回 None 表示自由行动,应交 DM 引擎。"""
    t = text.strip()
    if not t or t.lower() == "/help":
        add_message(session, "system", "system", (
            "/char 创建角色 · /check 感知 [DC] 属性检定(显式数值) · /roll 1d20+3 掷骰\n"
            "/hp 生命 /gp 金币 /inv 背包(含附魔) /spells 法术位 · /sell 编号 出售\n"
            "/rest 长休(回满HP+法术位) · /damage N /heal N /xp N /loot N\n"
            "/scene 场景卡 · /restart 重新开始\n自由行动:直接描写角色动作即可。"
        ))
        return session

    if t.lower() == "/restart":
        new = start_session(session.id, session.state.player.name)
        add_message(new, "system", "system", "世界重置,时间回到风铃镇傍晚的广场。")
        return new

    if t.lower() == "/char":
        for content in character.choose(session.state, ""):
            add_message(session, "system", "system", content)
        return session
    if t.lower().startswith("/char "):
        for content in character.choose(session.state, t[6:].strip()):
            add_message(session, "system", "system", content)
        return session

    if t.lower() == "/scene":
        world = session.state.world
        scene = world.scenes.get(session.state.scene_id)
        add_message(
            session,
            "card",
            "system",
            scene["name"] + "\n" + scene.get("desc", ""),
            {"scene_id": scene["id"], "image": world.scene_images.get(scene["id"], "")},
        )
        return session

    m = re.match(r"/roll\s+(.+)", t, re.IGNORECASE)
    if m:
        try:
            roll = dice.roll_expression(m.group(1).strip())
        except dice.DiceFormatError as e:
            add_message(session, "system", "system", str(e))
        else:
            session.stats["rolls"] += 1
            add_message(session, "roll", "dice", dice.summarize(roll), {"expression": roll.expression, "total": roll.total})
        return session

    m = re.match(r"/check\s*(.*)", t, re.IGNORECASE)
    if m:
        arg = m.group(1).strip()
        dc_override = None
        mdc = re.match(r"(.+?)\s+(\d{1,2})$", arg)
        if mdc:
            arg, dc_override = mdc.group(1).strip(), int(mdc.group(2))
        res = run_check(session, arg or "感知", dc_override=dc_override)
        add_message(session, "check", "dm", res.narrative, {
            "ability": res.ability,
            "value": res.value,
            "modifier": res.modifier,
            "dc": res.dc,
            "total": res.roll.total + res.modifier,
            "degree": res.degree,
            "success": res.success,
            "xp": res.xp,
        })
        add_message(session, "roll", "dice", dice.summarize(res.roll))
        return session

    if t.lower() == "/hp":
        p = session.state.player
        add_message(session, "system", "system", f"HP {p.hp}/{p.max_hp} | 生命状态:{'濒危' if p.hp <= 0 else ('重伤' if p.hp <= p.max_hp // 3 else '良好')}")
        return session

    if t.lower() == "/gp":
        add_message(session, "system", "system", f"金币 {session.state.player.gp} gp")
        return session

    if t.lower() == "/inv":
        add_message(session, "system", "system", _inventory_text(session))
        return session

    if t.lower().startswith("/sell"):
        return _handle_sell(session, t)

    if t.lower() == "/spells":
        c = session.state.player
        slots = " ".join(f"{lv}环×{n}" for lv, n in sorted(c.spell_slots.items())) or "无"
        spells = "、".join(s["name"] for s in c.spells if s["prepared"]) or "无"
        add_message(session, "system", "system", f"法术位:{slots} | 已准备:{spells}")
        return session

    if t.lower() == "/rest":
        c = session.state.player
        c.hp = c.max_hp
        c.spell_slots = dnd.spell_slots(c.klass, c.level)
        session.state.events.append("长休完成:HP 与法术位已回复。")
        add_message(session, "system", "system", f"长休完成。HP {c.hp}/{c.max_hp},法术位已回满。")
        return session

    m = re.match(r"/(damage|heal|xp|loot)\s+(\d{1,5})", t, re.IGNORECASE)
    if m:
        op, n = m.group(1).lower(), int(m.group(2))
        c = session.state.player
        if op in ("damage", "heal"):
            c.hp = min(c.max_hp, c.hp + (-n if op == "damage" else n))
            add_message(session, "system", "system", f"HP → {c.hp}/{c.max_hp}")
            return session
        if op == "xp":
            leveled = dnd.award_xp(c, n)
            session.stats["xp"] += n
            note = f"升级!当前 L{c.level}" if leveled else ""
            add_message(session, "system", "system", f"经验 +{n} XP(总数 {c.xp}){note}")
            return session
        if op == "loot":
            c.gp += n
            session.state.events.append(f"获得 {n} gp")
            add_message(session, "system", "system", f"金币 +{n}(当前 {c.gp} gp)")
            return session

    return None


def _handle_sell(session: GameSession, t: str) -> GameSession:
    c = session.state.player
    arg = _cmd(t.lower().replace("/inv", "/sell").replace("/sell", "/sell"))[1]
    if not c.inventory:
        add_message(session, "system", "system", "背包是空的,没什么可卖。")
        return session
    idx = None
    if arg.isdigit():
        idx = int(arg)
    else:
        for i, it in enumerate(c.inventory, 1):
            if arg and (arg in it.name or it.name in arg):
                idx = i
                break
    if idx is None or not (1 <= idx <= len(c.inventory)):
        add_message(session, "system", "system", "请给出想出售的物品编号: /sell 1,当前背包:\n" + _inventory_text(session))
        return session
    item = c.inventory.pop(idx - 1)
    price = dnd.item_value(item, c.abilities.charisma)
    c.gp += price
    session.state.events.append(f"出售 {item.name},得 {price} gp")
    add_message(session, "system", "system", f"你以 {price} gp 出售了 {item.name}×{item.qty}。当前 {c.gp} gp(魅力带来折扣,懂行的买家)。")
    return session


def _inventory_text(session: GameSession) -> str:
    c = session.state.player
    lines = [f"{i}. {it.name}×{it.qty} 价值{it.value}gp{(' [' + it.effect + ']') if it.effect else ''} —— {it.desc}"
             for i, it in enumerate(c.inventory, 1)]
    return ("背包(装备与附魔都会记在这里):\n" + "\n".join(lines) + f"\n金币:{c.gp} gp") if lines else f"背包空空。金币:{c.gp} gp"


def advance_scene(session: GameSession, scene_id: str) -> Message | None:
    """场景推进:换场景时追加 DM 入场白(只在世界声明过的大分支上允许)。"""
    world = session.state.world
    scene = world.scenes.get(scene_id)
    if not scene:
        return None
    session.state.scene_id = scene_id
    session.state.events.append(f"推进到「{scene['name']}」大分支")
    return add_message(session, "story", "dm", scene.get("entry", ""), {"scene_id": scene_id})
