"""
晋宁会馆·秃贝五边形 4.1
灵册大厅 —— 在馆人员登记

改进：
  1. 区分馆内/馆外身份
  2. 记录登记群号（register_group）
  3. 接入 identity_manager 分配初始身份
  4. 新增官网预留字段（join_date, oc_details 等）
  5. 卡片式反馈
"""

from nonebot import on_command, on_regex
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment, GroupMessageEvent

from src.common.data_manager import data_manager
from src.common.utils import parse_registry_form, check_sensitive_words, get_today_str
from src.common.response_manager import resp_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.common.identity import identity_manager
from src.plugins.tubei_system.config import system_config, game_config
from src.plugins.tubei_system.recorder import recorder


guide_cmd = on_command("登记", aliases={"在馆登记", "入册"}, priority=5, block=True)
submit_cmd = on_regex(r"^/在馆人员登记", priority=4, block=True)


# ==================== 引导登记 ====================

@guide_cmd.handle()
async def handle_guide(bot: Bot, event: MessageEvent):
    perm = await check_permission(event, "灵册大厅 · 在馆人员登记",
                                   min_tier="allied", deny_promotion=True)
    if not perm.allowed:
        await guide_cmd.finish(perm.deny_message)

    tip_msg = await resp_manager.get_text("admin.register_guide")
    await guide_cmd.send(tip_msg)

    template = await resp_manager.get_text("admin.register_template")
    await guide_cmd.finish(template)


# ==================== 提交登记 ====================

@submit_cmd.handle()
async def handle_submit(bot: Bot, event: MessageEvent):
    perm = await check_permission(event, "灵册大厅 · 档案提交", min_tier="allied")
    if not perm.allowed:
        await submit_cmd.finish(perm.deny_message)

    raw_text = event.get_plaintext().strip()
    data = parse_registry_form(raw_text)

    if not data:
        await submit_cmd.finish(ui.error(
            '解析失败！请确保保留了"QQ号:"、"妖名:"和"简介:"等关键词。'
        ))
        return

    target_qq = data["qq"]
    spirit_name = data["spirit_name"]
    intro = data["intro"]

    # 敏感词检查
    if check_sensitive_words(intro):
        await submit_cmd.finish(ui.error("内容包含敏感词。"))
        return

    # 权限检查：代他人登记需要管理权限
    sender_qq = str(event.user_id)
    is_superuser = sender_qq in system_config.superusers
    is_admin = sender_qq in system_config.tubei_admins

    if target_qq != sender_qq and not (is_superuser or is_admin):
        msg = await resp_manager.get_text("system.permission_denied")
        await submit_cmd.finish(msg)
        return

    # 确定登记群号和身份
    register_group = 0
    if isinstance(event, GroupMessageEvent):
        register_group = event.group_id

    identity = await identity_manager.on_new_registration(target_qq, register_group)

    # 构建成员数据
    member_data = {
        "qq": target_qq,
        "spirit_name": spirit_name,
        "nickname": data["nickname"] or spirit_name,
        "intro": intro,
        "register_time": int(event.time),
        "status": "active",
        "identity": identity,
        "register_group": register_group,
        "last_active": int(event.time),
        "public_visible": True,
        "oc_details": {},
        "web_synced": False,
        "web_profile_url": "",
    }

    await data_manager.update_member_info(target_qq, member_data)

    # 灵力数据初始化
    spirit_data = await data_manager.get_spirit_data(target_qq)
    is_new = not spirit_data

    if is_new:
        initial_sp = game_config.initial_sp
        await data_manager.update_spirit_data(target_qq, {
            "sp": initial_sp,
            "level": 1,
            "items": {},
            "achievements": ["初探灵界"],
            "join_date": get_today_str(),
            "total_meditation_count": 0,
            "total_sp_earned": 0,
            "total_kitchen_count": 0,
            "total_expedition_count": 0,
            "heixiu_count": 0,
            "title_history": [
                {"level": 1, "title": "灵识觉醒", "date": get_today_str()}
            ],
        })
        bonus_msg = await resp_manager.get_text("admin.bonus_msg", {"sp": initial_sp})
        await recorder.add_event("registry_new", int(target_qq), {"name": spirit_name})
    else:
        bonus_msg = await resp_manager.get_text("admin.update_msg")
        await recorder.add_event("registry_update", int(target_qq), {"name": spirit_name})

    # 身份提示
    identity_tips = {
        "decision": "👑 身份：决策组",
        "admin": "🛡 身份：管理组",
        "core_member": "🏠 身份：馆内成员",
        "outer_member": "🌐 身份：馆外成员",
    }
    identity_tip = identity_tips.get(identity, "")

    # 馆外成员额外提示
    outer_tip = ""
    if identity == "outer_member":
        outer_tip = "\n" + await resp_manager.get_text("admin.register_outer")

    reply = await resp_manager.get_text("admin.register_success", {
        "spirit_name": spirit_name,
        "bonus_msg": bonus_msg,
    })

    card = ui.render_result_card(
        "灵册大厅 · 登记完成",
        reply,
        stats=[
            ("📛 妖名", spirit_name),
            ("🏷 身份", identity_tip),
        ] if identity_tip else None,
        extra=outer_tip if outer_tip else None,
        footer="👉输入 档案 查看面板 | 菜单 查看功能"
    )
    await submit_cmd.finish(MessageSegment.at(event.user_id) + "\n" + card)