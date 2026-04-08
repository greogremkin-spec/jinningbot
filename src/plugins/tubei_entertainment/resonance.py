"""
晋宁会馆·秃贝五边形 4.1
灵力宿命（今日灵伴）+ 灵质鉴定 + 今日老婆（致敬萝卜）

3.2 改动：
1. 灵伴从当前群全体成员中匹配（不局限已登记成员）
2. 双向锁定配对算法
3. 灵力共鸣加成（双方登记=完整，单方登记=半额，无登记=无加成）
4. 谁使用谁加成，每日一次
5. 公开群不可用灵伴，allied/core群可用
6. 今日老婆：所有群可用，致敬萝卜
7. 退出此群彩蛋
8. 纯文字触发支持
9. 吉兆Buff鉴定必出稀有
"""

import random
import hashlib
import time
import logging
import math
from datetime import datetime

from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import (
    Bot, MessageEvent, MessageSegment, GroupMessageEvent
)

from src.common.data_manager import data_manager
from src.common.response_manager import resp_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.mutex import check_mutex, MutexError
from src.plugins.tubei_system.recorder import recorder
from src.common.utils import get_today_str, check_blessing

logger = logging.getLogger("tubei.resonance")



# ==================== 双向配对算法 ====================

def _build_pairs(member_ids: list, date_str: str, salt: str = "") -> dict:
    """
    基于日期种子的双向配对算法

    1. 排序成员列表（确保每次输入一致）
    2. 用日期+salt作为种子 shuffle
    3. 两两配对：[0]<->[1], [2]<->[3], ...
    4. 奇数人时最后一个和第一个配

    salt参数用于区分不同功能（灵伴 vs 今日老婆）
    """
    if len(member_ids) < 2:
        return {}

    sorted_ids = sorted(member_ids)

    seed = int(hashlib.sha256(f"{salt}_{date_str}".encode()).hexdigest(), 16)
    rng = random.Random(seed)
    rng.shuffle(sorted_ids)

    pairs = {}
    i = 0
    while i + 1 < len(sorted_ids):
        a = sorted_ids[i]
        b = sorted_ids[i + 1]
        pairs[a] = b
        pairs[b] = a
        i += 2

    # 奇数人：最后一个和第一个配
    if len(sorted_ids) % 2 == 1:
        last = sorted_ids[-1]
        first = sorted_ids[0]
        pairs[last] = first

    return pairs


# ==================== 获取群成员并配对 ====================

async def _get_group_members(bot: Bot, event: GroupMessageEvent):
    """
    获取当前群成员列表，返回 (all_member_ids, member_info_map) 或 None
    """
    group_id = event.group_id
    bot_id = str(event.self_id)

    try:
        group_members = await bot.get_group_member_list(group_id=group_id)
    except Exception as e:
        logger.error(f"[Resonance] 获取群成员列表失败: {e}")
        return None

    all_member_ids = []
    member_info_map = {}

    for m in group_members:
        mid = str(m["user_id"])
        if mid == bot_id:
            continue
        all_member_ids.append(mid)
        member_info_map[mid] = {
            "nickname": m.get("nickname", ""),
            "card": m.get("card", ""),
        }

    return (all_member_ids, member_info_map)


def _get_display_name(member_info_map: dict, uid: str) -> str:
    """获取用户展示名（优先群名片 > 昵称 > QQ号）"""
    info = member_info_map.get(uid, {})
    return info.get("card") or info.get("nickname") or f"妖灵{uid}"


def _avatar_url(qq: str) -> str:
    """获取QQ头像URL"""
    return f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640"


# ==================== 共鸣值计算 ====================

def _calc_resonance(sp_a: int, sp_b: int) -> int:
    """
    计算灵力共鸣值

    公式：base_rand + sqrt(min(sp_a, sp_b))
    - base_rand: 5~15 的随机基础值
    - sqrt(min): 取双方较低灵力的开平方，代表"共同基础"

    典型值：
      双方灵力 100/200 → min=100, sqrt=10 → 总共 15~25
      双方灵力 500/1000 → min=500, sqrt≈22 → 总共 27~37
      双方灵力 50/50 → min=50, sqrt≈7 → 总共 12~22
    """
    base = min(sp_a, sp_b)
    rand_part = random.randint(5, 15)
    sqrt_part = int(math.sqrt(base))
    return rand_part + sqrt_part


# ==================== 指令注册 ====================

# /灵伴 指令（带斜杠，NoneBot自动处理@秃贝的情况）
soulmate_slash_cmd = on_command(
    "灵伴",
    aliases={"今日灵伴", "宿命共鸣"},
    priority=5,
    block=True
)

# 纯文字触发："今日灵伴" / "灵伴"
#soulmate_text_trigger = on_message(priority=6, block=False)

# /今日老婆 指令
waifu_slash_cmd = on_command(
    "今日老婆",
    aliases={"群友老婆"},
    priority=5,
    block=True
)

# 纯文字触发："今日老婆"
#waifu_text_trigger = on_message(priority=6, block=False)

# "退出此群" 彩蛋
#quit_easter_egg = on_message(priority=6, block=False)

# 鉴定指令
appraise_cmd = on_command(
    "灵质鉴定",
    aliases={"鉴定", "灵力检测"},
    priority=5,
    block=True
)


# ==================== 今日灵伴 · 核心逻辑 ====================

async def _handle_soulmate(bot: Bot, event: MessageEvent):
    """灵伴核心逻辑"""
    if not isinstance(event, GroupMessageEvent):
        await bot.send(event, "灵伴匹配需要在群内使用~\n去群里发送 今日灵伴 试试吧")
        return
    uid = str(event.user_id)

    # 权限检查：公开群不可用
    perm = await check_permission(
        event, "灵力宿命 · 今日灵伴",
        min_tier="allied",
        deny_promotion=True
    )
    if not perm.allowed:
        await bot.send(event, perm.deny_message)
        return

    # 获取群成员
    result = await _get_group_members(bot, event)
    if result is None:
        await bot.send(event, ui.error("获取群成员列表失败，请稍后再试~"))
        return

    all_member_ids, member_info_map = result

    if len(all_member_ids) < 2:
        await bot.send(event, ui.info("群内人数不足，无法匹配灵伴~"))
        return

    # 构建今日配对
    today = datetime.now().strftime("%Y%m%d")
    pairs = _build_pairs(all_member_ids, today, salt="soulmate")
    partner_id = pairs.get(uid)

    if not partner_id:
        await bot.send(event, ui.info("今日灵伴匹配异常，请稍后再试~"))
        return

    partner_name = _get_display_name(member_info_map, partner_id)

    # ===== 检查双方登记状态，计算共鸣加成 =====
    a_member = await data_manager.get_member_info(uid)
    b_member = await data_manager.get_member_info(partner_id)

    a_registered = (a_member is not None and a_member.get("status") != "deleted")
    b_registered = (b_member is not None and b_member.get("status") != "deleted")

    resonance_msg = ""
    gain = 0
    today_str = get_today_str()

    if a_registered:
        # A已登记，检查今天是否已领过
        a_spirit = await data_manager.get_spirit_data(uid)
        already_claimed = (a_spirit.get("last_soulmate_bonus_date") == today_str)

        if already_claimed:
            # 今天已经领过了
            resonance_msg = "\n📌 今日已感应过灵伴的共鸣，加成已生效。"
        else:
            # 计算共鸣
            sp_a = a_spirit.get("sp", 0)

            if b_registered:
                # 双方都登记 → 完整共鸣
                b_spirit = await data_manager.get_spirit_data(partner_id)
                sp_b = b_spirit.get("sp", 0)
                gain = _calc_resonance(sp_a, sp_b)

                new_sp = sp_a + gain
                await data_manager.update_spirit_data(uid, {
                    "sp": new_sp,
                    "last_soulmate_bonus_date": today_str,
                })

                await recorder.add_event("soulmate_resonance", int(uid), {
                    "partner": partner_id,
                    "gain": gain,
                    "type": "full",
                })

                resonance_msg = (
                    f"\n\n☯ 灵力共鸣激活！\n"
                    f"  共鸣强度：{gain}\n"
                    f"  灵力 +{gain}"
                )

            else:
                # 仅A登记 → 微弱共鸣（半额）
                full_gain = _calc_resonance(sp_a, 0)
                gain = full_gain // 2
                if gain < 1:
                    gain = 1

                new_sp = sp_a + gain
                await data_manager.update_spirit_data(uid, {
                    "sp": new_sp,
                    "last_soulmate_bonus_date": today_str,
                })

                await recorder.add_event("soulmate_resonance", int(uid), {
                    "partner": partner_id,
                    "gain": gain,
                    "type": "half",
                })

                resonance_msg = (
                    f"\n\n☯ 微弱共鸣...\n"
                    f"  共鸣强度：{gain}\n"
                    f"  灵力 +{gain}\n"
                    f"  （对方尚未建立灵力档案）"
                )
    else:
        # A未登记 → 无加成
        resonance_msg = (
            "\n\n📌 建立灵力档案后可激活灵力共鸣~\n"
            "  👉 /登记"
        )

    # ===== 构建消息 =====
    msg = (
        MessageSegment.at(event.user_id)
        + " 🔮 检测到灵力共鸣！你今日的灵伴是:\n"
        + MessageSegment.image(_avatar_url(partner_id))
        + f"\n【{partner_name}】({partner_id})\n"
        + "你们的灵质空间产生了宿命般的共振 ✨"
        + resonance_msg
    )

    await bot.send(event, msg)


# ==================== 今日灵伴 · /灵伴 触发 ====================

@soulmate_slash_cmd.handle()
async def handle_soulmate_slash(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await soulmate_slash_cmd.finish(ui.info(
            "灵伴匹配需要在群内使用~\n"
            "去群里发送 /灵伴 试试吧"
        ))
        return
    await _handle_soulmate(bot, event)
    await soulmate_slash_cmd.finish()


# ==================== 今日灵伴 · 纯文字触发 ====================

"""@soulmate_text_trigger.handle()
async def handle_soulmate_text(bot: Bot, event: GroupMessageEvent):
    text = event.get_plaintext().strip()

    # 严格匹配：只有完整的纯文字才触发
    if text not in ("今日灵伴", "灵伴"):
        return

    # 避免和 /灵伴 重复触发（带/的已经被on_command处理了）
    if text.startswith("/") or text.startswith("／"):
        return

    await _handle_soulmate(bot, event)"""


# ==================== 今日老婆 · 核心逻辑 ====================

async def _handle_waifu(bot: Bot, event: MessageEvent):
    """今日老婆核心逻辑（致敬萝卜，所有群可用）"""
    # 必须在群里使用
    if not isinstance(event, GroupMessageEvent):
        await bot.send(event, "今日老婆需要在群内使用哦~")
        return
    uid = str(event.user_id)

    # 获取群成员
    result = await _get_group_members(bot, event)
    if result is None:
        await bot.send(event, "获取群成员列表失败，请稍后再试~")
        return

    all_member_ids, member_info_map = result

    if len(all_member_ids) < 2:
        await bot.send(event, "群内人数不足，无法匹配~")
        return

    today = datetime.now().strftime("%Y%m%d")
    pairs = _build_pairs(all_member_ids, today, salt="waifu")
    partner_id = pairs.get(uid)

    if not partner_id:
        await bot.send(event, "匹配异常，请稍后再试~")
        return

    partner_name = _get_display_name(member_info_map, partner_id)
    now_time = datetime.now().strftime("%H:%M:%S")

    # 根据群等级决定消息格式
    from src.common.group_manager import group_manager, TIER_DANGER,TIER_PUBLIC
    group_tier = group_manager.get_group_tier(event.group_id)

    if group_tier == TIER_DANGER or group_tier == TIER_PUBLIC:
        # 危险群格式 普通格式 （无宣群）
        msg = (
            MessageSegment.at(event.user_id)
            + "\n你今天的群友老婆是:\n"
            + MessageSegment.image(_avatar_url(partner_id))
            + f"\n【{partner_name}】({partner_id})\n"
            + "\n"
            + "[疯狂致敬膜拜Sam的萝卜2号机]\n"
            + "[反馈请联系3141451467]\n"
            + "[秃贝2154181438]\n"
            + "发送[退出此群]让我退出\n"
            + "自动报刀故障维修中。\n"
            + f" From [广播系统]\n"
            + f"{now_time}"
        )
    else:
        # 联盟群（有宣群）
        msg = (
            MessageSegment.at(event.user_id)
            + "\n你今天的群友老婆是:\n"
            + MessageSegment.image(_avatar_url(partner_id))
            + f"\n【{partner_name}】({partner_id})\n"
            + "\n"
            + "[疯狂致敬膜拜Sam的萝卜2号机]\n"
            + "[反馈请联系：3141451467]\n"
            + "[晋宁会馆564234162]\n"
            + "发送[退出此群]让我退出\n"
            + "自动报刀故障维修中。\n"
            + f" From [广播系统]\n"
            + f"{now_time}"
        )

    await bot.send(event, msg)


# ==================== 今日老婆 · /今日老婆 触发 ====================

@waifu_slash_cmd.handle()
async def handle_waifu_slash(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        await waifu_slash_cmd.finish("今日老婆需要在群内使用~")
        return
    await _handle_waifu(bot, event)
    await waifu_slash_cmd.finish()


# ==================== 今日老婆 · 纯文字触发 ====================

"""@waifu_text_trigger.handle()
async def handle_waifu_text(bot: Bot, event: GroupMessageEvent):
    text = event.get_plaintext().strip()

    if text != "今日老婆":
        return

    if text.startswith("/") or text.startswith("／"):
        return

    await _handle_waifu(bot, event)"""


# ==================== "退出此群" 彩蛋 ====================

# 在 resonance.py 中添加（退出彩蛋核心函数）
async def _handle_quit_easter_egg(bot: Bot, event: MessageEvent):
    if not isinstance(event, GroupMessageEvent):
        return
    """退出此群彩蛋"""
    responses = [
        "哎呀~秃贝的这个功能只是为了致敬萝卜前辈啦！你不会真的想让俺退群吧 (嘿咻)",
        "呜哇！别别别！秃贝只是在cos萝卜前辈而已！退群什么的才不会呢 (OvO)",
        "你认真的吗？！这只是致敬萝卜的彩蛋啦~秃贝才不走呢，哼！",
        "这是致敬萝卜前辈的经典功能~但秃贝可不会真的退群哦，这里是我的家嘛 (嘿咻)",
        "检测到退群指令...正在执行...\n\n开玩笑的啦！这只是致敬萝卜前辈的彩蛋功能，并非实际指令，秃贝哪儿也不去~ (OvO)",
    ]
    await bot.send(event, random.choice(responses))


# ==================== 灵质鉴定（完整保留） ====================

@appraise_cmd.handle()
async def handle_appraise(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "灵质鉴定", min_tier="public")
    if not perm.allowed:
        await appraise_cmd.finish(perm.deny_message)

    try:
        await check_mutex(uid, "resonance")
    except MutexError as e:
        await appraise_cmd.finish(e.message)

    data = await data_manager.get_spirit_data(uid)
    cost = game_config.appraise_cost

    current_sp = data.get("sp", 0)
    if current_sp < cost:
        await appraise_cmd.finish(ui.render_data_card(
            "灵质鉴定",
            [
                ("💰 需要", f"{cost} 灵力"),
                ("💰 当前", f"{current_sp} 灵力"),
                ("", ""),
                ("📌 提示", "通过 /聚灵 获取灵力"),
            ],
            footer="👉输入  聚灵 | 档案"
        ))
        return

    # 扣费
    await data_manager.update_spirit_data(uid, {"sp": current_sp - cost})

    # 判断是否稀有
    buffs = data.get("buffs", {})
    is_rare = False

    if buffs.pop("鸾草", None):
        is_rare = True
        await data_manager.update_spirit_data(uid, {"buffs": buffs})
    elif check_blessing(buffs, "resonance"):
        is_rare = True
        await data_manager.update_spirit_data(uid, {"buffs": buffs})
    else:
        is_rare = random.random() < game_config.rare_chance

    # 随机数值
    score = random.randint(0, 100)

    # 词条
    if is_rare:
        keyword = random.choice(game_config.keywords_rare)
        buff_entry = random.choice(game_config.buff_pool_rare)
    else:
        keyword = random.choice(game_config.keywords_normal)
        buff_entry = random.choice(game_config.buff_pool)

    buff_name = buff_entry["name"]
    buff_desc = buff_entry["desc"]

    # 应用 Buff
    if buff_name != "无":
        buffs[buff_name] = True
        await data_manager.update_spirit_data(uid, {"buffs": buffs})

    prefix = "🌟" if is_rare else "✨"
    rarity_text = "稀有" if is_rare else "普通"

    await recorder.add_event("resonance", int(uid), {
        "score": score, "keyword": keyword, "rare": is_rare
    })

    # 构建卡片
    tags = []
    if is_rare:
        tags.append("✨ 稀有词条")
    if buff_name != "无":
        tags.append(f"💫 {buff_name}")

    card = ui.render_result_card(
        "灵质鉴定报告",
        f"{prefix} 鉴定完成！",
        stats=[
            ("🔍 灵力纯度", f"{score}%"),
            ("🏷 灵质属性", f"【{keyword}】({rarity_text})"),
            ("⚡ 附加效果", buff_desc),
            ("💰 消耗", f"-{cost} 灵力"),
        ],
        tags=tags if tags else None,
        footer="👉输入  鉴定 再来一次 | 背包"
    )
    await appraise_cmd.finish(MessageSegment.at(uid) + "\n" + card)