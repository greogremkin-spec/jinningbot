"""
晋宁会馆·秃贝五边形 4.1
成就系统 2.0 + 称号系统

功能：
  1. 成就解锁检查（支持自动统计检查和手动触发）
  2. 成就卡片展示
  3. 称号佩戴与切换
  4. 成就定义从 game_balance.yaml 读取

指令：
  /成就        查看已解锁的成就列表
  /称号        查看可用称号
  /称号 [名称]  佩戴指定称号
"""

import time
import logging
from typing import Optional, List, Dict, Any, Tuple

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters import Message

from src.common.data_manager import data_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.common.utils import get_today_str
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.recorder import recorder

logger = logging.getLogger("tubei.achievement")


# ==================== 成就检查引擎 ====================

class AchievementEngine:
    """
    成就检查引擎（单例）

    支持两种检查方式：
    1. stat_gte: 统计字段 >= 目标值（自动检查）
    2. manual: 由各模块主动调用 try_unlock()
    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AchievementEngine()
        return cls._instance

    def _get_definitions(self) -> Dict[str, Any]:
        """从 game_config 获取成就定义"""
        return game_config.get("achievements", default={})

    async def try_unlock(
        self,
        uid: str,
        achievement_id: str,
        notify_bot: Optional[Bot] = None,
        notify_event: Optional[MessageEvent] = None,
    ) -> Optional[str]:
        """
        尝试解锁指定成就（手动触发）

        :param uid: 用户QQ号
        :param achievement_id: 成就ID
        :param notify_bot: 如果提供，解锁时发送通知
        :param notify_event: 通知的事件上下文
        :return: 解锁成功时返回成就名称，已拥有或不存在返回 None
        """
        defs = self._get_definitions()
        ach_def = defs.get(achievement_id)
        if not ach_def:
            return None

        spirit = await data_manager.get_spirit_data(uid)
        current_achs = spirit.get("achievements", [])

        # 检查是否已解锁
        unlocked_ids = set()
        for a in current_achs:
            if isinstance(a, dict):
                unlocked_ids.add(a.get("id", ""))
            elif isinstance(a, str):
                unlocked_ids.add(a)

        if achievement_id in unlocked_ids:
            return None

        # 解锁
        new_ach = {
            "id": achievement_id,
            "name": achievement_id,
            "desc": ach_def.get("desc", ""),
            "rarity": ach_def.get("rarity", "common"),
            "date": get_today_str(),
        }

        # 兼容旧版：如果 achievements 里有纯字符串，保留
        if current_achs and isinstance(current_achs[0], str):
            # 迁移旧格式
            migrated = []
            for old_ach in current_achs:
                old_def = defs.get(old_ach, {})
                migrated.append({
                    "id": old_ach,
                    "name": old_ach,
                    "desc": old_def.get("desc", ""),
                    "rarity": old_def.get("rarity", "common"),
                    "date": "",
                })
            current_achs = migrated

        current_achs.append(new_ach)
        await data_manager.update_spirit_data(uid, {"achievements": current_achs})

        await recorder.add_event("achievement_unlock", int(uid), {
            "achievement": achievement_id,
            "rarity": ach_def.get("rarity", "common"),
        })

        logger.info(f"[Achievement] {uid} 解锁成就: {achievement_id}")

        # 发送通知
        if notify_bot and notify_event:
            rarity_icons = {
                "common": "⭐",
                "rare": "🌟",
                "epic": "💫",
                "legendary": "🌈",
            }
            icon = rarity_icons.get(ach_def.get("rarity", "common"), "⭐")
            title_text = ""
            title = ach_def.get("title")
            if title:
                title_text = f"\n🏷 解锁称号：【{title}】"

            msg = (
                f"\n{icon} 成就解锁！\n"
                f"🏆 【{achievement_id}】\n"
                f"📜 {ach_def.get('desc', '')}"
                f"{title_text}"
            )
            try:
                await notify_bot.send(notify_event, MessageSegment.at(uid) + msg)
            except Exception:
                pass

        return achievement_id

    async def check_stat_achievements(
        self,
        uid: str,
        notify_bot: Optional[Bot] = None,
        notify_event: Optional[MessageEvent] = None,
    ) -> List[str]:
        """
        检查所有基于统计字段的成就（stat_gte 类型）

        在聚灵、厨房等操作后调用
        自动扫描所有 stat_gte 类型的成就定义
        如果用户的统计值满足条件，自动解锁

        :return: 本次新解锁的成就ID列表
        """
        defs = self._get_definitions()
        spirit = await data_manager.get_spirit_data(uid)
        unlocked = []

        for ach_id, ach_def in defs.items():
            if not isinstance(ach_def, dict):
                continue
            if ach_def.get("check_type") != "stat_gte":
                continue

            field = ach_def.get("check_field", "")
            value = ach_def.get("check_value", 0)

            current_val = spirit.get(field, 0)
            if current_val >= value:
                result = await self.try_unlock(
                    uid, ach_id,
                    notify_bot=notify_bot,
                    notify_event=notify_event,
                )
                if result:
                    unlocked.append(result)

        return unlocked

    async def get_user_achievements(self, uid: str) -> List[Dict[str, Any]]:
        """获取用户的成就列表（格式化）"""
        spirit = await data_manager.get_spirit_data(uid)
        achs = spirit.get("achievements", [])

        result = []
        defs = self._get_definitions()

        for a in achs:
            if isinstance(a, str):
                # 旧格式兼容
                ach_def = defs.get(a, {})
                result.append({
                    "id": a,
                    "name": a,
                    "desc": ach_def.get("desc", ""),
                    "rarity": ach_def.get("rarity", "common"),
                    "date": "",
                })
            elif isinstance(a, dict):
                result.append(a)

        return result

    async def get_available_titles(self, uid: str) -> List[str]:
        """获取用户可佩戴的称号列表"""
        achs = await self.get_user_achievements(uid)
        defs = self._get_definitions()
        titles = []

        for a in achs:
            ach_id = a.get("id", "")
            ach_def = defs.get(ach_id, {})
            title = ach_def.get("title")
            if title:
                titles.append(title)

        return titles

    async def get_equipped_title(self, uid: str) -> str:
        """获取用户当前佩戴的称号"""
        spirit = await data_manager.get_spirit_data(uid)
        return spirit.get("equipped_title", "")


# 全局单例
achievement_engine = AchievementEngine.get_instance()


# ==================== 指令注册 ====================

achievement_cmd = on_command("成就", aliases={"我的成就"}, priority=5, block=True)
title_cmd = on_command("称号", aliases={"我的称号"}, priority=5, block=True)


# ==================== 成就查看 ====================

@achievement_cmd.handle()
async def handle_achievement(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "成就系统", min_tier="allied", require_registered=True)
    if not perm.allowed:
        await achievement_cmd.finish(perm.deny_message)

    # 先做一次自动检查
    await achievement_engine.check_stat_achievements(uid, bot, event)

    achs = await achievement_engine.get_user_achievements(uid)

    if not achs:
        await achievement_cmd.finish(ui.render_panel(
            "🏆 会馆成就系统",
            "还没有解锁任何成就~\n\n💡 通过修行、探索、战斗等活动解锁成就",
            footer="👉输入 聚灵 | 派遣 | 厨房"
        ))
        return

    rarity_icons = {
        "common": "⭐",
        "rare": "🌟",
        "epic": "💫",
        "legendary": "🌈",
    }

    # 按稀有度排序
    rarity_order = {"legendary": 0, "epic": 1, "rare": 2, "common": 3}
    achs_sorted = sorted(achs, key=lambda x: rarity_order.get(x.get("rarity", "common"), 99))

    lines = []
    for a in achs_sorted:
        icon = rarity_icons.get(a.get("rarity", "common"), "⭐")
        name = a.get("name", a.get("id", "未知"))
        desc = a.get("desc", "")
        date = a.get("date", "")
        date_str = f" ({date})" if date else ""
        lines.append(f"  {icon} 【{name}】{date_str}\n     {desc}")

    equipped = await achievement_engine.get_equipped_title(uid)
    equipped_str = f"🏷 当前称号：【{equipped}】" if equipped else "🏷 未佩戴称号"

    content = "\n".join(lines)
    card = ui.render_panel(
        f"🏆 会馆成就系统 ({len(achs)} 个)",
        f"{equipped_str}\n\n{content}",
        footer="👉输入 我的称号 查看可用称号"
    )
    await achievement_cmd.finish(card)


# ==================== 称号系统 ====================

@title_cmd.handle()
async def handle_title(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    uid = str(event.user_id)

    perm = await check_permission(event, "称号系统", min_tier="allied", require_registered=True)
    if not perm.allowed:
        await title_cmd.finish(perm.deny_message)

    target_title = args.extract_plain_text().strip()
    available_titles = await achievement_engine.get_available_titles(uid)
    current_title = await achievement_engine.get_equipped_title(uid)

    # 无参数 → 显示可用称号列表
    if not target_title:
        if not available_titles:
            await title_cmd.finish(ui.render_panel(
                "🏷 称号系统",
                "还没有解锁任何称号~\n\n💡 解锁成就可获得对应称号",
                footer="👉输入  成就 查看成就进度"
            ))
            return

        lines = []
        for t in available_titles:
            marker = " ← 当前" if t == current_title else ""
            lines.append(f"  🏷 【{t}】{marker}")

        content = "\n".join(lines)
        card = ui.render_panel(
            "🏷 称号系统",
            f"当前称号：{f'【{current_title}】' if current_title else '未佩戴'}\n\n"
            f"可用称号：\n{content}\n\n"
            f"发送 /称号 [名称] 佩戴\n"
            f"发送 /称号 无 取消佩戴",
        )
        await title_cmd.finish(card)

    # 取消佩戴
    if target_title in ("无", "取消", "卸下"):
        await data_manager.update_spirit_data(uid, {"equipped_title": ""})
        await title_cmd.finish(ui.success("已取消佩戴称号。"))
        return

    # 佩戴指定称号
    if target_title not in available_titles:
        await title_cmd.finish(ui.error(
            f"你还没有解锁【{target_title}】这个称号。\n"
            f"👉 /成就 查看成就进度"
        ))
        return

    await data_manager.update_spirit_data(uid, {"equipped_title": target_title})
    await title_cmd.finish(ui.success(f"已佩戴称号：【{target_title}】"))