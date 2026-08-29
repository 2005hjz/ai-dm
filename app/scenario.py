"""剧本世界设定：只保留【大剧情分支】元数据，不含任何离线预先写定的剧情台词 / 推进链 / 检定映射。

剧情演进完全由 DM（DeepSeek-V4-Flash / 任何 OpenAI 兼容 LLM）按玩家实时自由指令判决：
- LLM 建议哪个大分支 → 在 `DMPlan.advance_scene` 填对应 zone id，引擎仅做合法性校验 + 场景卡渲染；
- 骰子检定由引擎按统一规则实时裁决（见 `gameplay.run_check`）；
- 生图 API / 本地 SVG mock 按本文的场景氛围与 NPC 设定渲染场景卡与角色画像。
"""

from __future__ import annotations

import base64


def _b64(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _svg_scene(name: str) -> str:
    body = ""
    for y, rx, opacity in ((330, "470", "0.22"), (360, "520", "0.24"), (392, "560", "0.2")):
        body += f'<ellipse cx="350" cy="{y}" rx="{rx}" ry="16" fill="#8f9cc0" opacity="{opacity}"/>'
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="440" viewBox="0 0 700 440">'
        '<rect width="700" height="440" fill="#0b0e1a"/>'
        '<rect x="0" y="300" width="700" height="140" fill="#06080f"/>'
        '<rect x="300" y="150" width="92" height="150" fill="none" stroke="#3a414f" stroke-width="6"/>'
        '<circle cx="612" cy="92" r="7" fill="#ffd269" opacity="0.85"/>'
        f'<text x="350" y="420" font-size="26" fill="#cbd3e6" text-anchor="middle">{name}</text>' + body + "</svg>"
    )
    return _b64(svg)


def _svg_npc(name: str, hair: str, cloth: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="700" viewBox="0 0 600 700">'
        '<rect width="600" height="700" fill="#0b0e1a"/>'
        '<ellipse cx="300" cy="625" rx="200" ry="28" fill="#000000" opacity="0.55"/>'
        '<ellipse cx="300" cy="470" rx="120" ry="170" fill="#131a2f"/>'
        '<circle cx="300" cy="285" r="85" fill="#d6b08a"/>'
        f'<path d="M220 285 a85 85 0 0 1 160 -0 L360 175 a80 80 0 0 0 -160 0 Z" fill="{hair}"/>'
        f'<path d="M215 290 a88 88 0 0 0 170 0" fill="{hair}" stroke="{hair}" stroke-width="26"/>'
        f'<rect x="268" y="378" width="64" height="135" rx="10" fill="{cloth}"/>'
        '<rect x="250" y="360" width="100" height="26" fill="#0d1120"/>'
        f'<text x="300" y="660" font-size="26" fill="#cbd3e6" text-anchor="middle">{name}</text>'
        "</svg>"
    )
    return _b64(svg)


SCENARIO = {
    "id": "mist-orphanage",
    "title": "《雾中孤儿院》",
    "genre": "悬疑 · 微恐 · 无限分支跑团",
    "skills": ["侦查", "推理", "交涉", "潜行", "体能", "医疗", "科技"],
    "npcs": {
        "keeper": {
            "npc_id": "keeper",
            "name": "老赵",
            "title": "守夜人",
            "desc": "佝偻着背，叼着半截烟，对访客戒心很重。",
            "relation": 0,
            "hp": 3,
            "portrait": _svg_npc("老赵", "#4a4a4a", "#c25a5a"),
        },
        "ghost": {
            "npc_id": "ghost",
            "name": "白影",
            "title": "廊道尽头的鬼影",
            "desc": "一个矮小的白色人形，头发遮住了大半张脸。",
            "relation": 0,
            "hp": 3,
            "portrait": _svg_npc("白影", "#dddddd", "#e6e6ea"),
        },
    },
    # 大剧情分支（剧本地图 zone）：仅描述「这是一个怎样的空间」，不含任何玩家台词挂钩。
    # 玩家具体怎么演、分支间怎么走动、要不要检定，全部由 DM 在当轮实时判决。
    "scenes": {
        "prologue": {
            "id": "prologue",
            "name": "铁门之外",
            "is_start": True,
            "entry": (
                "1998年，东南沿海，一座废弃近二十年的孤儿院，静静埋在终年不散的浓雾里。\n"
                "你是收到匿名信赴约的调查员。信上只有一行字：【7号房，有人等你。】\n"
                "你站在锈迹斑斑的铁门前。门缝里泄出昏黄的灯光，似乎……有人？"
            ),
            "desc": "铁门半掩，雾里隐约能看见主楼的轮廓，二楼某扇窗户亮着灯。",
        },
        "hallway": {
            "id": "hallway",
            "name": "主楼走廊",
            "entry": (
                "主楼内墙皮剥落，吊灯在头顶忽明忽暗。左右延伸的走廊尽头埋进雾气。\n"
                "墙上挂着一排褪色合影，尽头是通往楼上的螺旋楼梯。"
            ),
            "desc": "一眼望不到头的走廊，灯忽明忽暗，楼梯隐没在雾气里。",
        },
        "room7": {
            "id": "room7",
            "name": "7号房",
            "entry": (
                "推开【7号房】的门，房间里只有一张床、一扇封死的窗户，和地板中央一只小小的白布鞋。\n"
                "空气里浮着极淡的、被刻意藏过的呼吸声。"
            ),
            "desc": "空荡的儿童房，窗玻璃蒙着雾，地板中央躺着一只孤零零的白布鞋。",
        },
        "basement": {
            "id": "basement",
            "name": "地下室",
            "entry": (
                "楼梯尽头的门后是潮湿的地下室。铁架上摆满蒙灰的旧药瓶，墙角摊着一盒泛黄的剪报。\n"
                "守夜人老赵坐在那里，抬起头，目光里没有害怕，只有疲惫。"
            ),
            "desc": "潮湿的地下室，铁架上摆满旧药瓶，墙角散落一摊剪报。",
        },
        "end": {
            "id": "end",
            "name": "结局 · 雾散",
            "is_terminal": True,
            "entry": (
                "清晨五点半，雾终于散了。孤儿院在晨光里变得安静而普通。\n你走出铁门，回头看，那盏亮了一夜的灯已经熄了。"
            ),
            "desc": "雾散尽，晨光落在空荡荡的孤儿院前，世界重新明亮。",
        },
    },
    # 大剧情分支（从哪个 zone 可以走到哪些 zone）——渲染分支树 + 注入 DM 系统提示词。
    "branches": {
        "prologue": [
            {"target": "hallway", "label": "推开主楼大门，进入走廊探索"},
            {"target": "room7", "label": "循着匿名信直接走向7号房"},
        ],
        "hallway": [
            {"target": "room7", "label": "走进钉着褪色门牌的7号房"},
            {"target": "basement", "label": "沿螺旋楼梯下到地下室"},
        ],
        "room7": [
            {"target": "basement", "label": "追查真相，逼问守夜人/查阅地下室剪报"},
            {"target": "end", "label": "给出你的裁决，迎来雾散结局"},
        ],
        "basement": [
            {"target": "end", "label": "真相揭晓，迎来雾散结局"},
        ],
        "end": [],
    },
    # 大剧情分支的展示顺序（用于分支树 / 预热渲染的顺序）。
    "scene_order": ["prologue", "hallway", "room7", "basement", "end"],
}

SCENARIO["scene_images"] = {sc["id"]: _svg_scene(sc["name"]) for sc in SCENARIO["scenes"].values()}
