"""
晋宁会馆·秃贝五边形 4.1
妖灵药圃 · 灵植小院

3.2 改动：
1. 药圃数据统一为 4 格 list（启动时已迁移）
2. 卡片式反馈 + 密语系统
3. 文案全部从 resp_manager 获取
4. 收获时 increment_stat("total_harvest_count") 支持成就
5. 收获后自动检查统计类成就 + 满园春色成就
6. 露水凝珠：灌溉时自动消耗，所有植物 water_count+2
"""

import time
import random
from datetime import datetime
from collections import Counter

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent
from nonebot.params import CommandArg
from nonebot.adapters import Message

from src.common.data_manager import data_manager
from src.common.response_manager import resp_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.common.utils import get_today_str
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.mutex import check_mutex, MutexError
from src.plugins.tubei_system.recorder import recorder
from src.plugins.tubei_cultivation.achievement import achievement_engine


# ==================== 指令注册 ====================
garden_cmd = on_command("药圃", aliases={"妖灵药圃"}, priority=5, block=True)
sow_cmd = on_command("播种", priority=5, block=True)
water_cmd = on_command("灌溉", aliases={"浇水"}, priority=5, block=True)
harvest_cmd = on_command("收获", priority=5, block=True)


# ==================== 工具函数 ====================

def _get_empty_slot() -> dict:
    return {"status": "empty", "water_count": 0, "last_water": ""}


def _ensure_garden(data: dict) -> list:
    """确保药圃数据是 4 格 list（兜底）"""
    garden = data.get("garden", [])
    if not isinstance(garden, list):
        garden = []
    while len(garden) < game_config.garden_slot_count:
        garden.append(_get_empty_slot())
    return garden


# ==================== 查看药圃 ====================
@garden_cmd.handle()
async def handle_garden(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "妖灵药圃 · 灵植小院",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await garden_cmd.finish(perm.deny_message)

    members = await data_manager.get_all_members()
    owner_name = members.get(uid, {}).get("spirit_name", "路人")

    data = await data_manager.get_spirit_data(uid)
    garden = _ensure_garden(data)
    today = get_today_str()
    icons = game_config.garden_icons

    # 检查是否有露水凝珠
    items = data.get("items", {})
    has_dew = items.get("露水凝珠", 0) > 0

    # 构建地图和详情
    grid_cells = []
    details = []
    active_plants = []

    growth_cfg = game_config.garden_growth

    for i, slot in enumerate(garden):
        st = slot.get("status", "empty")
        icon = icons.get(st, "❓")
        grid_cells.append(f"[{i+1}] {icon}")

        if st == "empty":
            details.append(f"  [{i+1}] 待开垦")
        else:
            name = slot.get("plant_name", "未知")
            wc = slot.get("water_count", 0)
            lw = slot.get("last_water", "")
            is_thirsty = (lw != today and st != "mature")

            if st != "mature":
                active_plants.append((name, is_thirsty))

            water_mark = " 💧" if is_thirsty else ""

            if st == "seed":
                need = growth_cfg.get("seed_to_sprout", 1)
                bar = ui.render_progress_bar(wc, need, length=5, filled_char="🟩", empty_char="⬜")
                details.append(f"  [{i+1}] 种子{water_mark}\n    {bar}")
            elif st == "sprout":
                need = growth_cfg.get("sprout_to_growing", 2)
                bar = ui.render_progress_bar(wc, need, length=5, filled_char="🟩", empty_char="⬜")
                details.append(f"  [{i+1}] 嫩芽{water_mark}\n    {bar}")
            elif st == "growing":
                need = growth_cfg.get("growing_to_mature", 5)
                bar = ui.render_progress_bar(wc, need, length=5, filled_char="🟩", empty_char="⬜")
                details.append(f"  [{i+1}] {name}{water_mark}\n    {bar}")
            elif st == "mature":
                details.append(f"  [{i+1}] {name} ✨可收获!")
            else:
                details.append(f"  [{i+1}] {name}")

    # 地图网格
    grid = ui.render_mini_grid(grid_cells, columns=2)

    # 密语
    whisper = ""
    if active_plants:
        plant_name, is_thirsty = random.choice(active_plants)
        key = "garden_whispers_thirsty" if is_thirsty else "garden_whispers_happy"
        whisper_text = resp_manager.get_random_from(key, name=plant_name)
        if whisper_text and not whisper_text.startswith("["):
            whisper = f"\n{ui.THIN_DIVIDER}\n💬 {whisper_text}"

    detail_view = "\n".join(details)

    # 露水凝珠提示
    dew_hint = ""
    if has_dew:
        dew_hint = f"\n💧 持有露水凝珠 ×{items.get('露水凝珠', 0)}（灌溉时自动使用，效果翻倍）"

    content = f"{grid}\n{ui.THIN_DIVIDER}\n{detail_view}{dew_hint}{whisper}"

    card = ui.render_panel(
        f"{owner_name}的妖灵药圃",
        content,
        footer="👉输入  播种 | 灌溉 | 收获"
    )
    await garden_cmd.finish(card)


# ==================== 播种 ====================
@sow_cmd.handle()
async def handle_sow(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    uid = str(event.user_id)

    perm = await check_permission(event, "妖灵药圃 · 播种",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await sow_cmd.finish(perm.deny_message)

    try:
        await check_mutex(uid, "garden")
    except MutexError as e:
        await sow_cmd.finish(e.message)

    data = await data_manager.get_spirit_data(uid)
    garden = _ensure_garden(data)
    items = data.get("items", {})

    if items.get("神秘种子", 0) < 1:
        await sow_cmd.finish(ui.error("缺少 [神秘种子]。可通过派遣获得~"))

    target_idx = -1
    for i in range(len(garden)):
        if garden[i].get("status", "empty") == "empty":
            target_idx = i
            break

    if target_idx == -1:
        await sow_cmd.finish(ui.error("药圃已满，请先收获成熟的灵植。"))

    # 消耗种子
    items["神秘种子"] -= 1
    if items["神秘种子"] <= 0:
        del items["神秘种子"]

    # 随机灵植
    plants = game_config.garden_plants
    plant_name = random.choice(list(plants.keys()))

    garden[target_idx] = {
        "status": "seed",
        "plant_name": plant_name,
        "water_count": 0,
        "last_water": "",
        "sow_time": time.time(),
    }

    await data_manager.update_spirit_data(uid, {"garden": garden, "items": items})

    await sow_cmd.finish(ui.render_result_card(
        "妖灵药圃 · 播种",
        f"在第 {target_idx + 1} 块灵田种下了一颗种子~",
        stats=[("🌱 位置", f"第 {target_idx + 1} 格"), ("🌰 种子", "已消耗 1 颗")],
        footer="👉输入  灌溉 浇水促进生长"
    ))


# ==================== 灌溉 ====================
@water_cmd.handle()
async def handle_water(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "妖灵药圃 · 灌溉",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await water_cmd.finish(perm.deny_message)

    try:
        await check_mutex(uid, "garden")
    except MutexError as e:
        await water_cmd.finish(e.message)

    data = await data_manager.get_spirit_data(uid)
    garden = _ensure_garden(data)
    items = data.get("items", {})
    today = get_today_str()
    growth_cfg = game_config.garden_growth

    # 检查露水凝珠
    has_dew = items.get("露水凝珠", 0) > 0
    water_amount = 1
    dew_used = False

    if has_dew:
        water_amount = 2
        items["露水凝珠"] -= 1
        if items["露水凝珠"] <= 0:
            del items["露水凝珠"]
        dew_used = True

    watered_count = 0
    grow_msg = []

    for i in range(len(garden)):
        slot = garden[i]
        st = slot.get("status", "empty")
        lw = slot.get("last_water", "")

        if st in ("empty", "mature") or lw == today:
            continue

        slot["water_count"] = slot.get("water_count", 0) + water_amount
        slot["last_water"] = today
        watered_count += 1

        # 检查是否成长（可能因为露水凝珠一次跨越多个阶段）
        wc = slot["water_count"]

        if st == "seed" and wc >= growth_cfg.get("seed_to_sprout", 1):
            slot["status"] = "sprout"
            slot["water_count"] = wc - growth_cfg.get("seed_to_sprout", 1)
            grow_msg.append(f"[{i+1}] 发芽了！ 🌱")
            # 继续检查是否直接进入下一阶段
            st = "sprout"
            wc = slot["water_count"]

        if st == "sprout" and wc >= growth_cfg.get("sprout_to_growing", 2):
            slot["status"] = "growing"
            slot["water_count"] = wc - growth_cfg.get("sprout_to_growing", 2)
            grow_msg.append(f"[{i+1}] 长高了！ 🌿")
            st = "growing"
            wc = slot["water_count"]

        if st == "growing" and wc >= growth_cfg.get("growing_to_mature", 5):
            slot["status"] = "mature"
            grow_msg.append(f"[{i+1}] 成熟了！ 🌸")

    if watered_count == 0:
        # 如果使用了露水凝珠但没有植物可浇，退还
        if dew_used:
            items["露水凝珠"] = items.get("露水凝珠", 0) + 1
            await data_manager.update_spirit_data(uid, {"items": items})
        msg = await resp_manager.get_text("garden.water_none")
        await water_cmd.finish(msg)

    await data_manager.update_spirit_data(uid, {"garden": garden, "items": items})
    await recorder.add_event("garden_water", int(uid), {
        "count": watered_count, "dew_used": dew_used
    })

    # 反馈
    feedback = resp_manager.get_random_from("garden_water_feedback", default="💧 浇水成功！")

    tail = ""
    if grow_msg:
        tail = "\n ✨ " + "，".join(grow_msg)

    extra_lines = []
    if dew_used:
        extra_lines.append("💧 露水凝珠生效！浇水效果翻倍！")
    if tail.strip():
        extra_lines.append(tail.strip())

    extra_text = "\n".join(extra_lines) if extra_lines else None

    await water_cmd.finish(ui.render_result_card(
        "妖灵药圃 · 灌溉",
        feedback,
        stats=[("💧 浇灌", f"{watered_count} 棵植物 (每棵+{water_amount}水)")],
        extra=extra_text,
        footer="👉输入  药圃 查看状态"
    ))


# ==================== 收获 ====================
@harvest_cmd.handle()
async def handle_harvest(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "妖灵药圃 · 收获",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await harvest_cmd.finish(perm.deny_message)

    data = await data_manager.get_spirit_data(uid)
    garden = _ensure_garden(data)
    items = data.get("items", {})

    harvested = []
    for i in range(len(garden)):
        if garden[i].get("status") == "mature":
            name = garden[i]["plant_name"]
            items[name] = items.get(name, 0) + 1
            harvested.append(name)
            garden[i] = _get_empty_slot()

    if not harvested:
        await harvest_cmd.finish(ui.info("没有成熟的果实可以收获~"))

    await data_manager.update_spirit_data(uid, {"garden": garden, "items": items})
    await recorder.add_event("garden_harvest", int(uid), {"items": harvested})

    # 统计：累计收获数量
    await data_manager.increment_stat(uid, "total_harvest_count", len(harvested))

    # 成就检查：满园春色（同时收获4株）
    if len(harvested) >= 4:
        await achievement_engine.try_unlock(uid, "满园春色", bot, event)

    # 自动统计成就检查（灵植大师等）
    await achievement_engine.check_stat_achievements(uid, bot, event)

    c = Counter(harvested)
    harvest_str = " ".join(f"{k} x{v}" for k, v in c.items())

    plants_desc = game_config.garden_plants
    desc_lines = []
    for name in c.keys():
        desc = plants_desc.get(name, "未知效果")
        desc_lines.append(f"  📌 {name}: {desc}")

    await harvest_cmd.finish(ui.render_result_card(
        "妖灵药圃 · 大丰收！",
        f"🌾 收获了 {len(harvested)} 株灵植",
        stats=[(f"📦 获得", harvest_str)],
        extra="\n".join(desc_lines) if desc_lines else None,
        footer="👉输入  背包 查看道具 | 播种 继续种植 | 图鉴 [道具名]"
    ))