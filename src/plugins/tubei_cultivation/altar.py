"""
晋宁会馆·秃贝五边形 4.1
木头的催更祭坛

馆内专属功能
"""

import time

from nonebot import on_command, get_bot
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from src.common.data_manager import data_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.common.group_manager import group_manager
from src.plugins.tubei_system.config import game_config


altar_cmd = on_command("祭坛", aliases={"催更祭坛"}, priority=5, block=True)


@altar_cmd.handle()
async def handle_altar(bot: Bot, event: MessageEvent):
    # 馆内专属
    perm = await check_permission(event, "木头的催更祭坛",
                                   core_only=True, deny_promotion=True)
    if not perm.allowed:
        await altar_cmd.finish(perm.deny_message)

    status = await data_manager.get_bot_status()
    energy = status.get("altar_energy", 0)
    threshold = game_config.altar_threshold
    buff_active = status.get("ritual_buff_active", False)

    # 检查是否可以触发仪式
    if energy >= threshold and not buff_active:
        await data_manager.update_bot_status({
            "altar_energy": 0,
            "ritual_buff_active": True,
            "ritual_start_time": time.time(),
        })

        # 通知所有核心群
        for gid in group_manager.core_group_ids:
            if group_manager.is_debug_group(gid):
                continue
            try:
                await bot.send_group_msg(
                    group_id=gid,
                    message="🔥【全馆公告】催更祭坛仪式开启！\n全员聚灵收益加成生效中！"
                )
            except Exception:
                pass

        await altar_cmd.finish(ui.render_result_card(
            "木头的催更祭坛",
            "🔥 怨念汇聚，仪式已开启！",
            stats=[
                ("⛩ 能量", f"0 / {threshold} (已重置)"),
                ("✨ 全服Buff", "生效中！"),
            ],
            footer="全员聚灵收益加成 24 小时"
        ))

    # 检查 buff 是否过期
    if buff_active:
        start = status.get("ritual_start_time", 0)
        elapsed = time.time() - start
        buff_duration = game_config.altar_buff_duration
        if elapsed >= buff_duration:
            await data_manager.update_bot_status({
                "ritual_buff_active": False,
                "ritual_start_time": 0,
            })
            buff_active = False

    # 显示当前状态
    bar = ui.render_progress_bar(energy, threshold)
    buff_str = "✨ 生效中" if buff_active else "💤 未激活"

    card = ui.render_data_card(
        "木头的催更祭坛 · 实时监控",
        [
            ("⛩ 当前怨念", f"{energy} / {threshold}"),
            ("📊 进度", bar),
            ("✨ 全服Buff", buff_str),
            ("", ""),
            ("💡 机制", "每次聚灵自动上缴 1% 灵力"),
        ],
        footer="👉输入  集满怨念，催木头更新！"
    )
    await altar_cmd.finish(card)