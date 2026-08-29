"""默认剧本《雾中孤儿院》:单场景链 + NPC 设定。后续可扩展为剧情分支树。

每个场景:
  id / name / entry(开场白) / desc(氛围描述,用于场景卡) / dc_base(默认检定难度)
  hooks: 动作关键词 → (回应文本, 提议的技能名 or None=无需检定)
"""

from __future__ import annotations

import base64


def _b64(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

def _svg_scene(body: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="440" '
        'viewBox="0 0 700 440">'
        '<rect width="700" height="440" fill="#0b0e1a"/>'
        f'{body}'
        '</svg>'
    )
    return _b64(svg)

def _svg_npc(name: str, hair: str, cloth: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="700" '
        'viewBox="0 0 600 700">'
        '<rect width="600" height="700" fill="#0b0e1a"/>'
        '<ellipse cx="300" cy="625" rx="200" ry="28" fill="#000000" opacity="0.55"/>'
        '<ellipse cx="300" cy="470" rx="120" ry="170" fill="#131a2f"/>'
        '<circle cx="300" cy="285" r="85" fill="#d6b08a"/>'
        f'<path d="M220 285 a85 85 0 0 1 160 -0 L360 175 a80 80 0 0 0 -160 0 Z" fill="{hair}"/>'
        f'<path d="M215 290 a88 88 0 0 0 170 0" fill="{hair}" stroke="{hair}" stroke-width="26"/>'
        f'<rect x="268" y="378" width="64" height="135" rx="10" fill="{cloth}"/>'
        '<rect x="250" y="360" width="100" height="26" fill="#0d1120"/>'
        f'<text x="300" y="660" font-size="26" fill="#cbd3e6" text-anchor="middle">{name}</text>'
        '</svg>'
    )
    return _b64(svg)

def _fog(opacity: str = "0.22", color: str = "#8f9cc0") -> str:
    fog = ""
    for y, r in ((330, "470"), (360, "520"), (392, "560")):
        fog += f'<ellipse cx="350" cy="{y}" rx="{r}" ry="16" fill="{color}" opacity="{opacity}"/>'
    return fog

def _img_body(scene_id: str) -> str:
    if scene_id == "prologue":
        return (
            '<rect width="700" height="440" fill="#171d30"/>'
            '<rect x="0" y="340" width="700" height="100" fill="#06080f"/>'
            '<path d="M0 350 q180 14 700 8 v84 H0 Z" fill="#0a0e1a"/>'
            '<rect x="300" y="150" width="92" height="196" fill="#0d1120"/>'
            '<rect x="300" y="150" width="92" height="180" fill="none" stroke="#3a414f" stroke-width="6"/>'
            '<rect x="304" y="160" width="38" height="54" fill="none" stroke="#3a414f" stroke-width="5"/>'
            '<rect x="350" y="160" width="38" height="54" fill="none" stroke="#3a414f" stroke-width="5"/>'
            '<rect x="304" y="224" width="38" height="54" fill="none" stroke="#3a414f" stroke-width="5"/>'
            '<rect x="350" y="224" width="38" height="54" fill="none" stroke="#3a414f" stroke-width="5"/>'
            '<rect x="120" y="200" width="76" height="146" fill="#0d1120"/>'
            '<rect x="504" y="200" width="76" height="146" fill="#0d1120"/>'
            '<circle cx="612" cy="92" r="7" fill="#ffd269" opacity="0.85"/>'
            + _fog()
        )
    if scene_id == "hallway":
        return (
            '<rect width="700" height="440" fill="#161923"/>'
            '<rect x="0" y="0" width="700" height="120" fill="#211f29"/>'
            '<rect x="0" y="120" width="700" height="12" fill="#2e2b38"/>'
            '<circle cx="350" cy="52" r="13" fill="#fff3c4" opacity="0.5"/>'
            '<circle cx="270" cy="52" r="10" fill="#fff3c4" opacity="0.38"/>'
            '<circle cx="430" cy="52" r="10" fill="#fff3c4" opacity="0.38"/>'
            '<rect x="80" y="150" width="540" height="58" fill="none" stroke="#28242f" stroke-width="4"/>'
            '<rect x="104" y="240" width="120" height="150" fill="#10131d"/>'
            '<rect x="252" y="240" width="120" height="150" fill="#10131d"/>'
            '<rect x="400" y="240" width="120" height="150" fill="#10131d"/>'
            '<rect x="548" y="240" width="88" height="150" fill="#0d1018"/>'
            '<text x="104" y="226" font-size="20" fill="#8a90a6">7</text>'
            + _fog("0.3")
        )
    if scene_id == "room7":
        return (
            '<rect width="700" height="440" fill="#1c2029"/>'
            '<rect x="110" y="70" width="480" height="250" fill="#07090f"/>'
            '<rect x="128" y="92" width="230" height="206" fill="#0c0f16"/>'
            '<rect x="128" y="92" width="230" height="206" fill="none" stroke="#3c465e" stroke-width="5"/>'
            '<circle cx="243" cy="195" r="22" fill="#bfc8dd" opacity="0.10"/>'
            '<rect x="220" y="300" width="240" height="140" fill="#151923"/>'
            '<rect x="300" y="315" width="130" height="22" fill="#d9d4c4"/>'
            '<path d="M250 330 q120 -20 220 10 l0 90 q-110 24 -220 -10 Z" fill="#2a3040">'
            '</path>'
            '<ellipse cx="170" cy="350" rx="30" ry="12" fill="#d7d2c2"/>'
            '<path d="M168 330 q8 -26 18 -32 l-4 -14 -18 6 Z" fill="#d7d2c2"/>'
            + _fog("0.34")
        )
    if scene_id == "basement":
        shelves = ""
        for row in (0, 1, 2):
            y = 70 + row * 60
            shelves += (
                f'<rect x="40" y="{y}" width="110" height="12" fill="#39445c" opacity="0.7"/>'
                f'<rect x="300" y="{y}" width="110" height="12" fill="#39445c" opacity="0.7"/>'
                f'<rect x="560" y="{y}" width="110" height="12" fill="#39445c" opacity="0.7"/>'
            )
            for x in (50, 78, 106):
                shelves += f'<rect x="{x}" y="{y - 34}" width="18" height="32" rx="3" fill="#0b0e16" stroke="#5a6688" stroke-width="2"/>'
        return (
            '<rect width="700" height="440" fill="#101219"/>'
            '<rect x="0" y="150" width="700" height="150" fill="#0b0d13"/>'
            + shelves
            + '<text x="350" y="330" font-size="22" fill="#7c86a2" text-anchor="middle">剪 报</text>'
            + '<rect x="280" y="360" width="140" height="60" fill="#d8d3c0" rx="4"/>'
            + _fog("0.32", "#5c6683")
        )
    if scene_id == "end":
        return (
            '<rect width="700" height="440" fill="#eae6da"/>'
            '<rect x="0" y="320" width="700" height="120" fill="#d8d3c2"/>'
            '<circle cx="120" cy="90" r="58" fill="#fdf8ea"/>'
            '<rect x="230" y="150" width="230" height="180" fill="#cfc8b4"/>'
            '<rect x="230" y="150" width="230" height="180" fill="none" stroke="#a9a28c" stroke-width="6"/>'
            '<path d="M0 330 q240 22 700 8 v102 H0 Z" fill="#cfcabc"/>'
            + _fog("0.16", "#c9c1ab")
        )
    return '<rect width="700" height="440" fill="#10131c"/>' + _fog()

SCENARIO = {
    "id": "mist-orphanage",
    "title": "《雾中孤儿院》",
    "genre": "悬疑 · 微恐 · 单场景跑团",
    "skills": ["侦查", "推理", "交涉", "潜行", "体能", "医疗", "科技"],
    "npcs": {
        "keeper": {
            "npc_id": "keeper", "name": "老赵", "title": "守夜人",
            "desc": "佝偻着背,叼着半截烟,对访客戒心很重。",
            "relation": 0, "hp": 3,
            "portrait": _svg_npc("老赵", "#4a4a4a", "#c25a5a"),
        },
        "ghost": {
            "npc_id": "ghost", "name": "白影", "title": "廊道尽头的鬼影",
            "desc": "一个矮小的白色人形,头发遮住了大半张脸。",
            "relation": 0, "hp": 3,
            "portrait": _svg_npc("白影", "#dddddd", "#e6e6ea"),
        },
    },
    "scenes": {
        "prologue": {
            "id": "prologue", "name": "铁门之外", "dc_base": 8,
            "entry": (
                "1998年,东南沿海,一座废弃近二十年的孤儿院,静静埋在终年不散的浓雾里。\n"
                "你是收到匿名信赴约的调查员。信上只有一行字:【7号房,有人等你。】\n"
                "你站在锈迹斑斑的铁门前。门缝里泄出昏黄的灯光,似乎……有人?"
            ),
            "desc": "铁门半掩,雾里隐约能看到主楼的轮廓,二楼某扇窗户亮着灯。",
            "hooks": {
                "inspect": ("门锁是新的,门缝里卡着一封湿透的信,收件人写的是你的名字。", None),
                "roll_improv": "你摸了摸门封,发现门其实没锁,只是被雾和湿气卡住了。",
                "combat": "你对着铁门踢了一脚,声音在雾里荡开,门内那盏灯倏地灭了。",
                "flee": "雾太浓,你还没迈出两步就分不清来路。铁门在身后轻轻合上,像有人拉了一下。",
                "talk": "没有人回应。雾里只有你自己的呼吸声。",
            },
        },
        "room7": {
            "id": "room7", "name": "7号房", "dc_base": 11,
            "entry": (
                "你推开房间的门。房间里只有一张床、一扇封死的窗户,和地板上一只小小的白布鞋。\n"
                "床底下传出一阵极轻的抽泣声。窗玻璃上有字的痕迹,像是从里面往外写的。"
            ),
            "desc": "空荡的儿童房,窗玻璃蒙着雾,地板中央躺着一只孤零零的白布鞋。",
            "hooks": {
                "inspect": (
                    "你俯下身,床底的白影猛地抬头——孩子的脸,和合影里被涂黑的那张脸一模一样。", "侦查",
                ),
                "combat": "你刚抬手,抽泣声立刻停了。一根布鞋带从床底伸出来,缓缓缠上你的鞋尖。",
                "flee": "你转身欲逃,却发现门不知何时被锁上了。窗外,有什么东西的脸贴着玻璃。",
                "talk": "你轻声问话。床底安静了很久,然后传来一句几不可闻的:【……你是来带我走的吗。】",
            },
        },
        "hallway": {
            "id": "hallway", "name": "主楼走廊", "dc_base": 9,
            "entry": (
                "你推开主楼大门。灰尘在昏黄的吊灯下旋转。墙上挂着一排褪色的合影。\n"
                "走廊尽头是螺旋楼梯。左手边第一扇门上,钉着一张褪色门牌——【7号房】。"
            ),
            "desc": "一眼望不到头的走廊,灯忽明忽暗,楼梯隐没在雾气里。",
            "hooks": {
                "inspect": (
                    "那排合影里,每个孩子的眼睛都被涂黑了。最新的一张,角落里多了一个不属于任何孩子的影子。", "推理",
                ),
                "roll_improv": "【7号房】的门牌钉歪了。门把手上缠着一截浸湿的麻绳,像是刚从里面被拉断的。",
                "combat": "你握紧拳头朝虚空挥了一击,走廊那头的灯应声熄灭一盏,像某种回应。",
                "flee": "你刚转身,走廊那头的门缝里,一双惨白的眼睛正安静地看着你。",
                "talk": "脚步声停了,但你知道,有什么东西在听。",
            },
        },
        "basement": {
            "id": "basement", "name": "地下室", "dc_base": 10,
            "entry": (
                "楼梯尽头的门后,是地下室。\n"
                "铁架上一排排药瓶蒙着灰。墙角坐着老赵,他抬起头,眼神里没有害怕,只有疲惫。\n"
                "他问:“你都看见了?”地上摊着一盒泛黄的剪报。"
            ),
            "desc": "潮湿的地下室,铁架上摆满旧药瓶,墙角散落一摊剪报。",
            "hooks": {
                "inspect": (
                    "剪报头条:【孤儿院大火,孩子全部获救,唯独 7 号房的孩子失踪。】日期正是二十年前。", "推理",
                ),
                "combat": "老赵没躲,只摇摇头:“打我有用的话,二十年前就该有人打了。”",
                "flee": "你转身要走,老赵的声音追上来:“别怕那个影子。该怕的,是剪报盖住的事。”",
                "talk": "老赵盯着你:“你是第二个敢在夜里走进 7 号房的人。第一个……”他指了指那盒剪报。",
            },
        },
        "end": {
            "id": "end", "name": "结局:雾散", "is_terminal": True,
            "entry": (
                "清晨五点半,雾终于散了。\n"
                "你走出孤儿院,口袋里多了一双洗得干干净净的白布鞋。\n"
                "回头看,【7号房】的门牌掉在地上,背后,是一片纯白的墙。\n"
                "匿名信的第二行字在晨光里浮现:【谢谢你。替我把它带出去。】"
            ),
            "desc": "雾散尽,晨光落在空荡荡的孤儿院前,世界重新明亮。",
            "hooks": {},
        },
    },
}

SCENARIO["scene_images"] = {
    sc["id"]: _svg_scene(_img_body(sc["id"])) for sc in SCENARIO["scenes"].values()
}
# 剧情推进链:检查类检定成功后推进到下一场景
SCENARIO["scene_chain"] = {
    "prologue": "hallway",
    "hallway": "room7",
    "room7": "basement",
    "basement": "end",
}
# 每个场景:哪些技能检定成功会推进剧情
SCENARIO["advance_on"] = {
    "prologue": ["侦查", "推理"],
    "hallway": ["推理", "侦查"],
    "room7": ["侦查"],
    "basement": ["推理", "侦查"],
    "end": [],
}
# 关键词直达(便于测试跳场景)
SCENARIO["scene_shortcut"] = {
    "7号房": "room7",
    "门牌": "room7",
    "房间": "room7",
    "走廊": "hallway",
    "上二楼": "hallway",
    "楼上": "hallway",
    "地下室": "basement",
    "剪报": "basement",
    "老赵": "basement",
}
SCENARIO["scene_order"] = ["prologue", "hallway", "room7", "basement", "end"]
