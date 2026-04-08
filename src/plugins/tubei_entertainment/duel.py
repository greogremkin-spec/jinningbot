"""
晋宁会馆·秃贝五边形 4.1
灵质空间 · 斗帅宫

3.1 改动：
1. 数值从 game_config 读取
2. 卡片式反馈（包含双方信息）
3. 胜负文案分离
4. 接入权限检查
5. 接入 increment_stat("total_duel_wins") 支持成就检查
6. 胜利后自动检查统计类成就
"""

import random

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters import Message

from src.common.data_manager import data_manager
from src.common.response_manager import resp_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.mutex import check_mutex, MutexError
from src.plugins.tubei_system.recorder import recorder
from src.plugins.tubei_cultivation.achievement import achievement_engine

duel_cmd = on_command("灵力切磋", aliases={"切磋", "PK", "领域较量"}, priority=5, block=True)


@duel_cmd.handle()
async def handle_duel(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    uid = str(event.user_id)

    perm = await check_permission(event, "灵质空间 · 斗帅宫",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await duel_cmd.finish(perm.deny_message)

    try:
        await check_mutex(uid, "entertainment")
    except MutexError as e:
        await duel_cmd.finish(e.message)

    # 提取 @对象
    target_id = ""
    for seg in event.message:
        if seg.type == "at":
            target_id = str(seg.data["qq"])
            break

    if not target_id:
        await duel_cmd.finish(ui.render_panel(
            "灵质空间 · 斗帅宫",
            "与其他妖灵进行友好的灵力比拼。\n\n"
            "⚔ 规则：比拼灵力总值 (含±20%波动)\n"
            "🏆 胜者：吸取对方 1% 灵力 (上限 20)\n"
            "🛡 保护：对方灵力<50 时不吸取\n"
            "💔 败者：无损失 (仅颜面扫地)",
            footer="👉输入  切磋 @某人"
        ))
        return

    if target_id == uid:
        await duel_cmd.finish(ui.error("不能和自己切磋~"))

    me_data = await data_manager.get_spirit_data(uid)
    target_data = await data_manager.get_spirit_data(target_id)
    my_sp = me_data.get("sp", 0)
    target_sp = target_data.get("sp", 0)

    # 灵力波动
    fluct = game_config.duel_fluctuation
    p_me = int(my_sp * random.uniform(1 - fluct, 1 + fluct))
    p_target = int(target_sp * random.uniform(1 - fluct, 1 + fluct))

    # 获取对手名称
    members = await data_manager.get_all_members()
    my_name = members.get(uid, {}).get("spirit_name", "你")
    target_name = members.get(target_id, {}).get("spirit_name", f"对手({target_id})")

    if p_me > p_target:
        # 胜利
        steal_rate = game_config.duel_steal_rate
        steal_cap = game_config.duel_steal_cap
        protection = game_config.duel_protection_threshold

        steal = min(steal_cap, int(target_sp * steal_rate))
        if target_sp < protection:
            steal = 0

        await data_manager.update_spirit_data(uid, {"sp": my_sp + steal})
        if steal > 0:
            await data_manager.update_spirit_data(target_id, {"sp": target_sp - steal})

        # 统计：切磋胜利次数
        await data_manager.increment_stat(uid, "total_duel_wins")

        await recorder.add_event("duel_win", int(uid), {
            "opponent": target_id, "steal": steal
        })

        # 成就检查：演武达人等
        await achievement_engine.check_stat_achievements(uid, bot, event)

        card = ui.render_result_card(
            "灵质空间 · 切磋结果",
            "🏆 胜利！",
            stats=[
                ("⚡ 你的灵压", str(p_me)),
                ("⚡ 对手灵压", str(p_target)),
                ("", ""),
                ("🎯 结果", f"{my_name} 压制了 {target_name}"),
                ("💰 吸取灵力", f"+{steal}" if steal > 0 else "对方灵力过低，未吸取"),
            ],
            footer="👉输入  切磋 @某人 再战"
        )
    else:
        # 失败
        card = ui.render_result_card(
            "灵质空间 · 切磋结果",
            "💔 惜败...",
            stats=[
                ("⚡ 你的灵压", str(p_me)),
                ("⚡ 对手灵压", str(p_target)),
                ("", ""),
                ("🎯 结果", f"{target_name} 更胜一筹"),
                ("💰 损失", "无 (仅颜面扫地)"),
            ],
            footer="👉输入  聚灵 提升实力 | 切磋 再战"
        )

    await duel_cmd.finish(MessageSegment.at(uid) + "\n" + card)