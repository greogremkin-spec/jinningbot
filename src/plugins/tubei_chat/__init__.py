"""
晋宁会馆·秃贝五边形 4.1
AI 核心

3.2 改动：
1. block=False → 不吞消息
2. 取消 is_tome 介绍逻辑（@直接聊天）
3. 根据群等级调整行为（公开群不随机插嘴）
4. 休眠时段判断从 game_config 读取
5. 宣传功能：随机插嘴时有概率发宣传内容而非AI回复
"""

import random
import httpx
import json
import logging
from datetime import datetime
from pathlib import Path

from nonebot import on_message, get_driver
from nonebot.adapters.onebot.v11 import (
    Bot, GroupMessageEvent, MessageSegment, PrivateMessageEvent
)
from nonebot.plugin import PluginMetadata

from .rag_engine import build_system_prompt
from src.common.group_manager import group_manager
from src.common.data_manager import data_manager
from src.plugins.tubei_system.config import system_config, game_config

logger = logging.getLogger("tubei.chat")

__plugin_meta__ = PluginMetadata(
    name="秃贝 AI 核心",
    description="DeepSeek-V3 驱动的 AI 对话",
    usage="@秃贝 或 秃贝秃贝 + 任意内容",
)

driver = get_driver()

@driver.on_startup
async def _():
    print("  ✅ [Tubei Chat] AI 核心已注入 (Priority=99)")

# Priority=99 做最后兜底，block=False 不吞消息
ai_chat = on_message(priority=99, block=False)

# ==================== 上下文管理 ====================
# key格式: "group_{group_id}_{user_id}" 或 "private_{user_id}"
# value格式: {"messages": [...], "last_active": timestamp}
CONTEXT_CACHE = {}
MAX_CONTEXT_LEN = 10
CONTEXT_EXPIRE_SECONDS = 21600  # 6小时过期

def _get_context_key(event) -> str:
    """根据事件生成上下文key，按群隔离"""
    from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
    user_id = str(event.user_id)
    if isinstance(event, GroupMessageEvent):
        return f"group_{event.group_id}_{user_id}"
    elif isinstance(event, PrivateMessageEvent):
        return f"private_{user_id}"
    return f"user_{user_id}"


def _cleanup_expired_contexts():
    """清理过期的上下文（超过6小时未活跃的）"""
    import time
    now = time.time()
    expired_keys = [
        k for k, v in CONTEXT_CACHE.items()
        if now - v.get("last_active", 0) > CONTEXT_EXPIRE_SECONDS
    ]
    for k in expired_keys:
        del CONTEXT_CACHE[k]


# ==================== API ====================

def get_api_key() -> str:
    try:
        env_path = Path.cwd() / ".env.prod"
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "SILICONFLOW_API_KEY" in line:
                        return line.split("=")[1].strip().replace('"', '').replace("'", "")
    except Exception:
        pass
    return ""


async def chat_with_deepseek(context_key: str, prompt: str, system_prompt: str = "") -> str:
    API_KEY = get_api_key()
    if not API_KEY:
        return "(错误：未配置 API Key)"

    import time
    global CONTEXT_CACHE

    # 定期清理过期上下文
    _cleanup_expired_contexts()

    if context_key not in CONTEXT_CACHE:
        CONTEXT_CACHE[context_key] = {"messages": [], "last_active": time.time()}

    ctx = CONTEXT_CACHE[context_key]
    ctx["last_active"] = time.time()
    history = ctx["messages"]

    messages = [{"role": "system", "content": system_prompt}] + history + [
        {"role": "user", "content": prompt}
    ]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-ai/DeepSeek-V3",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.siliconflow.cn/v1/chat/completions",
                json=payload, headers=headers
            )
            if resp.status_code == 200:
                reply = resp.json()["choices"][0]["message"]["content"].strip()
                history.append({"role": "user", "content": prompt})
                history.append({"role": "assistant", "content": reply})
                ctx["messages"] = history[-MAX_CONTEXT_LEN * 2:]
                return reply
            return f"(API Error: {resp.status_code})"
    except Exception as e:
        logger.error(f"[Chat] API 调用失败: {e}")
        return "(灵力连接中断)"


# ==================== 休眠判断 ====================

def is_sleeping_time() -> bool:
    h = datetime.now().hour
    return game_config.sleep_start <= h < game_config.sleep_end


# ==================== 宣传功能 ====================

async def _try_send_promotion(bot: Bot, event: GroupMessageEvent) -> bool:
    """
    尝试发送宣传内容。

    返回 True 表示已发送宣传（调用方应跳过AI回复），
    返回 False 表示不发宣传（调用方继续正常AI回复）。
    """
    try:
        status = await data_manager.get_bot_status()
        promo = status.get("promotion", {})

        if not promo.get("enabled", False):
            return False

        chance = promo.get("chance", 0.20)
        if random.random() >= chance:
            return False

        content = promo.get("content", "")
        if not content:
            return False

        await bot.send(event, content)
        return True

    except Exception as e:
        logger.error(f"[Chat] 宣传发送失败: {e}")
        return False


# ==================== 主逻辑 ====================
@ai_chat.handle()
async def handle_chat(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    text = event.get_plaintext().strip()
    user_id = str(event.user_id)

    # 1. 绝对避让指令
    if text.startswith("/") or text.startswith("／"):
        return
    
    # 1.5 避让纯文字指令（防止指令触发后AI还额外回复）
    from src.common.command_registry import get_all_text_triggers, get_text_prefix_triggers, MENU_SECTIONS
    text_triggers = get_all_text_triggers()
    prefix_triggers = get_text_prefix_triggers()
    section_triggers = {s.get("text_trigger", ""): True for s in MENU_SECTIONS.values() if s.get("text_trigger")}

    # 精确匹配
    if text in text_triggers or text in section_triggers:
        return

    # 前缀匹配（如 "使用 天明珠"、"派遣 晋宁老街"）
    for prefix in prefix_triggers:
        if text == prefix or text.startswith(prefix + " "):
            return

    # 1.6 danger群：禁止AI，但不影响任何指令
    is_danger_group = False

    if isinstance(event, GroupMessageEvent):
        from src.common.group_manager import group_manager, TIER_DANGER
        if group_manager.get_group_tier(event.group_id) == TIER_DANGER:
            is_danger_group = True

    # 2. 判断触发条件
    should_trigger = False
    is_random_interjection = False

    if isinstance(event, PrivateMessageEvent):
        should_trigger = True

    elif isinstance(event, GroupMessageEvent):
        # @秃贝 → 触发
        if event.is_tome():
            should_trigger = True
        # "秃贝秃贝" → 触发
        if "秃贝秃贝" in text:
            should_trigger = True

        # 随机插嘴：仅核心群和联盟群
        if not should_trigger:
            tier = group_manager.get_group_tier(event.group_id)
            # 新增：馆禁检查
            if is_sleeping_time() and tier == "core":
                should_trigger = False
            else:
                if tier in ("core", "allied"):
                    min_len = game_config.random_chat_min_length
                    rate = game_config.random_chat_rate
                    if len(text) > min_len and random.random() < rate:
                        should_trigger = True
                        is_random_interjection = True

    # danger群禁止AI触发
    if is_danger_group:
        should_trigger = False

    if not should_trigger:
        return

    # 3. 休眠检查
    if is_sleeping_time() and user_id not in system_config.superusers:
        nickname = event.sender.nickname or "小友"
        await ai_chat.finish(f"（揉眼睛）{nickname}小友，现在是深夜了... 快去睡觉！(OvO)")

    # 4. 宣传功能：随机插嘴时有概率发宣传而非AI回复
    if is_random_interjection and isinstance(event, GroupMessageEvent):
        promoted = await _try_send_promotion(bot, event)
        if promoted:
            return

    # 5. 构建 Prompt 并调用 AI
    group_id = event.group_id if isinstance(event, GroupMessageEvent) else None
    sys_prompt = await build_system_prompt(user_id, group_id=group_id)
    context_key = _get_context_key(event)
    reply = await chat_with_deepseek(context_key, text, sys_prompt)

    # 6. 发送回复
    if isinstance(event, GroupMessageEvent):
        await ai_chat.finish(MessageSegment.at(user_id) + " " + reply)
    else:
        await ai_chat.finish(reply)