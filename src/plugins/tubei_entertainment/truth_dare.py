"""
晋宁会馆·秃贝五边形 4.1
真心话大冒险

公开群可用（趣味引流功能）
题库从 config/questions.json 读取
"""

import random
import json
import logging
from pathlib import Path

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from src.common.ui_renderer import ui
from src.common.permission import check_permission

logger = logging.getLogger("tubei.truth_dare")

QUESTIONS_FILE = Path("config/questions.json")
DEFAULT_QUESTIONS = {
    "truth": ["如果你能拥有无限大人的一个空间系技能，你最想拥有哪个？"],
    "dare": ["艾特妖王大人（析沐），并诚挚地说一句夸赞。"],
}


def load_questions() -> dict:
    """加载题库"""
    if not QUESTIONS_FILE.exists():
        return DEFAULT_QUESTIONS
    try:
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"[TruthDare] 加载题库失败: {e}")
        return DEFAULT_QUESTIONS


# ==================== 指令注册 ====================

truth_cmd = on_command("真心话", priority=5, block=True)
dare_cmd = on_command("大冒险", priority=5, block=True)


@truth_cmd.handle()
async def handle_truth(bot: Bot, event: MessageEvent):
    # 公开群可用
    perm = await check_permission(event, "真心话大冒险 · 灵力诚实探测", min_tier="public")
    if not perm.allowed:
        await truth_cmd.finish(perm.deny_message)

    questions = load_questions()
    pool = questions.get("truth", [])

    if not pool:
        await truth_cmd.finish(ui.error("题库空了..."))

    question = random.choice(pool)

    card = ui.render_result_card(
        "❤️ 灵力诚实探测",
        "请听题：",
        stats=[("📜 题目", "")],
        extra=f"👉 {question}",
        footer="👉输入  真心话 再来一题 | 大冒险"
    )
    await truth_cmd.finish(card)


@dare_cmd.handle()
async def handle_dare(bot: Bot, event: MessageEvent):
    # 公开群可用
    perm = await check_permission(event, "真心话大冒险 · 灵压勇气挑战", min_tier="public")
    if not perm.allowed:
        await dare_cmd.finish(perm.deny_message)

    questions = load_questions()
    pool = questions.get("dare", [])

    if not pool:
        await dare_cmd.finish(ui.error("题库空了..."))

    question = random.choice(pool)

    card = ui.render_result_card(
        "🔥 灵压勇气挑战",
        "请接受挑战：",
        stats=[("📜 任务", "")],
        extra=f"👉 {question}",
        footer="👉输入  大冒险 再来一题 | 真心话"
    )
    await dare_cmd.finish(card)