"""
晋宁会馆·秃贝五边形 4.1
引导系统

4.0 改动：
1. 菜单从 command_registry 自动生成
2. 板块菜单支持 /行政板块 和纯文字 行政板块
3. 说明从 command_registry 的 help_detail 自动读取
4. 三段式板块卡片（全称-简介-指令）
5. 不同群等级显示不同菜单
6. 去除官网链接
7. 指令展示优先纯文字
"""

from nonebot import on_command, on_keyword
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, PrivateMessageEvent, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.adapters import Message
from nonebot.plugin import PluginMetadata

from src.common.command_registry import COMMANDS, MENU_SECTIONS
from src.plugins.tubei_system.config import TUBEI_FULL_NAME
from pathlib import Path

from src.common.ui_renderer import ui
from src.common.group_manager import group_manager, TIER_CORE, TIER_ALLIED, TIER_PUBLIC
from src.common.permission import check_permission
from src.common.command_registry import (
    COMMANDS, MENU_SECTIONS,
    get_commands_by_section,
    get_help_detail,
    get_section_help_keywords,
)

__plugin_meta__ = PluginMetadata(
    name="秃贝指引系统",
    description="菜单/说明/关于/加入引导",
    usage="菜单, 说明, /关于",
)

# 群等级优先级
TIER_PRIORITY = {
    TIER_CORE: 0,
    TIER_ALLIED: 1,
    TIER_PUBLIC: 2,
}


def _tier_meets(current_tier: str, required_tier: str) -> bool:
    """检查当前群等级是否满足最低要求"""
    return TIER_PRIORITY.get(current_tier, 99) <= TIER_PRIORITY.get(required_tier, 99)


def _get_cmd_trigger_display(cmd: dict) -> str:
    """获取指令的展示文本（优先纯文字）"""
    if cmd.get("text"):
        return cmd["text"][0]
    elif cmd.get("slash"):
        return f"/{cmd['slash'][0]}"
    return ""


# ==================== 板块详细菜单生成 ====================

def _build_section_card(section_id: str, group_tier: str, user_id: str = "") -> str:

    from src.plugins.tubei_system.config import system_config
    is_superuser = user_id in system_config.superusers
    is_admin = user_id in system_config.tubei_admins or is_superuser

    """
    根据板块ID和群等级生成板块详细卡片

    三段式结构（每个模块）：
      模块全称
        一句话简介
      👉指令：触发词
    """
    # 判断用户权限
    from src.plugins.tubei_system.config import system_config
    is_superuser = user_id in system_config.superusers
    is_admin = user_id in system_config.tubei_admins or is_superuser


    section = MENU_SECTIONS.get(section_id)
    if not section:
        return ""

    cmds = get_commands_by_section(section_id)
    if not cmds:
        return ""

    lines = []
    has_visible = False

    for cmd in cmds:
        # 群等级过滤
        min_tier = cmd.get("min_tier", "public")
        if not _tier_meets(group_tier, min_tier):
            continue

        # 馆内专属过滤
        if cmd.get("core_only") and group_tier != "core":
            continue

        # 管理/决策专属过滤
        if cmd.get("admin_only") and not is_admin:
            continue
        if cmd.get("decision_only") and not is_superuser:
            continue

        has_visible = True
        display_name = cmd.get("display_name", "")
        description = cmd.get("description", "")
        trigger = _get_cmd_trigger_display(cmd)

        # 带参数的指令展示
        if cmd.get("has_args") and trigger:
            if cmd["id"] == "duel":
                trigger = f"{trigger} @某人"
            elif cmd["id"] in ("use_item", "lore", "unlock", "ranking", "title", "expedition"):
                trigger = trigger  # 无参数时就显示基础词

        lines.append(f"【{display_name}】")
        lines.append(f"    {description}")
        lines.append(f"👉 指令：{trigger}")
        lines.append("")

    if not has_visible:
        return ""

    icon = section.get("icon", "")
    title = section.get("title", section.get("name", ""))
    subtitle = section.get("subtitle", "")

    content = "\n".join(lines)

    return ui.render_panel(
        f"{icon} {title}",
        f"{subtitle}\n\n{content}",
        footer="👉输入  说明 [功能名]  查看详细规则"
    )


# ==================== 总览菜单生成 ====================

def _build_main_menu(group_tier: str, user_id: str = "") -> str:

    from src.plugins.tubei_system.config import system_config
    is_superuser = user_id in system_config.superusers
    is_admin = user_id in system_config.tubei_admins or is_superuser

    """生成简化总览菜单（根据群等级过滤板块）"""
    lines = []
    lines.append("纯文字指令可触发秃贝 | @秃贝 闲聊\n")

    from src.plugins.tubei_system.config import system_config
    is_superuser = user_id in system_config.superusers
    is_admin = user_id in system_config.tubei_admins or is_superuser

    for section_id, section in MENU_SECTIONS.items():
        # 公开群过滤
        if group_tier == "public" and not section.get("display_in_public", False):
            continue
        # 新增：管理板块仅管理员可见
        if section_id == "console" and not is_admin:
            continue


        icon = section.get("icon", "")
        name = section.get("name", "")
        subtitle = section.get("subtitle", "")
        text_trigger = section.get("text_trigger", "")

        lines.append(f"【{icon} {name}】")
        lines.append(f"    {subtitle}")
        lines.append(f"👉 指令：{text_trigger}")
        lines.append("")

    # 公开群额外提示
    if group_tier == "public":
        lines.append("📌 更多修行玩法可在晋宁会馆体验~")
        lines.append("📌 私聊秃贝发送「加入会馆」了解详情")

    content = "\n".join(lines)

    return ui.render_panel(
        TUBEI_FULL_NAME,
        content,
                footer="👉输入  查看指令  查看所有可用指令\n👉输入  [板块名]  查看详细菜单\n👉输入  说明 [功能名]  查看规则"
    )


# ==================== 对外暴露的核心函数（供 text_dispatcher 调用） ====================

async def _handle_menu(bot: Bot, event: MessageEvent):
    """菜单核心逻辑"""
    if isinstance(event, GroupMessageEvent):
        group_tier = group_manager.get_group_tier(event.group_id)
    else:
        group_tier = "core"

    menu = _build_main_menu(group_tier, user_id=str(event.user_id))
    await bot.send(event, menu)


async def _send_section_menu(bot: Bot, event: MessageEvent, section_id: str):
    """发送指定板块的详细菜单"""
    if isinstance(event, GroupMessageEvent):
        group_tier = group_manager.get_group_tier(event.group_id)
    else:
        group_tier = "core"

    card = _build_section_card(section_id, group_tier, user_id=str(event.user_id))
    if card:
        await bot.send(event, card)
    else:
        await bot.send(event, ui.info("该板块在当前群不可用~"))


async def _handle_help(bot: Bot, event: MessageEvent, key: str = ""):
    """说明核心逻辑"""
    if not key:
        keywords = get_section_help_keywords()
        available = "、".join(keywords)
        await bot.send(event, ui.info(
            f"请指定功能名称。\n"
            f"📌 例如：说明 聚灵\n\n"
            f"可查询：{available}"
        ))
        return

    content = get_help_detail(key)
    if not content:
        await bot.send(event, ui.info(f"未找到「{key}」的说明。"))
        return

    await bot.send(event, ui.render_panel(f"功能说明 · {key}", content))



async def _handle_view_commands(bot: Bot, event: MessageEvent):
    """查看所有可用指令（完整版，纯文字优先）"""
    if isinstance(event, GroupMessageEvent):
        group_tier = group_manager.get_group_tier(event.group_id)
    else:
        group_tier = "core"

    lines = []

    for sec_id, sec_info in MENU_SECTIONS.items():
        if sec_id == "console":
            continue
        if sec_id == "_guide":
            continue
        if group_tier == "public" and not sec_info.get("display_in_public", False):
            continue

        cmd_lines = []
        for cmd in COMMANDS:
            if cmd.get("section") != sec_id:
                continue
            if cmd.get("hidden"):
                continue
            if cmd.get("admin_only"):
                continue

            min_tier = cmd.get("min_tier", "public")
            if not _tier_meets(group_tier, min_tier):
                continue
            if cmd.get("core_only") and group_tier != "core":
                continue

            display_name = cmd.get("display_name", "")
            slash_list = cmd.get("slash", [])
            text_list = cmd.get("text", [])

            # 构建触发词：纯文字在前，斜杠在后
            text_triggers = []
            slash_triggers = []

            if text_list:
                for t in text_list:
                    if t not in text_triggers:
                        text_triggers.append(t)

            if slash_list:
                for s in slash_list:
                    # 避免和纯文字重复
                    if s not in text_triggers:
                        slash_triggers.append(f"/{s}")

            if not text_triggers and not slash_triggers:
                continue

            # 构建输出行
            cmd_lines.append(f"【{display_name}】")

            # 纯文字触发词
            if text_triggers:
                # 每行最多放3个，防超宽
                for i in range(0, len(text_triggers), 3):
                    chunk = text_triggers[i:i+3]
                    line = " | ".join(chunk)
                    if i == 0:
                        cmd_lines.append(f"  纯文字：{line}")
                    else:
                        cmd_lines.append(f"　　　　　{line}")

            # 斜杠触发词
            if slash_triggers:
                for i in range(0, len(slash_triggers), 3):
                    chunk = slash_triggers[i:i+3]
                    line = " | ".join(chunk)
                    if i == 0:
                        cmd_lines.append(f"  斜杠：{line}")
                    else:
                        cmd_lines.append(f"　　　　{line}")

            # 如果只有斜杠没有纯文字
            if not text_triggers and slash_triggers:
                pass  # 已在上面处理

        if cmd_lines:
            icon = sec_info.get("icon", "▪")
            name = sec_info.get("name", "")
            lines.append(f"{'━' * 15}")
            lines.append(f"{icon}【{name}】")
            lines.append("")
            lines.extend(cmd_lines)
            lines.append("")

    if not lines:
        await bot.send(event, ui.info("当前群没有可用的指令~"))
        return

    # 底部引导
    lines.append("━" * 15)
    lines.append("💡 纯文字直接发送即可触发")
    lines.append("💡 斜杠指令需带 / 前缀")
    lines.append("💡 说明 [功能名] 查看规则")
    lines.append("⚙ 管理员发送 管理员指令")

    content = "\n".join(lines)

    # 超长分段发送
    if len(content) > 1500:
        parts = content.split("━" * 15)
        for i, part in enumerate(parts):
            part = part.strip()
            if part:
                await bot.send(event, part)
    else:
        await bot.send(event, f"✦ {TUBEI_FULL_NAME} · 全指令清单\n{content}")


async def _handle_admin_commands(bot: Bot, event: MessageEvent):
    """查看管理员专属指令"""
    uid = str(event.user_id)
    from src.plugins.tubei_system.config import system_config
    is_superuser = uid in system_config.superusers
    is_admin = uid in system_config.tubei_admins or is_superuser

    if not is_admin:
        await bot.send(event, ui.info("此指令仅限管理组/决策组使用。"))
        return

    lines = []

    # 行政管理指令（管理组可用）
    admin_cmds = []
    for cmd in COMMANDS:
        if not cmd.get("admin_only"):
            continue
        display_name = cmd.get("display_name", "")
        slash_list = cmd.get("slash", [])
        trigger_str = " | ".join([f"/{s}" for s in slash_list])
        desc = cmd.get("description", "")
        admin_cmds.append(f"  {display_name}\n    → {trigger_str}\n    {desc}")

    if admin_cmds:
        lines.append("🏛 【行政管理指令】(管理组+)")
        lines.append("─" * 18)
        lines.extend(admin_cmds)
        lines.append("")

    # 决策组控制台指令
    console_cmds = []
    for cmd in COMMANDS:
        if cmd.get("section") != "console":
            continue
        if cmd.get("decision_only") and not is_superuser:
            continue

        display_name = cmd.get("display_name", "")
        slash_list = cmd.get("slash", [])
        desc = cmd.get("description", "")
        trigger_str = " | ".join([f"/{s}" for s in slash_list])
        console_cmds.append(f"  {display_name}\n    → {trigger_str}\n    {desc}")

    if console_cmds:
        lines.append("⚙ 【控制台指令】(决策组专用)")
        lines.append("─" * 18)
        lines.extend(console_cmds)
        lines.append("")

    if not lines:
        await bot.send(event, ui.info("没有可用的管理指令。"))
        return

    content = "\n".join(lines)
    card = ui.render_panel(
        "⚙ 管理员指令清单",
        content,
        footer="💡 所有管理指令仅支持 /斜杠 触发"
    )
    await bot.send(event, card)



# ==================== 指令注册 ====================

# /菜单
menu_cmd = on_command("菜单", priority=10, block=True)

# /指令 /查看指令 /所有指令
view_commands_cmd = on_command("指令", aliases={"查看指令", "所有指令"}, priority=10, block=True)

#用户使用手册
manual_cmd = on_command("使用手册", aliases={"用户手册", "用户使用手册", "新手指南"}, priority=10, block=True)

#查看管理员指令
admin_commands_cmd = on_command("管理员指令", aliases={"管理指令"}, priority=10, block=True)

# /行政板块 /修行板块 /娱乐板块
section_cmds = {}
for sid, sinfo in MENU_SECTIONS.items():
    slash_trigger = sinfo.get("slash_trigger", "")
    if slash_trigger:
        # 自动生成 "版块" 别名
        aliases = {slash_trigger}
        if "板块" in slash_trigger:
            aliases.add(slash_trigger.replace("板块", "版块"))

        section_cmds[sid] = on_command(slash_trigger, aliases=aliases, priority=10, block=True)
# /说明
help_cmd = on_command("说明", aliases={"规则", "怎么玩"}, priority=10, block=True)

# /关于
about_cmd = on_command("关于", priority=10, block=True)

# 加入引导（关键词触发）
join_cmd = on_keyword({"加入会馆", "加入晋宁", "加入晋宁会馆", "怎么加入"}, priority=10, block=True)


# ==================== Handler ====================

@menu_cmd.handle()
async def handle_menu(bot: Bot, event: MessageEvent):
    await _handle_menu(bot, event)
    await menu_cmd.finish()

@view_commands_cmd.handle()
async def handle_view_commands(bot: Bot, event: MessageEvent):
    await _handle_view_commands(bot, event)
    await view_commands_cmd.finish()

@admin_commands_cmd.handle()
async def handle_admin_commands(bot: Bot, event: MessageEvent):
    await _handle_admin_commands(bot, event)
    await admin_commands_cmd.finish()


# 动态注册板块菜单handler
for _sid, _cmd in section_cmds.items():
    def _make_handler(section_id):
        async def _handler(bot: Bot, event: MessageEvent):
            await _send_section_menu(bot, event, section_id)
        return _handler

    _cmd.handle()(_make_handler(_sid))


@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    key = args.extract_plain_text().strip()
    await _handle_help(bot, event, key)
    await help_cmd.finish()


@about_cmd.handle()
async def handle_about(bot: Bot, event: MessageEvent):
    about_text = group_manager.get_about_text()
    footer = "想加入？私聊秃贝发送「加入会馆」"
    await about_cmd.finish(ui.render_panel("关于晋宁会馆", about_text, footer=footer))


@join_cmd.handle()
async def handle_join(bot: Bot, event: MessageEvent):
    if isinstance(event, PrivateMessageEvent):
        join_text = group_manager.get_join_text()
        await join_cmd.finish(ui.render_panel(
            "欢迎加入晋宁会馆！",
            join_text,
            footer="期待你的到来~"
        ))
    else:
        await join_cmd.finish(ui.render_panel(
            "关于加入晋宁会馆",
            "想了解晋宁会馆？\n\n"
            "📌 私聊秃贝发送「加入会馆」\n"
            "📌 即可获取详细信息~\n\n"
            "或者发送 /关于 了解更多",
        ))


@manual_cmd.handle()
async def handle_manual(bot: Bot, event: MessageEvent):
    local_path = Path("data/使用手册.txt")
    # 容器内路径（docker cp 放进去的位置）+ file:// 前缀
    container_path = "file:///app/napcat/使用手册.txt"

    if not local_path.exists():
        await manual_cmd.finish(ui.error("使用手册文件不存在，请联系管理员。"))
        return

    import logging
    logger = logging.getLogger("tubei.guide")

    try:
        if isinstance(event, GroupMessageEvent):
            await bot.call_api(
                "upload_group_file",
                group_id=event.group_id,
                file=container_path,
                name="晋宁会馆·秃贝使用手册.txt"
            )
        else:
            await bot.call_api(
                "upload_private_file",
                user_id=event.user_id,
                file=container_path,
                name="晋宁会馆·秃贝使用手册.txt"
            )
    except Exception as e:
        logger.error(f"[Manual] 文件发送失败: {e}")
        await manual_cmd.finish(ui.info(
            "📖 文件发送失败。\n\n"
            "请联系析沐大人获取使用手册~"
        ))