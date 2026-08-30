"""剧本世界设定:D&D 5e 默认世界大纲 —— 只含【世界骨架/大分支】元数据,不含预写对话链。

剧本(WorldOutline)与角色卡互不绑定;玩家可导入自定规则文本,也可靠 SSE 进度生成世界大纲。
剧情演进由 DM(LLM)按玩家实时自由指令每一轮裁决。
"""

from __future__ import annotations

import base64

from .models import WorldOutline


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
    "id": "sunbell-ash-tomb",
    "title": "《风铃镇·灰烬墓穴》",
    "genre": "剑与魔法 · D&D 5e · 悬疑冒险",
    "setting": "凯旋大陆,旧帝国崩塌已百年,刀剑与魔法并存,巨龙沉睡于山脉,诸城自治。冒险者公会遍布,悬赏与传说就是通行的货币。",
    "mainline": "铁匠老格的女儿蕾拉接连失踪,镇上夜里钟声常无故自鸣。线索指向镇外黑松森林与其中的「灰烬墓穴」——墓穴深处封印着缚灵·残响,它正以活人精魄续命,钟声与失踪案都是它的手笔。",
    "rules_text": (
        "D&D 5e 基础规则:行动用 d20 属性检定(1-20),检定值=d20+属性修正(+熟练加值),达到 DC 即成功;"
        "难度由 DM 依剧情设定(简单5/普通10/困难15/挑战20/极难25);成功检定奖励经验;HP 归零倒地,长休回满;"
        "法术按环使用法术位,长休回复;战斗各轮由 DM 裁决。"
    ),
    "birthplaces": {
        "孤儿院": "你在镇上的圣礼孤儿院长大,熟悉每一条巷子与密道。",
        "绿野农庄": "你在北边农庄长大,熟悉荒野、牲畜与天气。",
        "北境商队": "你随商队长大,见多识广,擅长议价与认路。",
        "圣白城教会": "你被修士抚养长大,熟读经文与古代史。",
        "德鲁伊林地": "你在林间长大,与自然和野兽为伴。",
        "码头街": "你在码头街讨生活,嘴皮子利索,消息灵通。",
    },
    "npcs": {
        "mayor": {"npc_id": "mayor", "name": "马瑞卡", "title": "镇长", "desc": "银发中年妇人,眉间总锁着担忧,不愿多谈失踪案背后的风声。", "relation": 10, "hp": 8, "portrait": _svg_npc("马瑞卡", "#e0e0e0", "#7a4f9c")},
        "smith": {"npc_id": "smith", "name": "老格", "title": "铁匠", "desc": "粗粝的手掌,满身炉灰,悬赏就贴在自己的铺子门口。", "relation": 15, "hp": 12, "portrait": _svg_npc("老格", "#5b4a39", "#8a4b2f")},
        "barmaid": {"npc_id": "barmaid", "name": "雪梨", "title": "酒馆老板娘", "desc": "精明圆滑,把各路人马的闲话都装进耳朵里。", "relation": 5, "hp": 6, "portrait": _svg_npc("雪梨", "#4a1a1a", "#c25a5a")},
        "priest": {"npc_id": "priest", "name": "塞拉斯", "title": "神殿祭司", "desc": "清瘦,声音沉稳,知道墓穴封印的部分真相。", "relation": 10, "hp": 8, "portrait": _svg_npc("塞拉斯", "#dddddd", "#e6e6ea")},
        "crow": {"npc_id": "crow", "name": "乌鸦", "title": "神秘旅人", "desc": "斗篷遮脸,只在夜里出现,话里常带半句预言。", "relation": 0, "hp": 10, "portrait": _svg_npc("乌鸦", "#222222", "#2c2c34")},
        "leila": {"npc_id": "leila", "name": "蕾拉", "title": "失踪的铁匠之女", "desc": "金发少女,最后被人看见是三天前走进黑松森林。", "relation": 0, "hp": 6, "portrait": _svg_npc("蕾拉", "#d8a91b", "#4a7a8c")},
    },
    "scenes": {
        "prologue": {"id": "prologue", "name": "风铃镇广场", "is_start": True, "entry": (
            "深秋的傍晚,风铃镇集市收了摊。铁匠老格铺门口的悬赏在风里扑打:女儿蕾拉三天前走进黑松森林,至今未归。\n"
            "你站在广场的水井旁,手里攥着冒险者公会的简章。雾从镇外的森林边缘漫过来,掩住钟楼,只有风铃在响。\n——你的冒险,从这一刻开始。"
        ), "desc": "广场中央一口老水井,铁匠铺、酒馆与神殿围成一圈,钟楼隐在雾里。"},
        "market": {"id": "market", "name": "酒馆·铃铛与玫瑰", "entry": (
            "酒馆里暖光混着麦酒味。老板娘雪梨把闲话当酒卖:『前天有个斗篷人打听灰烬墓穴的事,出手就是金币。』\n你可以在酒馆打听消息、雇佣帮手、出售或交换装备。"
        ), "desc": "一楼大厅座无虚席,墙上钉满悬赏与旧地图。"},
        "forest": {"id": "forest", "name": "黑松森林", "entry": (
            "林子里光线被树冠削成碎斑,地面松针叠着旧脚印。远处墓穴方向传来一声不似狼嚎的低响。\n夜风里夹着铁锈与蜡的气味——灰烬墓穴,就在林深之处。"
        ), "desc": "浓密黑松遮天,雾在树根之间流淌,一条被踏平的旧路指向墓穴。"},
        "tomb": {"id": "tomb", "name": "灰烬墓穴", "entry": (
            "石门上镌着旧王朝的封印纹,门缝里漏出暗红色光。地上散落着被拖行的痕迹与一块蕾拉的银发带。\n深处,隐约有一种「钟声」,在无人敲击地响着。"
        ), "desc": "潮湿甬道两侧是空棺架,暗红光来自最深处的神殿方向。"},
        "sanctum": {"id": "sanctum", "name": "墓穴神殿", "entry": (
            "祭坛上,缚灵·残响以黑雾塑形,蕾拉昏睡在它脚边的法阵中,周围的烛火随它呼吸明灭。\n『迟到的勇者,』它开口,『要么献上你的精魄,要么,带她走。』"
        ), "desc": "穹顶破开一线天光,祭坛四角燃着蓝焰,法阵在地上缓缓旋转。"},
        "end": {"id": "end", "name": "结局·黎明的钟声", "is_terminal": True, "entry": (
            "缚灵在晨光里碎裂成灰烬。蕾拉睁开眼睛,第一句话是『谢谢』。\n镇上的钟声终于正常地敲响了——为平安,也为远行者。你的第一个冒险,就此画上句号。"
        ), "desc": "雾散,日光落在灰烬与晨露之上,冒险者公会的印章盖在你的冒险简报上。"},
    },
    "branches": {
        "prologue": [
            {"target": "market", "label": "进酒馆打听消息"},
            {"target": "forest", "label": "直奔黑松森林"},
        ],
        "market": [{"target": "forest", "label": "酒后出发,入林追查"}],
        "forest": [
            {"target": "tomb", "label": "循旧路深入灰烬墓穴"},
            {"target": "prologue", "label": "返回小镇修整补给"},
        ],
        "tomb": [
            {"target": "sanctum", "label": "走进墓穴神殿对阵缚灵"},
            {"target": "forest", "label": "暂退林间重整旗鼓"},
        ],
        "sanctum": [{"target": "end", "label": "击败缚灵,迎黎明的结局"}],
        "end": [],
    },
    "scene_order": ["prologue", "market", "forest", "tomb", "sanctum", "end"],
    "encounters": ["黑松林的饿狼群", "灰烬墓穴的食腐尸怪", "想独吞悬赏的赏金猎人", "墓穴神殿的缚灵·残响"],
}

SCENARIO["scene_images"] = {sc["id"]: _svg_scene(sc["name"]) for sc in SCENARIO["scenes"].values()}


def default_world() -> WorldOutline:
    """由默认剧本字典构造 WorldOutline(会话默认世界)。"""
    return WorldOutline(
        id=SCENARIO["id"],
        title=SCENARIO["title"],
        genre=SCENARIO["genre"],
        setting=SCENARIO["setting"],
        mainline=SCENARIO["mainline"],
        rules_text=SCENARIO["rules_text"],
        birthplaces=dict(SCENARIO["birthplaces"]),
        npcs={k: dict(v) for k, v in SCENARIO["npcs"].items()},
        scenes={k: dict(v) for k, v in SCENARIO["scenes"].items()},
        scene_order=list(SCENARIO["scene_order"]),
        scene_images=dict(SCENARIO["scene_images"]),
        branches={k: [dict(b) for b in v] for k, v in SCENARIO["branches"].items()},
        encounters=list(SCENARIO["encounters"]),
    )
