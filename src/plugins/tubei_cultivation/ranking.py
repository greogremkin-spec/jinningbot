"""
晋宁会馆·秃贝五边形 4.1
排行榜系统

支持三种触发方式：
1. 直达式：灵力排行榜、嘿咻排行榜、聚灵排行榜...
2. 参数式：排行榜 嘿咻、排行榜 聚灵...
3. 斜杠式：/灵力排行榜、/排行榜 嘿咻...

仅展示馆内成员（core_member + admin + decision）
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message
from nonebot.params import CommandArg

from src.common.data_manager import data_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission


# ==================== 排行榜类型定义 ====================

RANKING_TYPES = {
    "灵力": {
        "title": "🏆 灵力总榜",
        "field": "sp",
        "format": lambda v: f"{v} 灵力",
        "desc": "按当前灵力值排名",
    },
    "嘿咻": {
        "title": "🐾 嘿咻收集榜",
        "field": "heixiu_count",
        "format": lambda v: f"{v} 只",
        "desc": "按捕获嘿咻总数排名",
    },
    "聚灵": {
        "title": "🧘 聚灵次数榜",
        "field": "total_meditation_count",
        "format": lambda v: f"{v} 次",
        "desc": "按累计聚灵次数排名",
    },
    "厨房": {
        "title": "🍽 厨房灾难榜",
        "field": "total_kitchen_bad",
        "format": lambda v: f"{v} 次黑暗料理",
        "desc": "按累计吃到黑暗料理次数排名",
    },
    "派遣": {
        "title": "🚩 派遣次数榜",
        "field": "total_expedition_count",
        "format": lambda v: f"{v} 次",
        "desc": "按累计派遣次数排名",
    },
}

# 别名映射（用户输入 → 标准key）
RANKING_ALIAS = {
    "": "灵力",
    "灵力": "灵力",
    "sp": "灵力",
    "嘿咻": "嘿咻",
    "聚灵": "聚灵",
    "修行": "聚灵",
    "厨房": "厨房",
    "派遣": "派遣",
    "探索": "派遣",
}


# ==================== 核心渲染函数 ====================

async def _render_ranking(bot: Bot, event: MessageEvent, ranking_key: str):
    """渲染并发送指定类型的排行榜"""
    perm = await check_permission(event, "排行榜", min_tier="allied")
    if not perm.allowed:
        await bot.send(event, perm.deny_message)
        return

    config = RANKING_TYPES.get(ranking_key)
    if not config:
        config = RANKING_TYPES["灵力"]
        ranking_key = "灵力"

    field = config["field"]
    formatter = config["format"]
    title = config["title"]

    # 获取馆内成员
    core_members = await data_manager.get_core_members()
    uid = str(event.user_id)

    # 构建排行数据
    rank_data = []
    for qq, member in core_members.items():
        spirit = await data_manager.get_spirit_data(qq)
        value = spirit.get(field, 0)
        name = member.get("spirit_name", f"妖灵{qq}")
        equipped_title = spirit.get("equipped_title", "")
        display_name = f"[{equipped_title}] {name}" if equipped_title else name
        rank_data.append((qq, display_name, value))

    rank_data.sort(key=lambda x: x[2], reverse=True)
    top_n = rank_data[:15]

    items = []
    for qq, name, value in top_n:
        items.append((name, formatter(value)))

    # 找当前用户排名
    my_rank = None
    for idx, (qq, name, value) in enumerate(rank_data):
        if qq == uid:
            my_rank = idx + 1
            break

    # 构建底部：其他榜单快捷入口
    other_boards = []
    for key in RANKING_TYPES:
        if key != ranking_key:
            other_boards.append(f"{key}榜")
    other_str = " | ".join(other_boards)

    footer_parts = []
    if my_rank:
        footer_parts.append(f"你的排名：第 {my_rank} 名")
    footer_parts.append(f"其他榜：{other_str}")

    card = ui.render_ranking(
        title,
        items,
        footer="\n".join(footer_parts)
    )
    await bot.send(event, card)


# ==================== 参数式指令（原有，保留兼容） ====================

ranking_cmd = on_command("排行榜", aliases={"排行", "榜单"}, priority=5, block=True)

@ranking_cmd.handle()
async def handle_ranking(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    sub_type = args.extract_plain_text().strip()
    ranking_key = RANKING_ALIAS.get(sub_type)

    if ranking_key is None:
        # 未知类型，显示可用榜单
        lines = ["可用排行榜：", ""]
        for key, info in RANKING_TYPES.items():
            lines.append(f"  {info['title']}")
            lines.append(f"    → {key}排行榜 | {key}榜")
            lines.append(f"    → 排行榜 {key}")
            lines.append("")
        await ranking_cmd.finish(ui.render_panel(
            "🏆 排行榜系统",
            "\n".join(lines),
            footer="💡 直接发送 灵力排行榜 即可查看"
        ))
        return

    await _render_ranking(bot, event, ranking_key)
    await ranking_cmd.finish()


# ==================== 直达式指令（新增） ====================

# 灵力排行榜
power_ranking_cmd = on_command(
    "灵力排行榜", aliases={"灵力榜", "灵力排行"},
    priority=4, block=True
)
@power_ranking_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    await _render_ranking(bot, event, "灵力")

# 嘿咻排行榜
heixiu_ranking_cmd = on_command(
    "嘿咻排行榜", aliases={"嘿咻榜", "嘿咻排行"},
    priority=4, block=True
)
@heixiu_ranking_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    await _render_ranking(bot, event, "嘿咻")

# 聚灵排行榜
meditation_ranking_cmd = on_command(
    "聚灵排行榜", aliases={"聚灵榜", "聚灵排行"},
    priority=4, block=True
)
@meditation_ranking_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    await _render_ranking(bot, event, "聚灵")

# 厨房排行榜
kitchen_ranking_cmd = on_command(
    "厨房排行榜", aliases={"厨房榜", "厨房排行"},
    priority=4, block=True
)
@kitchen_ranking_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    await _render_ranking(bot, event, "厨房")

# 派遣排行榜
expedition_ranking_cmd = on_command(
    "派遣排行榜", aliases={"派遣榜", "派遣排行"},
    priority=4, block=True
)
@expedition_ranking_cmd.handle()
async def _(bot: Bot, event: MessageEvent):
    await _render_ranking(bot, event, "派遣")