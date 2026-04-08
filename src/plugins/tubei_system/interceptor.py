"""
晋宁会馆·秃贝五边形 4.1
消息拦截器

改进（相对2.0）：
  1. 取消白名单机制 → 所有群都能响应
  2. 接入身份感知系统 → 自动检测用户身份变更
  3. 调试群消息标记 → 日报统计时可过滤
  4. 保留防刷屏机制
"""

import time
from typing import Dict, List

from nonebot.adapters.onebot.v11 import (
    Bot, GroupMessageEvent, MessageEvent,
    PrivateMessageEvent, MessageSegment
)
from nonebot.message import event_preprocessor
from nonebot.exception import IgnoredException
from nonebot.log import logger

from .config import system_config
from .recorder import recorder
from src.common.group_manager import group_manager
from src.common.identity import identity_manager

# 引入 resp_manager
from src.common.response_manager import resp_manager
from src.common.utils import get_current_hour # 确保 utils 里有这个



# ==================== 内存缓存 ====================

# 用户消息时间戳历史
SPAM_CACHE: Dict[int, List[float]] = {}

# 封禁列表：{uid: 解封时间戳}
BAN_LIST: Dict[int, float] = {}

# 新增：劝睡冷却缓存
SLEEP_COOLDOWN: Dict[int, float] = {}

# ==================== 配置快捷引用 ====================

SUPERUSERS = system_config.superusers
ADMINS = system_config.tubei_admins
THRESHOLD = system_config.tubei_spam_threshold
BAN_DURATION = system_config.tubei_ban_duration


@event_preprocessor
async def system_guard(bot: Bot, event: MessageEvent):
    """
    全局消息拦截器

    流程：
    1. 特权豁免检查
    2. 封禁状态检查
    3. 频率限制检查
    4. 身份感知检查（异步，不阻塞）
    """
    user_id = str(event.user_id)
    uid_int = int(event.user_id)
    current_time = time.time()

    # ===== 1. 特权豁免 =====
    if user_id in SUPERUSERS or user_id in ADMINS:
        # 管理员也触发身份感知（但不阻塞）
        if isinstance(event, GroupMessageEvent):
            await _try_identity_check(user_id, event.group_id, bot)
        return

    # ===== 2. 封禁状态检查 =====
    if uid_int in BAN_LIST:
        unlock_time = BAN_LIST[uid_int]
        if current_time < unlock_time:
            raise IgnoredException("User Banned")
        else:
            del BAN_LIST[uid_int]
            if uid_int in SPAM_CACHE:
                del SPAM_CACHE[uid_int]
            logger.info(f"[Interceptor] 用户 {user_id} 封禁已解除")


    # ===== 2.5 馆禁时间劝睡逻辑 =====
    # 条件：核心群 + 非管理员 + 馆禁时段
    # 注意：game_config 需要在文件头引入
    from src.plugins.tubei_system.config import game_config
    
    is_core_group = group_manager.is_core_group(event.group_id) if isinstance(event, GroupMessageEvent) else False
    start_h = game_config.sleep_start
    end_h = game_config.sleep_end
    now_h = get_current_hour()
    
    # 判断是否在 1点-5点之间（跨天逻辑：start > end 的情况也兼容，虽然目前是 1-5）
    is_curfew = False
    if start_h <= end_h:
        is_curfew = start_h <= now_h < end_h
    else:
        is_curfew = now_h >= start_h or now_h < end_h

    if is_core_group and is_curfew and user_id not in SUPERUSERS and user_id not in ADMINS:
        # 冷却检查 (30分钟 = 1800秒)
        last_warn = SLEEP_COOLDOWN.get(uid_int, 0)
        if current_time - last_warn > 1800:
            # 概率触发 (5%)
            import random
            if random.random() < 0.05:
                SLEEP_COOLDOWN[uid_int] = current_time
                text = await resp_manager.get_random_from("system.sleep_persuasion")
                try:
                    # 引用回复
                    await bot.send(event, MessageSegment.reply(event.message_id) + text)
                except:
                    pass

    # ===== 3. 频率限制检查 =====
    if uid_int not in SPAM_CACHE:
        SPAM_CACHE[uid_int] = []

    # 清理 60 秒之前的记录
    history = [t for t in SPAM_CACHE[uid_int] if current_time - t <= 60]
    history.append(current_time)
    SPAM_CACHE[uid_int] = history

    count = len(history)

    if count <= THRESHOLD:
        # 未超限，触发身份感知
        if isinstance(event, GroupMessageEvent):
            await _try_identity_check(user_id, event.group_id, bot)
        return

    # 超限警告
    if count == THRESHOLD + 1:
        nickname = _get_nickname(event)
        await recorder.add_event("spam_block", uid_int, {"level": "warning"})

        msg = f"💨 呼... {nickname}小友，灵力感应太频繁了，让我喘口气嘛 (冒烟)"
        try:
            await bot.send(event, msg)
        except Exception:
            pass
        raise IgnoredException("Spam Warning")

    # 超限封禁
    if count >= THRESHOLD + 2:
        BAN_LIST[uid_int] = current_time + BAN_DURATION
        await recorder.add_event("spam_block", uid_int, {"level": "ban"})

        ban_minutes = BAN_DURATION // 60
        msg = f"⚠ 灵力回路过载！强制进入 {ban_minutes} 分钟休眠模式。"

        try:
            if isinstance(event, GroupMessageEvent):
                await bot.send(event, MessageSegment.at(uid_int) + msg)
            else:
                await bot.send(event, msg)
        except Exception:
            pass

        logger.warning(f"[Interceptor] 用户 {user_id} 因刷屏被封禁 {ban_minutes} 分钟")
        raise IgnoredException("Spam Ban Triggered")


async def _try_identity_check(user_id: str, group_id: int, bot: Bot):
    """
    尝试进行身份感知检查
    如果用户身份发生变更，通过私聊通知用户
    """
    try:
        notify_msg = await identity_manager.check_and_update(user_id, group_id)
        if notify_msg:
            try:
                await bot.send_private_msg(
                    user_id=int(user_id),
                    message=notify_msg
                )
            except Exception:
                # 私聊发送失败（对方未添加好友等），忽略
                logger.debug(f"[Interceptor] 无法私聊通知 {user_id} 身份变更")
    except Exception as e:
        logger.debug(f"[Interceptor] 身份检查异常: {e}")


def _get_nickname(event: MessageEvent) -> str:
    """提取用户昵称"""
    if isinstance(event, GroupMessageEvent) and event.sender.card:
        return event.sender.card
    if event.sender.nickname:
        return event.sender.nickname
    return "小友"



