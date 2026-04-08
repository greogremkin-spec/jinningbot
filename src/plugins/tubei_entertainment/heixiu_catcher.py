"""
晋宁会馆·秃贝五边形 4.1
嘿咻捕获计划

4.1 改动：
1. 取消超时逃跑机制，改为无限期等待
2. 取消100%捕捉率，改为概率捕捉（80%成功）
3. 捕捉失败 = 嘿咻逃跑，本轮结束
4. 类型在捕捉成功后才揭晓（惊喜机制）
5. 出现文案统一，不暴露类型
6. 接入成就系统
7. 提供 spawn_heixiu_in_group() 供引灵香调用
8. 馆禁时间不刷新
"""
import random
import asyncio
import time
import logging
from nonebot import on_command, on_message, require, get_bot
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, MessageSegment
from src.common.data_manager import data_manager
from src.common.response_manager import resp_manager
from src.common.ui_renderer import ui
from src.common.group_manager import group_manager
from src.common.utils import get_current_hour
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.recorder import recorder
from src.plugins.tubei_cultivation.achievement import achievement_engine

logger = logging.getLogger("tubei.heixiu")
try:
    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler
except ImportError:
    scheduler = None

# ==================== 全局状态 ====================
HEIXIU_STATE = {
    "active": False,
    "group_id": 0,
    "start_time": 0,
    "heixiu_type": "normal",
}
HEIXIU_LOCK = asyncio.Lock()

# 出现文案池（统一，不暴露类型）
SPAWN_MESSAGES = [
    "✨ 草丛里好像有什么在动...\n　发送「捕捉」试试看！",
    "✨ 角落里传来窸窸窣窣的声音...\n　发送「捕捉」抓住它！",
    "✨ 有什么毛茸茸的东西一闪而过！\n　快发送「捕捉」！",
    "✨ 嘿咻的气息... 就在附近！\n　发送「捕捉」寻找它！",
    "✨ 空气中弥漫着嘿咻的味道...\n　发送「捕捉」碰碰运气！",
]

# 类型配置（仅用于捕捉成功后的展示）
HEIXIU_TYPES = {
    "normal": {
        "name": "野生嘿咻",
        "catch_icon": "🐾",
        "reveal_text": "抓到了一只野生嘿咻！",
    },
    "rainbow": {
        "name": "彩虹嘿咻",
        "catch_icon": "🌈",
        "reveal_text": "等等... 这只嘿咻在发光！？\n🌈 居然是传说中的【彩虹嘿咻】！",
    },
    "golden": {
        "name": "黄金嘿咻",
        "catch_icon": "⭐",
        "reveal_text": "天哪... 金光闪闪的！！\n⭐ 这是...【黄金嘿咻】！！千载难逢！",
    },
    "shadow": {
        "name": "暗影嘿咻",
        "catch_icon": "🌑",
        "reveal_text": "咦... 它好像咬了你一口...\n🌑 是一只【暗影嘿咻】... 好疼。",
    },
}

# 捕捉失败文案池
ESCAPE_MESSAGES = [
    "🐾 嘿咻灵活地躲开了你的手，溜走了！",
    "🐾 差一点就抓到了... 嘿咻消失在草丛中。",
    "🐾 嘿咻吐了吐舌头，一溜烟跑了！",
    "🐾 你扑了个空！嘿咻已经不见踪影。",
    "🐾 嘿咻：「嘿咻！」(翻译：再见！) 然后跑了。",
    "🐾 手滑了！嘿咻趁机逃之夭夭...",
    "🐾 嘿咻假装被抓住，然后... 溜了。",
]


# ==================== 指令注册 ====================
help_cmd = on_command("嘿咻捕捉", aliases={"嘿咻捕获计划"}, priority=5, block=True)
capture_handler = on_message(priority=20, block=False)


@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)
    data = await data_manager.get_spirit_data(uid)
    count = data.get("heixiu_count", 0)
    card = ui.render_panel(
        "🐾 嘿咻捕获计划",
        f"会馆角落偶尔会出现野生的嘿咻！\n\n"
        f"• 触发：系统随机在群内通报\n"
        f"• 捕获：发送「捕捉」（先到先得）\n"
        f"• 概率：80% 成功 / 20% 逃跑\n"
        f"• 惊喜：捕捉成功后可能发现稀有品种！\n"
        f"• 种类：普通/🌈彩虹/⭐黄金/🌑暗影\n"
        f"• 成就：收集 10 只解锁 [嘿咻牧场主]\n\n"
        f"🐾 你已捕获：{count} 只",
        footer="💡 嘿咻出现时发送「捕捉」即可"
    )
    await help_cmd.finish(card)


# ==================== 捕捉逻辑 ====================
@capture_handler.handle()
async def handle_capture(bot: Bot, event: GroupMessageEvent):
    if not HEIXIU_STATE["active"]:
        return

    if event.get_plaintext().strip() != "捕捉":
        return

    # danger 群不允许捕捉
    from src.common.group_manager import TIER_DANGER
    if group_manager.get_group_tier(event.group_id) == TIER_DANGER:
        return

    if event.group_id != HEIXIU_STATE["group_id"]:
        return

    async with HEIXIU_LOCK:
        if not HEIXIU_STATE["active"]:
            return
        # 先到先得：立即关闭活跃状态
        HEIXIU_STATE["active"] = False
        heixiu_type = HEIXIU_STATE["heixiu_type"]

    uid = str(event.user_id)
    type_info = HEIXIU_TYPES.get(heixiu_type, HEIXIU_TYPES["normal"])

    # ===== 概率判定：80% 成功 / 20% 逃跑 =====
    catch_rate = game_config.get("heixiu", "catch_success_rate", default=0.80)
    is_success = random.random() < catch_rate

    if not is_success:
        # 捕捉失败，嘿咻逃跑
        escape_msg = random.choice(ESCAPE_MESSAGES)
        await recorder.add_event("heixiu_capture", int(uid), {
            "type": heixiu_type,
            "success": False,
        })
        await capture_handler.finish(
            MessageSegment.at(uid) + "\n" + escape_msg
        )

    # ===== 捕捉成功 =====
    data = await data_manager.get_spirit_data(uid)
    count = data.get("heixiu_count", 0) + 1
    updates = {"heixiu_count": count}

    # 类型奖励
    rewards_config = game_config.get("heixiu", "rewards", heixiu_type, default={})
    sp_reward = rewards_config.get("sp", 0)
    item_rewards = rewards_config.get("items", {})
    should_announce = rewards_config.get("announcement", False)

    # 灵力变化
    current_sp = data.get("sp", 0)
    new_sp = max(0, current_sp + sp_reward)
    updates["sp"] = new_sp

    # 物品奖励
    items = data.get("items", {})
    for item_name, item_count in item_rewards.items():
        items[item_name] = items.get(item_name, 0) + item_count
    updates["items"] = items

    await data_manager.update_spirit_data(uid, updates)
    await recorder.add_event("heixiu_capture", int(uid), {
        "type": heixiu_type,
        "success": True,
    })

    # ===== 构建反馈卡片 =====
    reveal = type_info["reveal_text"]
    stats = [("🐾 类型", f"{type_info['catch_icon']} {type_info['name']}")]
    stats.append(("📦 总数", f"{count} 只"))
    extra_lines = []

    if sp_reward > 0:
        stats.append(("✨ 灵力", f"+{sp_reward}"))
    elif sp_reward < 0:
        stats.append(("💔 灵力", f"{sp_reward} (被咬了！)"))
        extra_lines.append("嘿咻咬了你一口，但似乎掉了什么...")

    if item_rewards:
        items_str = "、".join(f"{k} x{v}" for k, v in item_rewards.items())
        stats.append(("🎁 掉落", items_str))

    # ===== 成就检查 =====
    ach_msg = ""
    if count >= 10:
        result = await achievement_engine.try_unlock(uid, "嘿咻牧场主", bot, event)
        if result:
            ach_msg += "\n🏆 解锁成就：【嘿咻牧场主】！"
    if heixiu_type == "rainbow":
        result = await achievement_engine.try_unlock(uid, "彩虹猎手", bot, event)
        if result:
            ach_msg += "\n🏆 解锁成就：【彩虹猎手】！"
    if heixiu_type == "golden":
        result = await achievement_engine.try_unlock(uid, "黄金传说", bot, event)
        if result:
            ach_msg += "\n🏆 解锁成就：【黄金传说】！"
    if heixiu_type == "shadow":
        result = await achievement_engine.try_unlock(uid, "暗影幸存者", bot, event)
        if result:
            ach_msg += "\n🏆 解锁成就：【暗影幸存者】！"

    extra_text = "\n".join(extra_lines) + ach_msg if (extra_lines or ach_msg) else None

    card = ui.render_result_card(
        f"🐾 嘿咻捕获成功！",
        reveal,
        stats=stats,
        extra=extra_text.strip() if extra_text else None,
    )
    await capture_handler.finish(MessageSegment.at(uid) + "\n" + card)

    # 全服公告
    if should_announce:
        members = await data_manager.get_all_members()
        name = members.get(uid, {}).get("spirit_name", f"妖灵{uid}")
        announce = f"{type_info['catch_icon']}【全服通报】{name} 捕获了一只 {type_info['name']}！"
        for gid in group_manager.core_group_ids:
            if gid == event.group_id or group_manager.is_debug_group(gid):
                continue
            try:
                await bot.send_group_msg(group_id=gid, message=announce)
            except Exception:
                pass


# ==================== 刷新嘿咻 ====================
def _is_curfew() -> bool:
    """检查是否处于馆禁时间"""
    h = get_current_hour()
    start = game_config.sleep_start
    end = game_config.sleep_end
    if start <= end:
        return start <= h < end
    else:
        return h >= start or h < end


def _roll_heixiu_type() -> str:
    """根据概率抽取嘿咻类型"""
    weights_config = game_config.get("heixiu", "type_weights", default={})
    types = list(weights_config.keys())
    weights = [weights_config[t] for t in types]
    if not types:
        return "normal"
    return random.choices(types, weights=weights, k=1)[0]


async def spawn_heixiu():
    """在随机核心群中刷出一只嘿咻"""
    # 馆禁时间不刷新
    if _is_curfew():
        return

    candidates = []
    for gid in group_manager.main_group_ids:
        if not group_manager.is_debug_group(gid):
            candidates.append(gid)

    if not candidates:
        return

    target = random.choice(candidates)
    await spawn_heixiu_in_group(target)


async def spawn_heixiu_in_group(group_id: int):
    """在指定群刷出一只嘿咻（供引灵香调用）"""
    # 馆禁时间不刷新
    if _is_curfew():
        return

    heixiu_type = _roll_heixiu_type()

    async with HEIXIU_LOCK:
        # 如果已有活跃嘿咻，不重复刷
        if HEIXIU_STATE["active"]:
            return

        HEIXIU_STATE.update({
            "active": True,
            "group_id": group_id,
            "start_time": time.time(),
            "heixiu_type": heixiu_type,
        })

    try:
        bot = get_bot()
        spawn_msg = random.choice(SPAWN_MESSAGES)
        await bot.send_group_msg(group_id=group_id, message=spawn_msg)
    except Exception as e:
        logger.error(f"[Heixiu] 刷新通报失败: {e}")
        # 刷新失败，重置状态
        async with HEIXIU_LOCK:
            HEIXIU_STATE["active"] = False
        return

    # 注意：不再有超时逃跑逻辑！
    # 嘿咻会一直等待，直到有人发"捕捉"


if scheduler:
    scheduler.add_job(
        spawn_heixiu,
        "interval",
        hours=game_config.heixiu_spawn_interval,
        jitter=game_config.heixiu_spawn_jitter,
        id="heixiu_spawn",
        replace_existing=True,
    )