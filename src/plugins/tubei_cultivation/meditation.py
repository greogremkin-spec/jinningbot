"""
晋宁会馆·秃贝五边形 4.1
聚灵台 —— 聚灵修行 + 每日灵签 + 个人档案

3.2 改动：
1. 接入成就系统（聚灵后自动检查统计类成就）
2. 接入世界事件（灵潮爆发加成）
3. 档案显示佩戴称号
4. 深夜聚灵触发隐藏成就
5. 单次 50+灵力触发成就
6. 读取 permanent_meditation_bonus（天明珠/秘卷/星核的永久加成）
7. 时段文案选择（清晨/正午/午后/黄昏/深夜）
8. 吉兆buff：强制大吉运势
9. 档案显示永久加成数值
"""

import random
import time
from datetime import datetime

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment

from src.common.data_manager import data_manager
from src.common.response_manager import resp_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.common.utils import (
    get_today_str, is_today, ensure_daily_reset,
    timestamp_now, get_current_hour, check_blessing
)
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.recorder import recorder
from src.plugins.tubei_system.mutex import check_mutex, MutexError
from src.plugins.tubei_cultivation.achievement import achievement_engine


# ==================== 指令注册 ====================
meditate_cmd = on_command("聚灵", aliases={"聚灵修行"}, priority=5, block=True)
fortune_cmd = on_command("求签", aliases={"每日灵签"}, priority=5, block=True)
profile_cmd = on_command("我的档案", aliases={"个人信息", "状态", "档案"}, priority=5, block=True)


# ==================== 时段判断 ====================

def _get_time_period() -> str:
    """根据当前小时数返回时段标识"""
    h = get_current_hour()
    if 5 <= h < 9:
        return "dawn"
    elif 9 <= h < 14:
        return "noon"
    elif 14 <= h < 18:
        return "afternoon"
    elif 18 <= h < 22:
        return "dusk"
    else:
        return "night"


async def _get_scene_text() -> str:
    """根据时段获取聚灵场景文案，优先使用时段文案，降级为通用文案"""
    period = _get_time_period()
    period_key = f"cultivation.meditate_scene_{period}"
    pool = resp_manager.get_list(period_key)
    if pool:
        return random.choice(pool)
    return await resp_manager.get_text("cultivation.meditate_scene")



# ==================== 等级检查 ====================

async def check_levelup(uid: str, current_sp: int, current_level: int) -> str:
    """检查是否晋升等级"""
    level_map = game_config.level_map
    level_titles = game_config.level_titles
    new_level = current_level

    for lv in sorted(level_map.keys(), reverse=True):
        if lv > current_level and current_sp >= level_map[lv]:
            new_level = lv
            break

    if new_level > current_level:
        await data_manager.update_spirit_data(uid, {"level": new_level})
        title = level_titles.get(new_level, "未知")

        spirit = await data_manager.get_spirit_data(uid)
        history = spirit.get("title_history", [])
        history.append({
            "level": new_level,
            "title": title,
            "date": get_today_str(),
        })
        await data_manager.update_spirit_data(uid, {"title_history": history})

        return await resp_manager.get_text(
            "cultivation.levelup",
            {"level": new_level, "title": title}
        )

    return ""


# ==================== 聚灵修行 ====================
@meditate_cmd.handle()
async def handle_meditate(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(
        event, "聚灵台 · 灵质修行",
        min_tier="allied", require_registered=True, deny_promotion=True
    )
    if not perm.allowed:
        await meditate_cmd.finish(perm.deny_message)

    try:
        await check_mutex(uid, "meditation")
    except MutexError as e:
        await meditate_cmd.finish(e.message)

    data = await data_manager.get_spirit_data(uid)
    members = await data_manager.get_all_members()
    is_registered = uid in members
    today = get_today_str()

    # 冷却检查
    if timestamp_now() - data.get("last_meditate_time", 0) < game_config.meditation_cooldown:
        msg = await resp_manager.get_text("system.cooldown", {"nickname": "小友"})
        await meditate_cmd.finish(msg)

    # 每日次数检查
    daily = ensure_daily_reset(data, extra_fields={"meditation": 0})
    if daily.get("meditation", 0) >= game_config.meditation_daily_limit:
        await meditate_cmd.finish("🔒 今日修行已达上限，请明日再来。")

    # 先检查晋升
    levelup_msg = await check_levelup(uid, data.get("sp", 0), data.get("level", 1))
    if levelup_msg:
        await meditate_cmd.finish(levelup_msg)

    # ===== 计算收益 =====
    level = data.get("level", 1)
    level_bonus_list = game_config.meditation_level_bonus
    lvl_bonus = level_bonus_list[min(level, len(level_bonus_list) - 1)]

    base = random.randint(game_config.meditation_base_min, game_config.meditation_base_max)

    # Buff 处理
    buffs = data.get("buffs", {})
    bf_bonus = 0.0

    if buffs.pop("蓝玉果", None):
        base = game_config.meditation_base_max
    if buffs.pop("聚气 Lv1", None):
        bf_bonus += 0.05
    if buffs.pop("聚气 MAX", None):
        bf_bonus += 0.20
    if buffs.pop("天佑", None):
        base = game_config.meditation_base_max

    # 运势处理
    fortune_mults = game_config.fortune_mults
    fortune_today = data.get("fortune_today", "平")

    # 吉兆buff：强制大吉
    blessing_active = check_blessing(buffs, "meditation")
    if blessing_active:
        fortune_today = "大吉"

    mult = fortune_mults.get(fortune_today, 0)

    if buffs.pop("灵心草", None):
        mult += 0.5

    # 世界事件：灵潮加成
    from src.plugins.tubei_system.world_event import get_event_bonus
    tide_bonus = await get_event_bonus("spirit_tide")
    if tide_bonus > 0:
        mult += tide_bonus

    # 祭坛 Buff 加成
    bot_status = await data_manager.get_bot_status()
    if bot_status.get("ritual_buff_active", False):
        base += game_config.altar_buff_bonus

    # 永久加成（天明珠/破碎星核）
    permanent_bonus = data.get("permanent_meditation_bonus", 0)

    # 最终灵力
    final_sp = int((base + lvl_bonus + permanent_bonus) * (1 + mult + bf_bonus))
    if final_sp < 0:
        final_sp = 0

    # 未登记上限
    msg_tail = ""
    current_sp = data.get("sp", 0)
    if not is_registered:
        cap = game_config.unregistered_sp_cap
        if current_sp >= cap:
            final_sp = 0
            msg_tail = f"\n🚫 瓶颈已至！请发送 /登记 突破上限。"
        else:
            final_sp = min(final_sp, cap - current_sp)

    new_sp = current_sp + final_sp
    daily["meditation"] = daily.get("meditation", 0) + 1

    # 写回数据
    await data_manager.update_spirit_data(uid, {
        "sp": new_sp,
        "last_meditate_time": timestamp_now(),
        "daily_counts": daily,
        "buffs": buffs,
    })

    # 统计字段
    await data_manager.increment_stat(uid, "total_meditation_count")
    await data_manager.increment_stat(uid, "total_sp_earned", final_sp)

    # 检查晋升
    levelup_msg_2 = await check_levelup(uid, new_sp, level)
    if levelup_msg_2:
        msg_tail += "\n" + levelup_msg_2

    # 祭坛税收
    tax = max(1, int(final_sp * game_config.altar_tax_rate))
    await data_manager.update_altar_energy(tax)

    # 记录事件
    await recorder.add_event("meditation", int(uid), {"sp_gain": final_sp})

    # ===== 成就检查 =====
    if final_sp >= 50:
        await achievement_engine.try_unlock(uid, "一夜暴富", bot, event)

    if get_current_hour() == 0:
        await achievement_engine.try_unlock(uid, "深夜修行者", bot, event)

    await achievement_engine.check_stat_achievements(uid, bot, event)

    # ===== 构建卡片反馈 =====
    scene = await _get_scene_text()

    # 状态标签
    tags = []
    if blessing_active:
        tags.append("🪶 吉兆加持")
    if fortune_today != "平":
        tags.append(f"运势:{fortune_today}")
    if tide_bonus > 0:
        tags.append("⚡ 灵潮")
    if bot_status.get("ritual_buff_active"):
        tags.append("⛩祭坛 Buff")
    if permanent_bonus > 0:
        tags.append(f"📈永久+{permanent_bonus}")
    for bk in list(buffs.keys()):
        if bk.startswith(("风行", "聚气", "丰收")):
            tags.append(bk)

    # 构建stats行（过滤空行）
    stats_rows = [
        ("🎯 运势", fortune_today),
        ("⚡ 基础", str(base)),
        ("📈 等级加成", f"+{lvl_bonus}"),
    ]
    if permanent_bonus > 0:
        stats_rows.append(("🌟 永久加成", f"+{permanent_bonus}"))
    stats_rows.append(("✨ 灵力", f"+{final_sp} (当前: {new_sp})"))

    result = ui.render_result_card(
        "聚灵台 · 修行报告",
        scene,
        stats=stats_rows,
        tags=tags if tags else None,
        extra=msg_tail.strip() if msg_tail.strip() else None,
        footer="👉输入  求签 | 聚灵 | 档案"
    )
    await meditate_cmd.finish(MessageSegment.at(uid) + "\n" + result)


# ==================== 每日灵签 ====================
@fortune_cmd.handle()
async def handle_fortune(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "每日灵签", min_tier="public")
    if not perm.allowed:
        await fortune_cmd.finish(perm.deny_message)

    try:
        await check_mutex(uid, "meditation")
    except MutexError as e:
        await fortune_cmd.finish(e.message)

    data = await data_manager.get_spirit_data(uid)
    today = get_today_str()

    if data.get("last_fortune_date") == today:
        await fortune_cmd.finish("🔒 今日已求过签啦，明日再来~")

    # 抽签
    fortune_names = game_config.fortune_names
    fortune_weights = game_config.fortune_weights
    result = random.choices(fortune_names, weights=fortune_weights, k=1)[0]

    await data_manager.update_spirit_data(uid, {
        "last_fortune_date": today,
        "fortune_today": result,
    })

    # 宜忌
    yi_pool = resp_manager.get_list("fortune_yi")
    ji_pool = resp_manager.get_list("fortune_ji")
    yi = random.choice(yi_pool) if yi_pool else "聚灵"
    ji_candidates = [x for x in ji_pool if x != yi]
    ji = random.choice(ji_candidates) if ji_candidates else "无"

    if result in ["大吉", "中吉", "小吉"]:
        key = "cultivation.fortune_good"
    else:
        key = "cultivation.fortune_bad"

    msg = await resp_manager.get_text(key, {"result": result, "yi": yi, "ji": ji})
    card = ui.render_panel("聚灵台 · 每日灵签", msg, footer="👉输入  聚灵 | 档案")
    await fortune_cmd.finish(MessageSegment.at(uid) + "\n" + card)


# ==================== 个人档案 ====================
@profile_cmd.handle()
async def handle_profile(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(
        event, "妖灵档案",
        min_tier="allied", require_registered=True
    )
    if not perm.allowed:
        await profile_cmd.finish(perm.deny_message)

    members = await data_manager.get_all_members()
    spirit = await data_manager.get_spirit_data(uid)

    if uid not in members:
        await profile_cmd.finish("📋 请先发送 /登记 建立档案。")

    m = members[uid]
    level_titles = game_config.level_titles
    lv = spirit.get("level", 1)
    title = level_titles.get(lv, "灵识觉醒")

    # 佩戴称号
    equipped_title = spirit.get("equipped_title", "")
    name_display = m["spirit_name"]
    if equipped_title:
        name_display = f"[{equipped_title}] {m['spirit_name']}"

    # 身份标签
    identity = m.get("identity", "guest")
    identity_tags = {
        "decision": "👑 决策组",
        "admin": "🛡 管理组",
        "core_member": "🏠 馆内成员",
        "outer_member": "🌐 馆外成员",
        "guest": "👤 访客",
    }
    identity_tag = identity_tags.get(identity, "❓ 未知")

    # 成就数量
    achs = spirit.get("achievements", [])
    ach_count = len(achs)

    # 永久加成
    perm_med_bonus = spirit.get("permanent_meditation_bonus", 0)
    perm_exp_bonus = spirit.get("permanent_expedition_bonus", 0)

    # 状态标签
    buff_tags = []
    buffs = spirit.get("buffs", {})

    # 吉兆buff显示
    blessing = buffs.get("blessing")
    if blessing and isinstance(blessing, dict) and time.time() < blessing.get("expire", 0):
        active_systems = []
        if blessing.get("kitchen"):
            active_systems.append("厨房")
        if blessing.get("meditation"):
            active_systems.append("聚灵")
        if blessing.get("resonance"):
            active_systems.append("鉴定")
        if blessing.get("smelting"):
            active_systems.append("熔炼")
        if active_systems:
            buff_tags.append(f"🪶 吉兆({'/'.join(active_systems)})")

    if buffs.get("taste_loss_expire", 0) > time.time():
        buff_tags.append("💀 味蕾丧失")
    for k in buffs:
        if k.startswith(("风行", "聚气", "丰收")) or k == "天佑":
            buff_tags.append(f"✨ {k}")
    if buffs.get("灵心草"):
        buff_tags.append("🌿 灵心草")
    if buffs.get("蓝玉果"):
        buff_tags.append("🔵 蓝玉果")
    if buffs.get("空间简片"):
        buff_tags.append("⚡ 空间简片")
    if buffs.get("万宝如意"):
        buff_tags.append("🎁 万宝如意")
    if buffs.get("护身符"):
        buff_tags.append("🛡 护身符")
    if buffs.get("清心露"):
        buff_tags.append("💧 清心露")
    if buffs.get("混沌残片"):
        buff_tags.append("🌀 混沌残片")
    if buffs.get("鸾草"):
        buff_tags.append("🌾 鸾草")
    if buffs.get("凤羽花"):
        buff_tags.append("🌺 凤羽花")
    if buffs.get("涪灵丹"):
        buff_tags.append("💊 涪灵丹")

    today = get_today_str()
    if spirit.get("last_fortune_date") == today:
        fortune = spirit.get("fortune_today", "平")
        buff_tags.append(f"🎴 {fortune}")

    buff_str = ui.render_status_tags(buff_tags) if buff_tags else "💚 状态正常"
    bag_count = sum(v for v in spirit.get("items", {}).values() if v > 0)
    heixiu = spirit.get("heixiu_count", 0)

    # 构建档案行
    rows = [
        ("🏷 身份", identity_tag),
        ("📱 QQ", uid),
        ("🌀 境界", f"Lv.{lv} [{title}]"),
        ("✨ 灵力", str(spirit.get("sp", 0))),
    ]

    # 永久加成展示
    if perm_med_bonus > 0 or perm_exp_bonus > 0:
        bonus_parts = []
        if perm_med_bonus > 0:
            bonus_parts.append(f"聚灵+{perm_med_bonus}")
        if perm_exp_bonus > 0:
            bonus_parts.append(f"派遣+{perm_exp_bonus}")
        rows.append(("📈 永久加成", " | ".join(bonus_parts)))

    # 钥匙解锁区域
    unlocked = spirit.get("unlocked_locations", [])
    if unlocked:
        rows.append(("🔑 钥匙解锁", f"{len(unlocked)} 个区域"))

    rows.extend([
        ("🎒 背包", f"{bag_count} 件"),
        ("🐾 嘿咻", f"{heixiu} 只"),
        ("🏆 成就", f"{ach_count} 个"),
        ("", ""),
        ("💫 状态", buff_str),
    ])

    card = ui.render_data_card(
        f"📋 {name_display} 的修行档案",
        rows,
        footer="👉输入  成就 | 背包 | 排行榜 | 图鉴"
    )
    await profile_cmd.finish(card)