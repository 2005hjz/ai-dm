"""玩法引擎(application层):指令解析、d20 属性检定数值裁决、状态推进。

- 检定严格 D&D 5e:d20 + 属性修正(+熟练加值) vs DC;展示属性值/加值/DC 供玩家判断;
- 成功检定奖励 XP,引擎自动结算升级(属性/生命/熟练加值随等级成长);
- 剧情推进只走「世界声明的大分支」白名单,防 LLM 幻觉乱跳。
"""

from __future__ import annotations

import re

from . import character, dice, dnd
from .models import AttackProposal, AttackResult, CheckResult, GameSession, Item, Message, Quest
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
    st.quests = [q.model_copy(deep=True) for q in st.world.quests]
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
            "/quests 任务板(公会/NPC) · /accept N 接任务 · /complete N 结算任务\n"
            "/attack [目标] 攻击检定(d20 命中+伤害骰,击杀得经验) · /rest 长休(回满HP+法术位)\n"
            "/damage N /heal N /xp N /loot N · /scene 场景卡 · /restart 重新开始\n"
            "自由行动:直接描写角色动作即可。"
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

    if t.lower() == "/quests":
        add_message(session, "system", "system", _quest_board_text(session))
        return session
    m = re.match(r"/(quest|accept)\s+(\d+)", t, re.IGNORECASE)
    if m:
        q = _quest_by_number(session, int(m.group(2)), "available")
        if q is None:
            add_message(session, "system", "system", "没有找到可接取的任务,先 /quests 查看悬赏板与 NPC 委托。")
        else:
            accept_quest(session, q)
            add_message(session, "system", "system", f"已接受任务【{q.title}】({q.source})——{q.objective}")
        return session
    m = re.match(r"/complete\s+(\d+)", t, re.IGNORECASE)
    if m:
        q = _quest_by_number(session, int(m.group(1)), "accepted")
        if q is None or not complete_quest(session, q):
            add_message(session, "system", "system", "没有可结算的已接受任务,用 /quests 查看。")
        else:
            add_message(session, "system", "system", f"任务完成!《{q.title}》奖励 +{q.reward_xp} XP、{q.reward_gp} gp。")
        return session
    if t.lower().startswith("/attack"):
        proposal = None
        if len(t) > len("/attack") and t[len("/attack"):].strip():
            proposal = AttackProposal(target=t[len("/attack"):].strip()[:24])
        res = resolve_attack(session, proposal)
        if res is None:
            add_message(session, "system", "system", "当前没有明确的战斗目标——等 DM 开启战斗(敌人出现时),或用 /quests 接取清剿类任务。")
        else:
            add_message(session, "combat", "dice", res.narrative, {"target": res.target, "ac": res.ac, "atk_total": res.atk_total, "hit": res.hit, "damage": res.damage_total, "killed": res.killed, "xp": res.xp})
            session.stats["rolls"] += 1
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


def _award_xp(session: GameSession, amount: int, source: str) -> bool:
    """给角色发放经验(检定成功/任务奖励/击杀/特殊事件)并结算升级。"""
    if amount <= 0:
        return False
    c = session.state.player
    leveled = dnd.award_xp(c, amount)
    session.stats["xp"] += amount
    session.state.events.append(f"获得 {amount} XP({source})" + (" —— 升级!" if leveled else ""))
    return leveled


def _add_item(session: GameSession, item: Item) -> None:
    c = session.state.player
    found = next((x for x in c.inventory if x.name == item.name), None)
    if found:
        found.qty += max(1, item.qty)
    else:
        c.inventory.append(item)


def _quest_by_number(session: GameSession, idx: int, status: str) -> Quest | None:
    for i, q in enumerate([x for x in session.state.quests if x.status == status], 1):
        if i == idx:
            return q
    return None


def _quest_board_text(session: GameSession) -> str:
    board, active = [], []
    for q in session.state.quests:
        (active if q.status == "accepted" else board).append(q)
    lines = ["【冒险者公会的悬赏板与 NPC 委托】"]
    for i, q in enumerate(board, 1):
        lines.append(f"{i}. 【{q.source}】《{q.title}》—— {q.desc}({q.objective})奖励:{q.reward_xp} XP/{q.reward_gp} gp")
    lines.append("【已接取】(用 /complete 编号 结算)")
    for i, q in enumerate(active, 1):
        lines.append(f"{i}. 《{q.title}》({q.source})——{q.objective}")
    if not active:
        lines.append("  (暂无)")
    lines.append("接取:/accept 编号 · 结算:/complete 编号")
    return "\n".join(lines)


def accept_quest(session: GameSession, quest: Quest) -> None:
    quest.status = "accepted"
    session.state.events.append(f"接受任务《{quest.title}》({quest.source})")


def complete_quest(session: GameSession, quest: Quest) -> bool:
    """任务完成结算:经验/金币/装备奖励全部自动入库。"""
    if quest.status != "accepted":
        return False
    quest.status = "done"
    _award_xp(session, quest.reward_xp, f"完成任务《{quest.title}》")
    if quest.reward_gp:
        session.state.player.gp += quest.reward_gp
        session.state.events.append(f"任务奖励金币 +{quest.reward_gp} → {session.state.player.gp} gp")
    for it in quest.reward_items:
        _add_item(session, it)
        session.state.events.append(f"任务奖励物品【{it.name}】入库")
    session.stats["quests_done"] += 1
    session.state.events.append(f"完成任务《{quest.title}》({quest.source})")
    return True


def _attack_narrative(target: str, ac: int, d20: int, mod: int, total: int, hit: bool, crit: bool, weapon: str, dmg_expr: str, dmg_total: int, killed: bool, hp: int, max_hp: int) -> str:
    head = "⚔ 大成功(暴击)!" if crit else "命中!" if hit else "未命中!"
    dmg = f" 伤害({weapon}) {dmg_expr} → {dmg_total}" if hit and dmg_expr else ""
    tail = f" 剩余 HP {hp}/{max_hp}。" if hit and not killed else (" 已被击杀!" if killed else "。")
    return f"【攻击检定 · {target}】命中骰 d20={d20} 修正{mod:+d} = {total} vs AC {ac} → {head}{dmg}{tail}"


def resolve_attack(session: GameSession, proposal: AttackProposal | None = None, seed: int | None = None) -> AttackResult | None:
    """攻击检定:引擎掷 d20 判定命中(vs AC),命中后掷伤害骰;击杀结算经验/金币/装备。seed 用于测试可控。"""
    combat = session.state.combat
    if not combat or combat.get("killed"):
        return None
    c = session.state.player
    weapon, sides, ability = dnd.class_weapon(c.klass)
    if proposal and proposal.weapon:
        weapon = proposal.weapon
    target = (proposal.target if proposal and proposal.target else "") or combat.get("name", "敌人")
    ac = proposal.ac if proposal and proposal.ac is not None else int(combat.get("ac", 12))
    ability_cn = proposal.ability if proposal and proposal.ability else ability
    amod = dnd.mod(dnd.ability_value(c, dnd.resolve_ability(ability_cn)))
    atk_mod = amod + c.prof_bonus
    roll = dice.roll_expression("1d20", seed=seed)
    total = roll.total + atk_mod
    crit = roll.total == 20
    fumble = roll.total == 1
    hit = not fumble and (crit or total >= ac)
    dmg_total, dmg_expr = 0, ""
    if hit:
        dice_n = 2 if crit else 1
        dmg_expr = f"{dice_n}d{sides}{amod:+d}"
        damage_seed = None if seed is None else seed + 7
        dmg_total = dice.roll_expression(dmg_expr, seed=damage_seed).total
    hp = max(0, int(combat.get("hp", 0)) - dmg_total)
    killed = hp <= 0
    combat["hp"] = hp
    if killed:
        combat["killed"] = True
        reward_xp = int(combat.get("reward_xp", 0) or 0)
        _award_xp(session, reward_xp, f"击杀{target}")
        if combat.get("gold"):
            c.gp += int(combat["gold"])
            session.state.events.append(f"从{target}身上搜得 {int(combat['gold'])} gp")
        for it in combat.get("loot", []) or []:
            _add_item(session, Item(name=str(it.get("name"))[:40], desc=str(it.get("desc", ""))[:80], effect=str(it.get("effect", ""))[:60], qty=max(1, int(it.get("qty", 1))), value=max(0, int(it.get("value", 2)))))
            session.state.events.append(f"从{target}身上获得物品【{it.get('name')}】")
        session.stats["kills"] += 1
    return AttackResult(
        target=target, ac=ac, weapon=weapon,
        atk_d20=roll.total, atk_mod=atk_mod, atk_total=total,
        hit=hit, crit=crit, damage_total=dmg_total, damage_expression=dmg_expr,
        killed=killed, enemy_hp=hp, xp=int(combat.get("reward_xp", 0) or 0) if killed else 0,
        narrative=_attack_narrative(target, ac, roll.total, atk_mod, total, hit, crit, weapon, dmg_expr, dmg_total, killed, hp, int(combat.get("max_hp", hp))),
    )


def open_combat(session: GameSession, spec: dict) -> None:
    """按 DM 声明开启战斗目标(防御性清洗字段)。"""
    combat = {
        "name": str(spec.get("name", "敌人"))[:20] or "敌人",
        "ac": max(5, min(25, int(spec.get("ac", 12) or 12))),
        "hp": max(1, int(spec.get("hp", 8) or 8)),
        "max_hp": max(1, int(spec.get("max_hp", spec.get("hp", 8)) or 8)),
        "weapon": str(spec.get("weapon", ""))[:20],
        "damage": str(spec.get("damage", ""))[:20],
        "reward_xp": max(0, int(spec.get("reward_xp", 0) or 0)),
        "gold": max(0, int(spec.get("gold", 0) or 0)),
        "loot": list(spec.get("loot", []) or []),
    }
    session.state.combat = combat
    session.state.events.append(f"战斗开始:【{combat['name']}】AC {combat['ac']} HP {combat['hp']}")


def advance_scene(session: GameSession, scene_id: str) -> Message | None:
    """场景推进:换场景时追加 DM 入场白(只在世界声明过的大分支上允许)。"""
    world = session.state.world
    scene = world.scenes.get(scene_id)
    if not scene:
        return None
    session.state.scene_id = scene_id
    session.state.events.append(f"推进到「{scene['name']}」大分支")
    return add_message(session, "story", "dm", scene.get("entry", ""), {"scene_id": scene_id})
