"""
晋宁会馆·秃贝五边形 4.1
无限大人的厨房 · 生存挑战

4.1 改动：
1. 每个饭点窗口限吃 1 次（不再是一天随便吃4次）
2. 跨天夜宵窗口 22:00-01:00 合并为同一窗口
3. 保留原有所有机制（成就/世界事件/buff等）
"""

import random
import time

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

from src.common.data_manager import data_manager
from src.common.response_manager import resp_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.common.utils import ensure_daily_reset, get_current_hour, timestamp_now, check_blessing
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.recorder import recorder
from src.plugins.tubei_system.mutex import check_mutex, MutexError
from src.plugins.tubei_cultivation.achievement import achievement_engine


kitchen_cmd = on_command("厨房生存", aliases={"厨房", "吃饭", "干饭"}, priority=5, block=True)


# ==================== 饭点工具函数 ====================

# 饭点窗口定义（与 yaml 对应，但把跨天的合并标注）
# 格式：(start, end, slot_id)
# slot_id 相同 = 同一顿饭
MEAL_SLOTS = [
    (6,  9,  "breakfast"),   # 早餐
    (11, 14, "lunch"),       # 午餐
    (16, 21, "dinner"),      # 晚餐
    (22, 24, "midnight"),    # 夜宵前半段
    (0,  1,  "midnight"),    # 夜宵后半段（跨天，同一个 slot_id）
]


def check_meal_time() -> bool:
    """检查当前是否在饭点时段"""
    h = get_current_hour()
    for start, end, _ in MEAL_SLOTS:
        if start <= end:
            if start <= h < end:
                return True
        else:
            if h >= start or h < end:
                return True
    return False


def get_current_meal_slot() -> str:
    """
    获取当前饭点窗口ID。
    不在饭点返回空字符串。
    跨天夜宵 22:00-01:00 统一返回 "midnight"。
    """
    h = get_current_hour()
    for start, end, slot_id in MEAL_SLOTS:
        if start <= end:
            if start <= h < end:
                return slot_id
        else:
            if h >= start or h < end:
                return slot_id
    return ""


def get_meal_display_name(slot_id: str) -> str:
    """饭点窗口的中文名"""
    names = {
        "breakfast": "早餐 (6-9点)",
        "lunch": "午餐 (11-14点)",
        "dinner": "晚餐 (16-21点)",
        "midnight": "夜宵 (22-1点)",
    }
    return names.get(slot_id, "未知餐次")


def get_next_meal_hint() -> str:
    """获取下一个饭点的提示文案"""
    h = get_current_hour()
    # 按时间顺序检查下一个饭点
    schedule = [
        (6, "早餐 6:00"),
        (11, "午餐 11:00"),
        (16, "晚餐 16:00"),
        (22, "夜宵 22:00"),
    ]
    for start_h, name in schedule:
        if h < start_h:
            return f"下一餐：{name}"
    return "下一餐：明天早餐 6:00"


# ==================== 夜宵跨天处理 ====================

def get_midnight_eaten_key(data: dict) -> bool:
    """
    检查夜宵窗口是否已吃过。
    
    夜宵跨天特殊处理：
    - 22:00-23:59 吃了 → 记录 midnight_eaten_date = 今天日期
    - 00:00-00:59 检查 → 看 midnight_eaten_date 是否 = 昨天日期
    
    用一个独立字段 midnight_eaten_date 记录，不受 daily_counts 日期重置影响。
    """
    return data.get("midnight_eaten_date", "")


def mark_midnight_eaten(data: dict) -> dict:
    """标记夜宵已吃，使用当前日期"""
    from src.common.utils import get_today_str
    data["midnight_eaten_date"] = get_today_str()
    return data


def is_midnight_already_eaten(data: dict) -> bool:
    """
    判断当前夜宵窗口是否已经吃过。
    
    逻辑：
    - 如果现在是 22:00-23:59（前半段）：
      检查 midnight_eaten_date == 今天 → 已吃
    - 如果现在是 00:00-00:59（后半段）：
      检查 midnight_eaten_date == 昨天 → 已吃（说明昨晚22-24点吃了）
      检查 midnight_eaten_date == 今天 → 已吃（说明今天0点后吃了）
    """
    from src.common.utils import get_today_str
    from datetime import datetime, timedelta
    
    eaten_date = data.get("midnight_eaten_date", "")
    if not eaten_date:
        return False
    
    today = get_today_str()
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    h = get_current_hour()
    
    if 22 <= h < 24:
        # 前半段：只看今天
        return eaten_date == today
    elif 0 <= h < 1:
        # 后半段：看昨天或今天
        return eaten_date in (today, yesterday)
    
    return False


# ==================== 主逻辑 ====================

@kitchen_cmd.handle()
async def handle_kitchen(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "无限大人的厨房 · 生存挑战", min_tier="public")
    if not perm.allowed:
        await kitchen_cmd.finish(perm.deny_message)

    try:
        await check_mutex(uid, "kitchen")
    except MutexError as e:
        await kitchen_cmd.finish(e.message)

    # 饭点检查
    if not check_meal_time():
        msg = await resp_manager.get_text("entertainment.kitchen_not_time")
        next_hint = get_next_meal_hint()
        await kitchen_cmd.finish(ui.render_panel(
            "无限大人的厨房",
            f"{msg}\n\n💡 {next_hint}"
        ))

    data = await data_manager.get_spirit_data(uid)

    # 每日次数（总次数仍然限 4）
    daily = ensure_daily_reset(data, extra_fields={
        "kitchen": 0, "bad_streak": 0, "good_streak": 0,
        "kitchen_slots": {}
    })

    if daily.get("kitchen", 0) >= game_config.kitchen_daily_limit:
        await kitchen_cmd.finish(ui.info(
            f"今天已经吃了 {game_config.kitchen_daily_limit} 顿，明天再来~"
        ))

    # ===== 饭点窗口限次检查 =====
    meal_slot = get_current_meal_slot()
    
    if meal_slot == "midnight":
        # 夜宵特殊处理（跨天）
        if is_midnight_already_eaten(data):
            await kitchen_cmd.finish(ui.info(
                f"🌙 这顿夜宵已经吃过啦~\n{get_next_meal_hint()}"
            ))
    else:
        # 普通饭点：看 daily_counts 里的 kitchen_slots
        slots = daily.get("kitchen_slots", {})
        if slots.get(meal_slot):
            slot_name = get_meal_display_name(meal_slot)
            await kitchen_cmd.finish(ui.info(
                f"🍽 {slot_name} 已经吃过啦~\n{get_next_meal_hint()}"
            ))

    # ===== 以下是原有逻辑，完全保留 =====

    buffs = data.get("buffs", {})
    is_taste_lost = timestamp_now() < buffs.get("taste_loss_expire", 0)

    # 世界事件：无限失控
    from src.plugins.tubei_system.world_event import is_event_active
    kitchen_chaos_active = await is_event_active("kitchen_chaos")

    # 计算成功概率
    base_prob = game_config.kitchen_success_rate
    bad_streak = daily.get("bad_streak", 0)

    if kitchen_chaos_active:
        base_prob = 1.0
    elif bad_streak >= 3:
        base_prob = game_config.kitchen_bad_streak_bonus_3
    elif bad_streak >= 2:
        base_prob += game_config.kitchen_bad_streak_bonus_2

    if buffs.pop("清心露", None):
        base_prob = min(1.0, base_prob + 0.20)

    blessing_active = check_blessing(buffs, "kitchen")
    if blessing_active:
        base_prob = 1.0

    is_success = random.random() < base_prob

    sp_change = 0
    result_title = ""
    result_desc = ""
    result_tags = []
    used_fulingdan = False

    if is_taste_lost:
        taste_sp = game_config.kitchen_taste_loss_sp
        sp_change = taste_sp
        result_title = "😶 味蕾丧失中"
        result_desc = await resp_manager.get_text(
            "entertainment.kitchen_taste_lost", {"sp": taste_sp}
        )
        result_tags.append("味蕾丧失")

    elif is_success:
        reward = game_config.kitchen_reward_sp
        sp_change = reward
        menu = random.choice(game_config.kitchen_menu_good)
        result_title = "✨ 绝世珍馐"
        result_desc = await resp_manager.get_text(
            "entertainment.kitchen_good", {"menu": menu, "sp": reward}
        )
        daily["bad_streak"] = 0
        daily["good_streak"] = daily.get("good_streak", 0) + 1

        if kitchen_chaos_active:
            result_tags.append("🔥 无限失控中")
        if blessing_active:
            result_tags.append("🪶 吉兆加持")

        if daily["good_streak"] >= 3:
            await achievement_engine.try_unlock(uid, "美食品鉴家", bot, event)

    else:
        penalty = game_config.kitchen_penalty_sp
        menu = random.choice(game_config.kitchen_menu_bad)

        if buffs.pop("涪灵丹", None):
            sp_change = 0
            used_fulingdan = True
            result_title = "💊 涪灵丹护体"
            result_desc = (
                f"呃啊... 是【{menu}】！\n"
                f"但涪灵丹抵消了所有负面效果！\n"
                f"💰 灵力变化：±0"
            )
        else:
            sp_change = -penalty
            result_title = "💀 深渊料理"
            result_desc = await resp_manager.get_text(
                "entertainment.kitchen_bad", {"menu": menu, "sp": penalty}
            )
            buffs["taste_loss_expire"] = timestamp_now() + game_config.kitchen_taste_loss_duration
            result_tags.append("💀 味蕾丧失 2h")

            await data_manager.increment_stat(uid, "total_kitchen_bad")
            await data_manager.increment_stat(uid, "total_taste_loss")

        daily["good_streak"] = 0
        daily["bad_streak"] = daily.get("bad_streak", 0) + 1

    # ===== 更新数据 =====
    daily["kitchen"] = daily.get("kitchen", 0) + 1

    # 标记该饭点窗口已吃
    if meal_slot == "midnight":
        mark_midnight_eaten(data)
    else:
        slots = daily.get("kitchen_slots", {})
        slots[meal_slot] = True
        daily["kitchen_slots"] = slots

    current_sp = data.get("sp", 0)
    new_sp = max(0, current_sp + sp_change)

    await data_manager.update_spirit_data(uid, {
        "sp": new_sp,
        "daily_counts": daily,
        "buffs": buffs,
    })

    await data_manager.increment_stat(uid, "total_kitchen_count")

    await recorder.add_event("kitchen", int(uid), {
        "sp_change": sp_change,
        "success": is_success,
        "taste_loss": not is_success and not is_taste_lost and not used_fulingdan,
    })

    await achievement_engine.check_stat_achievements(uid, bot, event)

    # ===== 构建卡片 =====
    sp_display = f"+{sp_change}" if sp_change >= 0 else str(sp_change)
    slot_name = get_meal_display_name(meal_slot)

    stats = [
        ("💰 灵力变化", f"{sp_display} (当前: {new_sp})"),
        ("🍽 本餐", slot_name),
        ("📊 今日已吃", f"{daily['kitchen']} / {game_config.kitchen_daily_limit} 顿"),
    ]

    extra_text = None
    if not is_taste_lost and not is_success and not used_fulingdan:
        if daily.get("bad_streak", 0) > 0:
            extra_text = f"🛡 连败保底: {daily['bad_streak']}/3"

    card = ui.render_result_card(
        f"无限大人的厨房 · {result_title}",
        result_desc,
        stats=stats,
        tags=result_tags if result_tags else None,
        extra=extra_text,
        footer=f"👉 {get_next_meal_hint()}"
    )
    await kitchen_cmd.finish(MessageSegment.at(uid) + "\n" + card)