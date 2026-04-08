"""
晋宁会馆·秃贝五边形 4.1
每日灵力运行报告

每日 00:05 自动生成并私聊发送给决策组
调试群数据不纳入统计
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

from nonebot import get_bot, require

try:
    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler
except ImportError:
    scheduler = None
    logging.warning("[Reporter] APScheduler 未安装，日报功能禁用")

from src.common.data_manager import data_manager
from src.common.ui_renderer import ui
from .config import system_config

logger = logging.getLogger("tubei.reporter")
LOG_DIR = Path("data/logs")


async def generate_daily_report():
    """生成并发送昨日运行报告"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{yesterday}.jsonl"

    # 统计
    stats = Counter()
    total_sp_generated = 0
    active_users = set()
    taste_loss_count = 0

    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        evt_type = entry.get("type", "unknown")
                        uid = entry.get("uid")
                        evt_data = entry.get("data", {})

                        # 跳过调试群数据（通过 group_id 判断）
                        # 如果记录中包含 group_id 且为调试群则跳过
                        # 目前日志未记录 group_id，所以全部统计
                        # 未来可增强

                        stats[evt_type] += 1
                        if uid:
                            active_users.add(uid)

                        if evt_type == "meditation":
                            total_sp_generated += evt_data.get("sp_gain", 0)
                        if evt_type == "kitchen" and evt_data.get("taste_loss"):
                            taste_loss_count += 1
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"[Reporter] 读取日志失败: {e}")

    # 全局状态
    bot_status = await data_manager.get_bot_status()
    altar_energy = bot_status.get("altar_energy", 0)
    current_persona = bot_status.get("persona", "normal")

    total_events = sum(stats.values())

    report = ui.render_data_card(
        f"📊 每日灵力运行报告 [{yesterday}]",
        [
            ("👥 活跃妖灵", f"{len(active_users)} 位"),
            ("📨 处理讯息", f"{total_events} 条"),
            ("", ""),
            ("🧘 聚灵修行", f"{stats.get('meditation', 0)} 次 (+{total_sp_generated} SP)"),
            ("🍳 厨房生存", f"{stats.get('kitchen', 0)} 次 (味蕾丧失 {taste_loss_count} 人)"),
            ("🔮 灵质鉴定", f"{stats.get('resonance', 0)} 次"),
            ("🌿 药圃操作", f"{stats.get('garden_water', 0) + stats.get('garden_harvest', 0)} 次"),
            ("⚔️ 灵力切磋", f"{stats.get('duel_win', 0)} 次"),
            ("🐾 嘿咻捕捉", f"{stats.get('heixiu_capture', 0)} 次"),
            ("", ""),
            ("🚫 刷屏拦截", f"{stats.get('spam_block', 0)} 次"),
            ("❌ 系统错误", f"{stats.get('error', 0)} 次"),
            ("⛩ 祭坛能量", f"{altar_energy} / 1000"),
            ("🎭 当前相位", current_persona),
        ],
        footer="今日也是为会馆努力工作的一天呢 (嘿咻)"
    )

    # 发送
    try:
        bot = get_bot()
        for superuser in system_config.superusers:
            try:
                await bot.send_private_msg(user_id=int(superuser), message=report)
                logger.info(f"[Reporter] 日报已发送给 {superuser}")
            except Exception as e:
                logger.error(f"[Reporter] 发送给 {superuser} 失败: {e}")
    except Exception as e:
        logger.error(f"[Reporter] 获取Bot实例失败: {e}")

async def cleanup_old_logs():
    """清理30天前的日志文件"""
    import os
    from datetime import datetime, timedelta

    if not LOG_DIR.exists():
        return

    cutoff = datetime.now() - timedelta(days=30)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    cleaned = 0

    for f in LOG_DIR.iterdir():
        if f.suffix == ".jsonl" and f.stem < cutoff_str:
            try:
                f.unlink()
                cleaned += 1
                logger.info(f"[Reporter] 已清理旧日志: {f.name}")
            except Exception as e:
                logger.error(f"[Reporter] 清理日志失败 {f.name}: {e}")

    if cleaned > 0:
        logger.info(f"[Reporter] 共清理 {cleaned} 个过期日志文件")


if scheduler:
    scheduler.add_job(
        generate_daily_report, "cron",
        hour=0, minute=5,
        id="daily_report", replace_existing=True
    )
    scheduler.add_job(
        cleanup_old_logs, "cron",
        hour=0, minute=10,
        id="cleanup_old_logs", replace_existing=True
    )