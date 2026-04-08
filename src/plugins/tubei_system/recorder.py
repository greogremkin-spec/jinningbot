"""
晋宁会馆·秃贝五边形 4.1
灵质纪事记录器

按日切割 JSONL 日志文件
"""

import time
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger("tubei.recorder")

LOG_DIR = Path("data/logs")
if not LOG_DIR.exists():
    LOG_DIR.mkdir(parents=True)


class EventRecorder:
    """
    事件记录器（单例）

    标准事件类型：
      meditation, kitchen, resonance, duel_win,
      expedition_start, expedition_finish,
      heixiu_capture, registry_new, registry_update,
      spam_block, error, persona_change, admin_action,
      identity_upgrade, garden_water, garden_harvest
    """
    _instance: Optional["EventRecorder"] = None

    def __init__(self):
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "EventRecorder":
        if cls._instance is None:
            cls._instance = EventRecorder()
        return cls._instance

    def _get_log_file(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return LOG_DIR / f"{today}.jsonl"

    async def add_event(
        self,
        event_type: str,
        user_id: int,
        details: Optional[Dict[str, Any]] = None
    ):
        """记录一条事件"""
        if details is None:
            details = {}

        record = {
            "ts": int(time.time()),
            "type": event_type,
            "uid": user_id,
            "data": details,
        }

        async with self._lock:
            try:
                log_file = self._get_log_file()
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.error(f"[Recorder] 写入失败: {e}")


recorder = EventRecorder.get_instance()