"""
晋宁会馆·秃贝五边形 4.1
灵风传送 —— 妖灵派遣（9 大灵域版）

3.2 改动：
1. 9 个派遣区域（晋宁世界观）
2. 区域描述展示
3. 接入成就检查
4. 记录已探索区域（晋宁旅者成就）
5. 护身符 Buff（灵力+20%）
6. 等级检查加入 unlocked_locations（析沐的钥匙）
7. permanent_expedition_bonus（上古秘卷永久加成）
8. 派遣列表显示钥匙解锁状态
9. 三大决策组信物掉落由 game_balance.yaml drops 控制
"""

import time
import random

from nonebot import on_command, require, get_bot
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters import Message

from src.common.data_manager import data_manager
from src.common.response_manager import resp_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.common.utils import format_duration, timestamp_now
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.recorder import recorder
from src.plugins.tubei_cultivation.achievement import achievement_engine

try:
    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler
except ImportError:
    scheduler = None


# ==================== 指令注册 ====================

exped_cmd = on_command("派遣", aliases={"妖灵派遣", "灵风传送"}, priority=5, block=True)
recall_cmd = on_command("召回", aliases={"强制召回"}, priority=5, block=True)


# ==================== 等级或钥匙检查 ====================

def _can_access_location(user_level: int, req_level: int, loc_name: str, unlocked: list) -> bool:
    """检查用户是否可以进入指定区域（等级足够 或 钥匙已解锁）"""
    if user_level >= req_level:
        return True
    if loc_name in unlocked:
        return True
    return False


def _get_lock_status(user_level: int, req_level: int, loc_name: str, unlocked: list) -> str:
    """获取区域的锁定状态标记"""
    if user_level >= req_level:
        return "🔓"  # 等级解锁
    if loc_name in unlocked:
        return "🔑"  # 钥匙解锁
    return "🔒"  # 未解锁


# ==================== 自动结算 ====================

async def auto_settle_expeditions():
    """定时任务：自动结算所有已完成的派遣"""
    now = time.time()
    spirits = data_manager.spirits_raw

    for uid, data in spirits.items():
        exped = data.get("expedition", {})
        if exped.get("status") != "exploring":
            continue
        if now < exped.get("end_time", 0):
            continue
        await _settle_expedition(uid, data, exped)


async def _settle_expedition(uid: str, data: dict, exped: dict):
    """结算单个用户的派遣"""
    locations = game_config.expedition_locations
    loc_name = exped.get("location", "晋宁老街")
    cfg = locations.get(loc_name)
    if not cfg:
        cfg = list(locations.values())[0] if locations else {}

    sp_min = cfg.get("sp_min", 5)
    sp_max = cfg.get("sp_max", 5)
    sp_gain = random.randint(sp_min, sp_max)

    # 护身符 Buff：灵力+20%
    buffs = data.get("buffs", {})
    if buffs.pop("护身符", None):
        sp_gain = int(sp_gain * 1.2)

    # 永久派遣加成（上古秘卷）
    permanent_exped_bonus = data.get("permanent_expedition_bonus", 0)
    sp_gain += permanent_exped_bonus

    drop_list = []
    items = data.get("items", {})

    # 丰收 Buff
    drop_bonus = 0.0
    if buffs.pop("丰收 Lv1", None):
        drop_bonus = 0.1

    # 凤羽花 Buff：必出法宝碎片
    force_fragment = False
    if buffs.pop("凤羽花", None):
        force_fragment = True

    for item_name, prob in cfg.get("drops", {}).items():
        if item_name == "法宝碎片" and force_fragment:
            items[item_name] = items.get(item_name, 0) + 1
            drop_list.append(item_name)
        elif random.random() < (prob + drop_bonus):
            items[item_name] = items.get(item_name, 0) + 1
            drop_list.append(item_name)

    # 确保凤羽花触发时法宝碎片在掉落列表里
    if force_fragment and "法宝碎片" not in drop_list:
        items["法宝碎片"] = items.get("法宝碎片", 0) + 1
        drop_list.append("法宝碎片")

    new_sp = data.get("sp", 0) + sp_gain

    # 记录已探索区域
    explored = data.get("explored_locations", [])
    if loc_name not in explored:
        explored.append(loc_name)

    await data_manager.update_spirit_data(uid, {
        "sp": new_sp,
        "items": items,
        "expedition": {"status": "idle"},
        "buffs": buffs,
        "explored_locations": explored,
    })

    await data_manager.increment_stat(uid, "total_expedition_count")

    await recorder.add_event("expedition_finish", int(uid), {
        "loc": loc_name, "sp": sp_gain, "drops": drop_list,
    })

    # 成就检查：晋宁旅者（探索全部 9 区域）
    all_locations = list(game_config.expedition_locations.keys())
    if len(explored) >= len(all_locations):
        await achievement_engine.try_unlock(uid, "晋宁旅者")

    # 统计成就
    await achievement_engine.check_stat_achievements(uid)

    # 私聊通知
    try:
        bot = get_bot()
        drop_str = "、".join(drop_list) if drop_list else "无"

        # 构建额外说明
        extra_lines = []
        if permanent_exped_bonus > 0:
            extra_lines.append(f"📈 永久加成：+{permanent_exped_bonus}")

        extra_text = "\n".join(extra_lines) if extra_lines else None

        card = ui.render_result_card(
            "灵风传送 · 探索归来",
            f"你从【{loc_name}】安全返回了~",
            stats=[
                ("📍 地点", loc_name),
                ("✨ 灵力", f"+{sp_gain}"),
                ("📦 掉落", drop_str),
            ],
            extra=extra_text,
            footer="👉输入  派遣 继续探索 | 背包"
        )
        await bot.send_private_msg(user_id=int(uid), message=card)
    except Exception:
        pass


if scheduler:
    scheduler.add_job(
        auto_settle_expeditions, "interval",
        minutes=10, id="expedition_auto_settle",
        replace_existing=True,
    )


# ==================== 强制召回 ====================
@recall_cmd.handle()
async def handle_recall(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(
        event, "灵风传送 · 强制召回",
        min_tier="allied", require_registered=True
    )
    if not perm.allowed:
        await recall_cmd.finish(perm.deny_message)

    data = await data_manager.get_spirit_data(uid)
    exped = data.get("expedition", {})

    if exped.get("status") != "exploring":
        await recall_cmd.finish(ui.info("当前没有正在进行的派遣任务。"))

    penalty = game_config.expedition_recall_penalty
    new_sp = max(0, data.get("sp", 0) - penalty)

    await data_manager.update_spirit_data(uid, {
        "sp": new_sp,
        "expedition": {"status": "idle"},
    })

    await recall_cmd.finish(ui.render_result_card(
        "灵风传送 · 强制召回",
        "灵体已强制返回！",
        stats=[("💰 灵力", f"-{penalty} (当前: {new_sp})")],
        footer="👉输入  派遣 重新出发"
    ))


# ==================== 派遣主指令 ====================
@exped_cmd.handle()
async def handle_expedition(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    uid = str(event.user_id)

    perm = await check_permission(
        event, "灵风传送 · 妖灵派遣",
        min_tier="allied", require_registered=True, deny_promotion=True
    )
    if not perm.allowed:
        await exped_cmd.finish(perm.deny_message)

    arg_text = args.extract_plain_text().strip()
    data = await data_manager.get_spirit_data(uid)
    exped_data = data.get("expedition", {})
    status = exped_data.get("status", "idle")
    now = timestamp_now()

    locations = game_config.expedition_locations
    user_lv = data.get("level", 1)
    unlocked = data.get("unlocked_locations", [])

    # ===== 自动结算 =====
    if status == "exploring" and now >= exped_data.get("end_time", 0):
        await _settle_expedition(uid, data, exped_data)
        data = await data_manager.get_spirit_data(uid)
        status = "idle"

    # ===== 查询进度 =====
    if status == "exploring":
        remain = int(exped_data.get("end_time", 0) - now)
        time_str = format_duration(remain)
        loc = exped_data.get("location", "未知")
        loc_cfg = locations.get(loc, {})
        desc = loc_cfg.get("desc", "")

        card = ui.render_data_card(
            "灵风传送 · 探索中",
            [
                ("📍 地点", loc),
                ("📝 描述", desc),
                ("⏳ 剩余", time_str),
            ],
            footer="👉输入  召回 强制返回"
        )
        await exped_cmd.finish(card)

    # ===== 无参数 → 显示地点列表 =====
    if not arg_text:
        explored = set(data.get("explored_locations", []))
        permanent_exped_bonus = data.get("permanent_expedition_bonus", 0)

        # 按等级分组
        groups = {}
        for name, info in locations.items():
            req_lv = info.get("level", 1)
            if req_lv not in groups:
                groups[req_lv] = []
            groups[req_lv].append((name, info))

        rows = []
        for lv in sorted(groups.keys()):
            # 确定该等级组的解锁状态
            rows.append(("", f"── Lv.{lv} 区域 ──"))
            for name, info in groups[lv]:
                hours = info.get("time", 3600) // 3600
                visited = "✅" if name in explored else "⬜"
                lock = _get_lock_status(user_lv, lv, name, unlocked)
                desc = info.get("desc", "")[:20]

                if lock == "🔒":
                    rows.append((f"  {lock} {name}", f"需要 Lv.{lv}"))
                elif lock == "🔑":
                    rows.append((f"  {visited} {name} 🔑", f"{hours}h | {desc}..."))
                else:
                    rows.append((f"  {visited} {name}", f"{hours}h | {desc}..."))

        rows.append(("", ""))
        rows.append(("🗺 已探索", f"{len(explored)} / {len(locations)} 区域"))
        if permanent_exped_bonus > 0:
            rows.append(("📈 永久加成", f"+{permanent_exped_bonus} 灵力/次"))

        card = ui.render_data_card(
            "灵风传送 · 九大灵域",
            rows,
            footer="👉输入  派遣 [地点名] 出发\n🔑 = 钥匙解锁  🔒 = 等级不足"
        )
        await exped_cmd.finish(card)

    # ===== 发起派遣 =====
    target_loc = arg_text

    if target_loc not in locations:
        await exped_cmd.finish(ui.error("未知地点。请使用 /派遣 查看可选目的地。"))

    cfg = locations[target_loc]
    req_level = cfg.get("level", 1)

    # 等级 + 钥匙检查
    if not _can_access_location(user_lv, req_level, target_loc, unlocked):
        await exped_cmd.finish(ui.error(
            f"等级不足！需要 Lv.{req_level}。\n"
            f"📌 你当前 Lv.{user_lv}\n"
            f"🔑 使用【析沐的钥匙】可提前解锁"
        ))

    # Buff 加速
    buffs = data.get("buffs", {})
    duration = cfg.get("time", 3600)
    time_reduce = 1.0

    if buffs.pop("空间简片", None):
        time_reduce *= 0.5
    if buffs.pop("风行 Lv1", None):
        time_reduce *= 0.9
    if buffs.pop("风行 MAX", None):
        time_reduce *= 0.7

    duration = int(duration * time_reduce)

    await data_manager.update_spirit_data(uid, {
        "expedition": {
            "status": "exploring",
            "location": target_loc,
            "start_time": now,
            "end_time": now + duration,
        },
        "buffs": buffs,
    })

    await recorder.add_event("expedition_start", int(uid), {"loc": target_loc})

    hours = round(duration / 3600, 1)
    desc = cfg.get("desc", "")

    # 构建额外信息
    extra_lines = []
    if time_reduce < 1.0:
        extra_lines.append(f"⚡ 加速生效！耗时已缩短")
    if _get_lock_status(user_lv, req_level, target_loc, unlocked) == "🔑":
        extra_lines.append("🔑 通过析沐的钥匙解锁")

    extra_text = "\n".join(extra_lines) if extra_lines else None

    card = ui.render_result_card(
        "灵风传送 · 出发！",
        f"灵体已传送至【{target_loc}】",
        stats=[
            ("📍 目的地", target_loc),
            ("📝 描述", desc),
            ("⏳ 预计耗时", f"{hours} 小时"),
        ],
        extra=extra_text,
        footer="👉输入  派遣 查看进度 | 召回 强制返回"
    )
    await exped_cmd.finish(card)