"""
晋宁会馆·秃贝五边形 4.1
管理员控制台

3.2 改动：
1. time.sleep → asyncio.sleep
2. 新增 /重载配置、/强制保存
3. 使用 game_config 读取配置
4. 卡片式反馈
5. 新增宣传管理指令（/宣传开关、/宣传内容、/宣传概率）
"""

import asyncio
import time

from nonebot import on_command, get_bot
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from nonebot.adapters import Message

from src.common.data_manager import data_manager
from src.common.response_manager import resp_manager
from src.common.group_manager import group_manager
from src.common.ui_renderer import ui
from .config import system_config, game_config
from .interceptor import BAN_LIST
from .recorder import recorder


# ==================== 指令注册 ====================

persona_cmd = on_command(
    "切换人格", aliases={"变身", "切换模式"},
    permission=SUPERUSER, priority=1, block=True
)
status_cmd = on_command(
    "系统状态", aliases={"查看状态"},
    permission=SUPERUSER, priority=1, block=True
)
broadcast_cmd = on_command(
    "全员广播", aliases={"广播", "公告"},
    permission=SUPERUSER, priority=1, block=True
)
ban_cmd = on_command(
    "封印", aliases={"关小黑屋"},
    permission=SUPERUSER, priority=1, block=True
)
gift_cmd = on_command(
    "全员福利", aliases={"发红包"},
    permission=SUPERUSER, priority=1, block=True
)
reload_cmd = on_command(
    "重载配置", aliases={"刷新配置", "reload"},
    permission=SUPERUSER, priority=1, block=True
)
force_save_cmd = on_command(
    "强制保存", aliases={"保存数据", "save"},
    permission=SUPERUSER, priority=1, block=True
)
promo_toggle_cmd = on_command(
    "宣传开关",
    permission=SUPERUSER, priority=1, block=True
)
promo_content_cmd = on_command(
    "宣传内容",
    permission=SUPERUSER, priority=1, block=True
)
promo_chance_cmd = on_command(
    "宣传概率",
    permission=SUPERUSER, priority=1, block=True
)


# ==================== 人格系统 ====================

VALID_PERSONAS = {
    "normal": "✨ 普通模式 (治愈管家)",
    "middle_school": "🔥 中二模式 (漆黑烈焰)",
    "cold": "❄ 高冷模式 (绝对零度)",
    "secretary": "📋 秘书模式 (高效冷漠)",
    "overload": "⚡ 过载模式 (电波话痨)",
}

@persona_cmd.handle()
async def handle_persona(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    mode = args.extract_plain_text().strip()

    if not mode:
        status = await data_manager.get_bot_status()
        curr = status.get("persona", "normal")

        rows = [("🎭 当前人格", VALID_PERSONAS.get(curr, curr)), ("", "")]
        for k, v in VALID_PERSONAS.items():
            marker = " ← 当前" if k == curr else ""
            rows.append((f"  {k}", f"{v}{marker}"))

        msg = ui.render_data_card("人格切换面板", rows, footer="👉 /切换人格 模式代码")
        await persona_cmd.finish(msg)

    if mode not in VALID_PERSONAS:
        await persona_cmd.finish(ui.error("无效的模式代码。请使用 /切换人格 查看可选项。"))

    await data_manager.update_bot_status({"persona": mode})
    await recorder.add_event("persona_change", int(event.user_id), {"new_persona": mode})
    await persona_cmd.finish(f"🔄 系统重构完成！\n🎭 当前人格已切换为：【{VALID_PERSONAS[mode]}】")


# ==================== 系统状态 ====================
@status_cmd.handle()
async def handle_status(bot: Bot, event: MessageEvent):
    status = await data_manager.get_bot_status()
    persona = status.get("persona", "normal")
    energy = status.get("altar_energy", 0)

    members = await data_manager.get_all_members()
    active_count = len([m for m in members.values() if m.get("status") != "deleted"])
    core_count = len([m for m in members.values()
                      if m.get("identity") in ("core_member", "admin", "decision")
                      and m.get("status") != "deleted"])
    outer_count = active_count - core_count

    spirits = await data_manager.get_all_spirits()
    total_sp = sum(s.get("sp", 0) for s in spirits.values())

    # 宣传状态
    promo = status.get("promotion", {})
    promo_enabled = "✅ 开启" if promo.get("enabled", False) else "❌ 关闭"
    promo_chance = promo.get("chance", 0.20)

    msg = ui.render_data_card(
        "🖥 系统控制台",
        [
            ("🎭 人格", VALID_PERSONAS.get(persona, persona)),
            ("", ""),
            ("👥 总人数", f"{active_count} 位"),
            ("🏠 馆内", f"{core_count} 位"),
            ("🌐 馆外", f"{outer_count} 位"),
            ("✨ 全馆灵力", f"{total_sp}"),
            ("⛩ 祭坛能量", f"{energy} / 1000"),
            ("", ""),
            ("🏘 核心群", f"{len(group_manager.core_group_ids)} 个"),
            ("🚫 当前封禁", f"{len(BAN_LIST)} 人"),
            ("", ""),
            ("📢 宣传功能", promo_enabled),
            ("📢 宣传概率", f"{int(promo_chance * 100)}%"),
        ],
        footer="👉 /切换人格 | /全员广播 | /强制保存 | /宣传开关"
    )
    await status_cmd.finish(msg)


# ==================== 全员广播 ====================
@broadcast_cmd.handle()
async def handle_broadcast(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    msg_text = args.extract_plain_text().strip()
    if not msg_text:
        await broadcast_cmd.finish(ui.error("请输入广播内容。\n📌 用法：/全员广播 [内容]"))

    count = 0
    for gid in group_manager.core_group_ids:
        if group_manager.is_debug_group(gid):
            continue
        try:
            await bot.send_group_msg(
                group_id=gid,
                message=f"📢 【会馆公告】\n{msg_text}"
            )
            count += 1
            await asyncio.sleep(0.5)
        except Exception:
            pass

    await broadcast_cmd.finish(ui.success(f"广播已发送至 {count} 个群。"))


# ==================== 封印 ====================
@ban_cmd.handle()
async def handle_ban(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    params = args.extract_plain_text().strip().split()
    if len(params) != 2:
        await ban_cmd.finish(ui.error("用法：/封印 [QQ 号] [分钟数]"))

    target_qq, mins_str = params
    if not target_qq.isdigit():
        await ban_cmd.finish(ui.error("QQ 号格式错误。"))

    try:
        mins = int(mins_str)
    except ValueError:
        await ban_cmd.finish(ui.error("分钟数必须是整数。"))

    BAN_LIST[int(target_qq)] = time.time() + mins * 60
    await recorder.add_event("admin_action", int(event.user_id), {
        "action": "ban", "target": target_qq, "duration": mins
    })
    await ban_cmd.finish(ui.success(f"已封印 {target_qq} 的灵力回路 {mins} 分钟。"))


# ==================== 全员福利 ====================
@gift_cmd.handle()
async def handle_gift(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    params = args.extract_plain_text().strip().split()
    if len(params) < 2:
        await gift_cmd.finish(ui.error(
            "格式错误！\n📌 用法 1: /全员福利 sp 100\n📌 用法 2: /全员福利 item [物品名] [数量]"
        ))

    gift_type = params[0].lower()
    members = await data_manager.get_all_members()
    active_uids = [qq for qq, m in members.items() if m.get("status") != "deleted"]
    count = 0

    if gift_type == "sp":
        try:
            amount = int(params[1])
        except ValueError:
            await gift_cmd.finish(ui.error("数值必须是整数。"))

        for uid in active_uids:
            data = await data_manager.get_spirit_data(uid)
            await data_manager.update_spirit_data(uid, {"sp": data.get("sp", 0) + amount})
            count += 1

        await recorder.add_event("admin_action", int(event.user_id), {
            "action": "gift_sp", "amount": amount, "count": count
        })
        await gift_cmd.finish(ui.success(f"全员 {amount} 灵力发放完毕！(共{count}人)"))

    elif gift_type == "item":
        if len(params) != 3:
            await gift_cmd.finish(ui.error("请指定物品名和数量。"))

        item_name = params[1]
        try:
            amount = int(params[2])
        except ValueError:
            await gift_cmd.finish(ui.error("数量必须是整数。"))

        for uid in active_uids:
            data = await data_manager.get_spirit_data(uid)
            items = data.get("items", {})
            items[item_name] = items.get(item_name, 0) + amount
            await data_manager.update_spirit_data(uid, {"items": items})
            count += 1

        await recorder.add_event("admin_action", int(event.user_id), {
            "action": "gift_item", "item": item_name, "amount": amount, "count": count
        })
        await gift_cmd.finish(ui.success(f"全员 {item_name} x{amount} 发放完毕！(共{count}人)"))
    else:
        await gift_cmd.finish(ui.error("未知类型，仅支持 sp 或 item。"))


# ==================== 配置热重载 ====================
@reload_cmd.handle()
async def handle_reload(bot: Bot, event: MessageEvent):
    resp_manager.reload()
    game_config.reload()
    group_manager.reload()
    await reload_cmd.finish(ui.success(
        "配置重载完成！\n✅ responses.yaml\n✅ game_balance.yaml\n✅ groups.yaml"
    ))


# ==================== 强制保存 ====================
@force_save_cmd.handle()
async def handle_force_save(bot: Bot, event: MessageEvent):
    await data_manager.persist_all()
    await force_save_cmd.finish(ui.success("所有数据已强制保存到磁盘。"))


# ==================== 宣传开关 ====================
@promo_toggle_cmd.handle()
async def handle_promo_toggle(bot: Bot, event: MessageEvent):
    status = await data_manager.get_bot_status()
    promo = status.get("promotion", {})

    current = promo.get("enabled", False)
    new_state = not current

    promo["enabled"] = new_state

    # 确保有默认值
    if "chance" not in promo:
        promo["chance"] = 0.20
    if "content" not in promo:
        promo["content"] = ""
    if "version" not in promo:
        promo["version"] = "3.2"

    await data_manager.update_bot_status({"promotion": promo})

    state_text = "✅ 已开启" if new_state else "❌ 已关闭"
    card = ui.render_data_card(
        "📢 宣传功能",
        [
            ("📢 状态", state_text),
            ("📊 触发概率", f"{int(promo.get('chance', 0.20) * 100)}% (随机插嘴时)"),
            ("📝 当前内容", promo.get("content", "(空)")[:50] + "..." if len(promo.get("content", "")) > 50 else promo.get("content", "(空)")),
        ],
        footer="👉 /宣传内容 [文本] | /宣传概率 [0~100]"
    )
    await promo_toggle_cmd.finish(card)


# ==================== 宣传内容 ====================
@promo_content_cmd.handle()
async def handle_promo_content(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    new_content = args.extract_plain_text().strip()

    if not new_content:
        # 显示当前内容
        status = await data_manager.get_bot_status()
        promo = status.get("promotion", {})
        current_content = promo.get("content", "(空)")

        await promo_content_cmd.finish(ui.render_panel(
            "📢 当前宣传内容",
            current_content if current_content else "(空)",
            footer="👉 /宣传内容 [新文本] 来修改"
        ))
        return

    status = await data_manager.get_bot_status()
    promo = status.get("promotion", {})
    promo["content"] = new_content

    if "enabled" not in promo:
        promo["enabled"] = False
    if "chance" not in promo:
        promo["chance"] = 0.20

    await data_manager.update_bot_status({"promotion": promo})

    await promo_content_cmd.finish(ui.success(
        f"宣传内容已更新！\n\n📝 新内容：\n{new_content}"
    ))


# ==================== 宣传概率 ====================
@promo_chance_cmd.handle()
async def handle_promo_chance(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    val_str = args.extract_plain_text().strip()

    if not val_str:
        status = await data_manager.get_bot_status()
        promo = status.get("promotion", {})
        current_chance = promo.get("chance", 0.20)
        await promo_chance_cmd.finish(ui.info(
            f"当前宣传概率：{int(current_chance * 100)}%\n"
            f"📌 用法：/宣传概率 [0~100]\n"
            f"📌 表示随机插嘴时有多少概率改为发宣传"
        ))
        return

    try:
        val = int(val_str)
    except ValueError:
        await promo_chance_cmd.finish(ui.error("请输入 0~100 的整数。"))
        return

    if val < 0 or val > 100:
        await promo_chance_cmd.finish(ui.error("范围 0~100。"))
        return

    status = await data_manager.get_bot_status()
    promo = status.get("promotion", {})
    promo["chance"] = val / 100.0

    if "enabled" not in promo:
        promo["enabled"] = False
    if "content" not in promo:
        promo["content"] = ""

    await data_manager.update_bot_status({"promotion": promo})

    await promo_chance_cmd.finish(ui.success(f"宣传概率已设为 {val}%"))