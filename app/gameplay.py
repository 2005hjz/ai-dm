"""玩法引擎:指令解析、骰子裁决、状态推进。不依赖具体 LLM,可单独测试。

剧情推进不在此层离线预写——本层只负责「数值裁决」与「状态合法变更」:
- DM(LLM) 当轮给出 DMPlan(叙述 / 是否建议检定 / 推进到哪个大分支),引擎按统一规则掷骰裁决;
- 场景跳转只接受声明后的大剧情分支 id(白名单校验),防止 LLM 幻觉乱跳。
"""

from __future__ import annotations

import re

from . import dice
from .models import CheckResult, GameSession, Message
from .persistence import new_id
from .scenario import SCENARIO


def add_message(session: GameSession, kind: str, role: str, content: str, meta: dict | None = None) -> Message:
    msg = Message(id=f"{kind}-{new_id()}", kind=kind, role=role, content=content, meta=meta)
    session.messages.append(msg)
    return msg


def start_session(session_id: str, player_name: str = "无名调查员") -> GameSession:
    """创建新会话,写入开场剧情。"""
    sess = GameSession(id=session_id, title=SCENARIO["title"])
    sess.state.player.name = player_name
    sess.state.skill_list = list(SCENARIO["skills"])
    for npc_id, npc in SCENARIO["npcs"].items():
        sess.state.npcs[npc_id] = {
            "npc_id": npc_id,
            "name": npc["name"],
            "title": npc.get("title", ""),
            "alive": True,
            "relation": npc.get("relation", 0),
            "hp": npc.get("hp", 3),
            "max_hp": npc.get("hp", 3),
            "portrait": npc.get("portrait", ""),
            "desc": npc.get("desc", ""),
        }
    prologue = SCENARIO["scenes"]["prologue"]
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
                "· 自由行动:直接打字描述你的动作,我会实时判定并演进剧情\n"
                "· /roll 1d20+3  掷骰\n"
                "· /check 侦查    技能检定(我按场景给出 DC)\n"
                "· /scene         查看当前场景卡\n"
                "· /hp            查看状态\n"
                "· /help          查看指令\n"
                "· /restart       重新开始\n"
                "输入「开始冒险」即可继续。"
            ),
        ),
    ]
    return sess


_DC_BASE = 10  # 统一默认检定难度;LLM 建议 dc 时可覆盖


def run_check(session: GameSession, skill: str, seed: int | None = None, dc_override: int | None = None):
    """执行一次 d20 技能检定:统一默认 DC + 技能倾向微调,输出结构化 CheckResult。

    dc_override: 当 DM 结构化契约显式给出 DC 时优先采用(否则按统一默认计算)。
    """
    skill = dice.normalize_skill(skill) or "侦查"

    dc_bonus = 0
    if skill in ("侦查", "推理", "搜索", "调查", "医疗", "科技"):
        dc_bonus = 0
    elif skill in ("交涉", "欺骗", "恐吓", "潜行", "体能"):
        dc_bonus = 1
    else:
        dc_bonus = 2
    dc = min(14, _DC_BASE + dc_bonus)
    if dc_override is not None:
        dc = max(3, min(25, int(dc_override)))

    roll = dice.roll_expression("1d20", seed=seed)
    if skill in ("潜行", "敏捷") and session.state.flags.get("adv_stealth"):
        roll.total += 2
        roll.modifier += 2
    total = roll.total
    success = total >= dc

    degree = ("大成功" if total >= dc + 5 else "成功") if success else ("大失败" if total <= dc - 5 else "失败")
    margin = total - dc

    res = CheckResult(
        skill=skill,
        dc=dc,
        roll=roll,
        success=success,
        margin=margin,
        degree=degree,
        narrative=_narrative(skill, success, degree),
    )

    s = session.stats
    s["checks"] += 1
    s["checks_passed" if success else "checks_failed"] += 1
    s["big_success" if degree == "大成功" else "big_failure"] += 1
    s["rolls"] += 1

    _log_check(session, res)
    return res


def _log_check(session: GameSession, res: CheckResult) -> None:
    """写入 SQLite 审计(结构化数值检定),失败不影响主流程(防御性编程)。"""
    try:
        from . import storage

        if storage.telemetry_enabled():
            storage.get_store().log_check(
                session_id=session.id,
                turn=session.state.turn,
                scene_id=session.state.scene_id,
                skill=res.skill,
                dc=res.dc,
                total=res.roll.total,
                success=res.success,
                degree=res.degree,
                expression=res.roll.expression,
            )
    except Exception:
        pass


def _narrative(skill: str, success: bool, degree: str) -> str:
    if degree == "大成功":
        head = "这一手漂亮极了。"
    elif degree == "大失败":
        head = "糟糕,事情被搞砸了。"
    elif success:
        head = "你成功了。"
    else:
        head = "你失败了。"
    body = {
        "侦查": "雾气太浓,视线被吞掉;你眯起眼睛,从被忽略的角落捞出一个细节。",
        "推理": "线索在脑中叮咚一声撞在一起,你隐约摸到了真相的轮廓。",
        "交涉": "对方措辞松动,气氛缓和下来。",
        "潜行": "你贴着墙根挪动,脚步轻得像雾。",
        "体能": "你鼓足一口气完成动作,呼哧带喘却稳稳落地。",
        "医疗": "手法干净利落,伤口被稳稳处理。",
        "科技": "设备发出一声清脆提示音,成功了。",
    }.get(skill, "")
    return f"{head}{body}"


def apply_command(session: GameSession, text: str) -> GameSession | None:
    """处理斜杠指令;返回 None 表示属于自由行动,应交给 DM 引擎。"""
    t = text.strip()
    if not t or t.lower() == "/help":
        add_message(
            session,
            "system",
            "system",
            "/roll 1d20+3 → 掷骰\n/check 侦查 → 技能检定(自动 DC)\n/scene → 查看场景卡\n/hp → 查看状态\n/restart → 重新开始\n自由行动:直接打字即可。",
        )
        return session

    if t.lower() == "/restart":
        new = start_session(session.id, session.state.player.name)
        add_message(
            new,
            "system",
            "system",
            "世界重置,时间回到开头。你重新站在孤儿院锈迹斑斑的铁门前。",
        )
        return new

    if t.lower() == "/scene":
        scene = SCENARIO["scenes"].get(session.state.scene_id)
        add_message(
            session,
            "card",
            "system",
            scene["name"] + "\n" + scene.get("desc", ""),
            {"scene_id": scene["id"], "image": SCENARIO["scene_images"].get(scene["id"], "")},
        )
        return session

    m = re.match(r"/roll\s+(.+)", t, re.IGNORECASE)
    if m:
        expr = m.group(1).strip()
        try:
            roll = dice.roll_expression(expr)
        except dice.DiceFormatError as e:
            add_message(session, "system", "system", str(e))
        else:
            s = session.stats
            s["rolls"] += 1
            total = roll.total
            sides = roll.sides
            degree = (
                "大成功"
                if roll.rolls and all(r == sides for r in roll.rolls)
                else ("大失败" if total <= 4 and sides >= 6 else "普通")
            )
            add_message(
                session,
                "roll",
                "dice",
                dice.summarize(roll),
                {"expression": expr, "total": total, "degree": degree},
            )
        return session

    m = re.match(r"/check\s*(.*)", t, re.IGNORECASE)
    if m:
        skill_arg = m.group(1).strip()
        res = run_check(session, skill_arg)
        skill_label = "技能检定" if skill_arg == "" else f"{res.skill}检定"
        add_message(
            session,
            "check",
            "dm",
            f"「{skill_label}」DC={res.dc}",
            {
                "degree": res.degree,
                "dc": res.dc,
                "total": res.roll.total,
                "success": res.success,
                "skill": res.skill,
            },
        )
        add_message(session, "story", "dm", res.narrative)
        add_message(session, "roll", "dice", dice.summarize(res.roll))
        return session

    if t.lower() == "/hp":
        p = session.state.player
        add_message(
            session,
            "system",
            "system",
            f"HP {p.hp}/{p.max_hp}（{p.hp_labels[min(p.hp, len(p.hp_labels) - 1)]}）",
        )
        return session

    return None


def advance_scene(session: GameSession, scene_id: str) -> Message | None:
    """场景推进:换场景时返回 DM 的入场白。"""
    scene = SCENARIO["scenes"].get(scene_id)
    if not scene:
        return None
    session.state.scene_id = scene_id
    return add_message(
        session,
        "story",
        "dm",
        scene.get("entry", ""),
        {"scene_id": scene_id},
    )
