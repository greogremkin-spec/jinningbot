"""
晋宁会馆·秃贝五边形 4.1
名单管理

管理组专属指令：查看名单、修改数值、发放物品、除名
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.adapters import Message

from src.common.data_manager import data_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.plugins.tubei_system.config import system_config
from src.plugins.tubei_system.recorder import recorder


list_cmd = on_command("查看名单", aliases={"名单", "在馆名单"}, priority=5, block=True)
modify_cmd = on_command("修改", aliases={"改数值"}, priority=5, block=True)
give_cmd = on_command("发放", aliases={"发东西"}, priority=5, block=True)
del_cmd = on_command("删除名单", aliases={"除名"}, priority=5, block=True)


# ==================== 查看名单 ====================

@list_cmd.handle()
async def handle_list(bot: Bot, event: GroupMessageEvent):
    perm = await check_permission(event, "灵册大厅 · 在馆名单", admin_only=True)
    if not perm.allowed:
        await list_cmd.finish(perm.deny_message)

    await list_cmd.send(ui.info("正在调取名单..."))

    members = await data_manager.get_all_members()
    if not members:
        await list_cmd.finish(ui.info("名单为空。"))

    # 按身份分组
    core_lines = []
    outer_lines = []
    idx = 0

    sorted_members = sorted(
        members.values(),
        key=lambda x: x.get("register_time", 0)
    )

    for m in sorted_members:
        if m.get("status") == "deleted":
            continue
        idx += 1
        uid = m["qq"]
        spirit = await data_manager.get_spirit_data(uid)
        identity = m.get("identity", "core_member")

        line = f"{idx}. {m['spirit_name']} ({uid}) | Lv.{spirit.get('level', 1)} | {spirit.get('sp', 0)}灵力"

        if identity in ("core_member", "admin", "decision"):
            core_lines.append(line)
        else:
            outer_lines.append(line)

    msg_parts = []
    if core_lines:
        msg_parts.append("🏠 馆内成员：\n" + "\n".join(core_lines))
    if outer_lines:
        msg_parts.append("🌐 馆外成员：\n" + "\n".join(outer_lines))

    full_msg = "\n\n".join(msg_parts) if msg_parts else "名单为空。"

    # 分段发送（防超长）
    if len(full_msg) > 1500:
        parts = [full_msg[i:i+1500] for i in range(0, len(full_msg), 1500)]
        for part in parts:
            await list_cmd.send(part)
        await list_cmd.finish()
    else:
        await list_cmd.finish(ui.render_panel("在馆人员名单", full_msg))


# ==================== 修改数值 ====================

@modify_cmd.handle()
async def handle_modify(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    perm = await check_permission(event, "管理指令 · 数值修改", admin_only=True)
    if not perm.allowed:
        return

    params = args.extract_plain_text().strip().split()
    if len(params) != 3:
        await modify_cmd.finish(ui.error("用法：/修改 [QQ] [灵力/等级] [数值]"))

    uid, key, val = params

    key_map = {"灵力": "sp", "等级": "level", "sp": "sp", "level": "level"}
    if key not in key_map:
        await modify_cmd.finish(ui.error("仅支持修改：灵力、等级。"))

    real_key = key_map[key]
    try:
        val = int(val)
    except ValueError:
        await modify_cmd.finish(ui.error("数值必须是整数。"))

    await data_manager.update_spirit_data(uid, {real_key: val})
    await recorder.add_event("admin_action", int(event.user_id), {
        "action": "modify", "target": uid, "key": real_key, "value": val
    })

    await modify_cmd.finish(ui.success(f"{uid} 的 {key} 已变更为 {val}。"))


# ==================== 发放物品 ====================

@give_cmd.handle()
async def handle_give(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    perm = await check_permission(event, "管理指令 · 物品发放", admin_only=True)
    if not perm.allowed:
        return

    params = args.extract_plain_text().strip().split()
    if len(params) != 3:
        await give_cmd.finish(ui.error("用法：/发放 [QQ] [物品名] [数量]"))

    uid, item, count = params
    try:
        count = int(count)
    except ValueError:
        await give_cmd.finish(ui.error("数量必须是整数。"))

    data = await data_manager.get_spirit_data(uid)
    items = data.get("items", {})
    items[item] = items.get(item, 0) + count
    await data_manager.update_spirit_data(uid, {"items": items})

    await recorder.add_event("admin_action", int(event.user_id), {
        "action": "give", "target": uid, "item": item, "count": count
    })

    await give_cmd.finish(ui.success(f"{uid} 获得了 {item} x{count}。"))


# ==================== 除名 ====================

@del_cmd.handle()
async def handle_delete(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    perm = await check_permission(event, "管理指令 · 除名", admin_only=True)
    if not perm.allowed:
        return

    target = args.extract_plain_text().strip()
    if not target.isdigit():
        await del_cmd.finish(ui.error("请输入QQ号。"))

    member = await data_manager.get_member_info(target)
    if not member:
        await del_cmd.finish(ui.info("查无此人。"))

    await data_manager.delete_member(target)
    await recorder.add_event("admin_action", int(event.user_id), {
        "action": "delete", "target": target
    })

    name = member.get("spirit_name", target)
    await del_cmd.finish(ui.success(f"【{name}】({target}) 已除名。"))