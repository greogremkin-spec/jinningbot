"""
晋宁会馆·秃贝五边形 4.1
世界事件系统

三个事件：
  1. 灵潮爆发 - 聚灵收益+30%，持续2小时
  2. 嘿咻暴动 - 每30分钟刷一只嘿咻，持续2小时
  3. 无限失控 - 厨房全部变为绝世珍馐，持续1小时

每天随机触发，概率可配置
事件状态存储在 bot_status.json 中
"""

import random
import asyncio
import time
import logging

from nonebot import on_command, require, get_bot

from src.common.data_manager import data_manager
from src.common.group_manager import group_manager
from src.common.ui_renderer import ui
from src.plugins.tubei_system.config import system_config, game_config
from src.common.utils import get_current_hour


try:
    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler
except ImportError:
    scheduler = None

logger = logging.getLogger("tubei.world_event")

def _is_curfew() -> bool:
    """检查是否处于馆禁时间"""
    start = game_config.sleep_start
    end = game_config.sleep_end
    now = get_current_hour()
    if start <= end:
        return start <= now < end
    else:
        return now >= start or now < end

# ==================== 事件状态管理 ====================

async def get_active_events() -> dict:
    """获取当前所有活跃的世界事件"""
    status = await data_manager.get_bot_status()
    return status.get("world_events", {})


async def is_event_active(event_id: str) -> bool:
    """检查某个事件是否正在生效"""
    events = await get_active_events()
    event = events.get(event_id, {})
    if not event.get("active", False):
        return False
    end_time = event.get("end_time", 0)
    if time.time() >= end_time:
        # 已过期，清除
        await _deactivate_event(event_id)
        return False
    return True


async def get_event_bonus(event_id: str) -> float:
    """获取事件加成值（如灵潮的0.30）"""
    if not await is_event_active(event_id):
        return 0.0
    config = game_config.get("world_events", event_id, default={})
    return config.get("bonus", 0.0)


async def _activate_event(event_id: str, duration: int):
    """激活一个世界事件"""
    now = time.time()
    status = await data_manager.get_bot_status()
    events = status.get("world_events", {})
    events[event_id] = {
        "active": True,
        "start_time": now,
        "end_time": now + duration,
    }
    await data_manager.update_bot_status({"world_events": events})


async def _deactivate_event(event_id: str):
    """停用一个世界事件"""
    status = await data_manager.get_bot_status()
    events = status.get("world_events", {})
    if event_id in events:
        events[event_id] = {"active": False}
        await data_manager.update_bot_status({"world_events": events})


# ==================== 事件通报 ====================

async def _broadcast_to_core(message: str):
    """向所有核心群（非调试群）发送通报"""
    if _is_curfew(): # 馆禁时间禁止通报
        return
    
    try:
        bot = get_bot()
        for gid in group_manager.core_group_ids:
            if group_manager.is_debug_group(gid):
                continue
            try:
                await bot.send_group_msg(group_id=gid, message=message)
                await asyncio.sleep(0.3)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"[WorldEvent] 通报失败: {e}")


# ==================== 灵潮爆发 ====================

async def trigger_spirit_tide():
    """触发灵潮爆发事件"""
    config = game_config.get("world_events", "spirit_tide", default={})
    duration = config.get("duration", 7200)
    bonus_pct = int(config.get("bonus", 0.30) * 100)

    await _activate_event("spirit_tide", duration)

    hours = duration // 3600
    msg = ui.render_panel(
        "⚡ 【灵潮预警】",
        f"天地灵气异常涌动！\n\n"
        f"📈 效果：聚灵收益 +{bonus_pct}%\n"
        f"⏳ 持续：{hours} 小时\n\n"
        f"抓紧修行！",
    )
    await _broadcast_to_core(msg)
    logger.info(f"[WorldEvent] 灵潮爆发已触发，持续 {hours} 小时")


async def end_spirit_tide():
    """灵潮结束通报"""
    if await is_event_active("spirit_tide"):
        return  # 还没结束
    await _broadcast_to_core("🌊 灵潮已退去，天地归于平静。")


# ==================== 嘿咻暴动 ====================

async def trigger_heixiu_frenzy():
    """触发嘿咻暴动事件"""
    config = game_config.get("world_events", "heixiu_frenzy", default={})
    duration = config.get("duration", 7200)
    interval = config.get("spawn_interval", 1800)

    await _activate_event("heixiu_frenzy", duration)

    hours = duration // 3600
    msg = ui.render_panel(
        "🐾 【嘿咻暴动】",
        f"大量嘿咻涌入会馆！\n\n"
        f"📈 效果：每 {interval // 60} 分钟刷一只嘿咻\n"
        f"⏳ 持续：{hours} 小时\n\n"
        f"全员准备捕捉！",
    )
    await _broadcast_to_core(msg)
    logger.info(f"[WorldEvent] 嘿咻暴动已触发，持续 {hours} 小时")

    # 启动连续刷新任务
    asyncio.create_task(_heixiu_frenzy_loop(duration, interval))


async def _heixiu_frenzy_loop(duration: int, interval: int):
    """嘿咻暴动期间的连续刷新循环"""
    from src.plugins.tubei_entertainment.heixiu_catcher import spawn_heixiu

    end_time = time.time() + duration
    while time.time() < end_time:
        await asyncio.sleep(interval)
        if time.time() >= end_time:
            break
        try:
            await spawn_heixiu()
        except Exception as e:
            logger.error(f"[WorldEvent] 暴动刷新嘿咻失败: {e}")

    await _broadcast_to_core("🐾 嘿咻暴动结束了，妖灵们恢复了平静。")


# ==================== 无限失控 ====================

async def trigger_kitchen_chaos():
    """触发无限失控事件"""
    config = game_config.get("world_events", "kitchen_chaos", default={})
    duration = config.get("duration", 3600)

    await _activate_event("kitchen_chaos", duration)

    hours = duration // 3600
    mins = (duration % 3600) // 60
    time_str = f"{hours}小时" if hours > 0 else f"{mins}分钟"

    msg = ui.render_panel(
        "🍳 【无限失控】",
        f"无限大人的灵力突然暴走了！\n\n"
        f"📈 效果：厨房全部变为绝世珍馐\n"
        f"⏳ 持续：{time_str}\n\n"
        f"快去厨房蹭饭！",
    )
    await _broadcast_to_core(msg)
    logger.info(f"[WorldEvent] 无限失控已触发，持续 {time_str}")

    # 定时结束
    asyncio.create_task(_kitchen_chaos_end(duration))


async def _kitchen_chaos_end(duration: int):
    """等待无限失控结束"""
    await asyncio.sleep(duration)
    await _deactivate_event("kitchen_chaos")
    await _broadcast_to_core("🍳 无限大人冷静下来了... 厨房恢复了原本的「味道」。")


# ==================== 每日随机触发 ====================

async def daily_event_roll():
    """
    每日事件抽签
    每天上午 10:00 执行一次
    根据配置的概率决定当天是否触发某个事件
    """
    from src.common.utils import get_current_hour

    now_hour = get_current_hour()
    events_config = game_config.get("world_events", default={})

    for event_id, config in events_config.items():
        if not isinstance(config, dict):
            continue

        daily_chance = config.get("daily_chance", 0)
        min_hour = config.get("min_hour", 10)
        max_hour = config.get("max_hour", 22)

        # 已经在活跃状态的跳过
        if await is_event_active(event_id):
            continue

        # 概率判定
        if random.random() >= daily_chance:
            continue

        # 随机选择触发时间
        trigger_hour = random.randint(min_hour, max_hour - 1)
        delay_seconds = max(0, (trigger_hour - now_hour) * 3600 + random.randint(0, 3599))

        if delay_seconds <= 0:
            # 已过时间窗口，今天不触发
            continue

        logger.info(
            f"[WorldEvent] 今日将触发 [{config.get('name', event_id)}]，"
            f"预计 {trigger_hour}:xx"
        )

        # 延迟触发
        asyncio.create_task(_delayed_trigger(event_id, delay_seconds))


async def _delayed_trigger(event_id: str, delay: int):
    """延迟触发事件"""
    await asyncio.sleep(delay)

    # 再次检查是否已经有活跃事件（避免冲突）
    if await is_event_active(event_id):
        return

    trigger_map = {
        "spirit_tide": trigger_spirit_tide,
        "heixiu_frenzy": trigger_heixiu_frenzy,
        "kitchen_chaos": trigger_kitchen_chaos,
    }

    trigger_func = trigger_map.get(event_id)
    if trigger_func:
        await trigger_func()


# ==================== 事件状态查询指令 ====================

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

event_status_cmd = on_command("世界事件", aliases={"事件", "灵潮"}, priority=5, block=True)


@event_status_cmd.handle()
async def handle_event_status(bot: Bot, event: MessageEvent):
    events = await get_active_events()
    events_config = game_config.get("world_events", default={})

    rows = []
    has_active = False

    for event_id, config in events_config.items():
        if not isinstance(config, dict):
            continue
        name = config.get("name", event_id)
        effect = config.get("effect", "未知效果")

        event_state = events.get(event_id, {})
        if event_state.get("active", False):
            end_time = event_state.get("end_time", 0)
            remaining = int(end_time - time.time())
            if remaining > 0:
                has_active = True
                from src.common.utils import format_duration
                time_str = format_duration(remaining)
                rows.append((f"🔴 {name}", f"生效中 (剩余 {time_str})"))
                rows.append(("  📈 效果", effect))
                rows.append(("", ""))
            else:
                rows.append((f"⚪ {name}", "今日未触发"))
        else:
            rows.append((f"⚪ {name}", "今日未触发"))

    if not rows:
        rows.append(("💤 当前无事件", "天下太平"))

    card = ui.render_data_card(
        "🌍 世界事件 · 实时监控",
        rows,
        footer="👉输入  事件每日随机触发，敬请期待~"
    )
    await event_status_cmd.finish(card)


# ==================== 定时任务注册 ====================

if scheduler:
    # 每天 10:00 进行当日事件抽签
    scheduler.add_job(
        daily_event_roll, "cron",
        hour=10, minute=0,
        id="daily_event_roll",
        replace_existing=True,
    )

    # 每 5 分钟检查过期事件
    async def check_expired_events():
        events = await get_active_events()
        now = time.time()
        for event_id, state in events.items():
            if state.get("active") and now >= state.get("end_time", 0):
                await _deactivate_event(event_id)
                logger.info(f"[WorldEvent] 事件 {event_id} 已自然结束")

    scheduler.add_job(
        check_expired_events, "interval",
        minutes=5,
        id="check_expired_events",
        replace_existing=True,
    )