"""
晋宁会馆·秃贝五边形 4.1
文案管理器

职责：
  1. 启动时一次性加载 responses.yaml 到内存
  2. 提供统一的文案获取接口（支持 dot 路径、随机选择、模板填充）
  3. 所有模块必须通过此管理器获取文案，禁止直接读 yaml

接口说明：
  get_text(key_path, args)      获取单条文案（列表则随机选一条）
  get_list(key_path)            获取完整列表
  get_random_from(key_path)     从列表随机选一条并格式化
  reload()                      热重载文案文件
"""

import yaml
import random
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("tubei.response")

RESPONSES_PATH = Path("config/responses.yaml")


class ResponseManager:
    """
    单例文案管理器

    数据结构示例：
      responses.yaml:
        cultivation:
          meditate_scene:
            - "你在聚灵台盘膝而坐..."
            - "微风拂过，风铃轻响..."
          meditate_success: "聚灵完成！运势[{fortune}]..."

      调用方式：
        await resp_manager.get_text("cultivation.meditate_success", {"fortune": "大吉"})
        resp_manager.get_list("cultivation.meditate_scene")
    """
    _instance: Optional["ResponseManager"] = None

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._load()

    @classmethod
    def get_instance(cls) -> "ResponseManager":
        if cls._instance is None:
            cls._instance = ResponseManager()
        return cls._instance

    def _load(self):
        """加载 responses.yaml"""
        if not RESPONSES_PATH.exists():
            logger.warning(f"[ResponseManager] {RESPONSES_PATH} 不存在！")
            self._data = {}
            return

        try:
            with open(RESPONSES_PATH, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
            # 统计加载的文案数量
            total = self._count_entries(self._data)
            logger.info(
                f"[ResponseManager] 文案加载完成 | "
                f"顶层键: {list(self._data.keys())} | "
                f"总条目: {total}"
            )
        except Exception as e:
            logger.error(f"[ResponseManager] 加载失败: {e}")
            self._data = {}

    def _count_entries(self, data: Any, depth: int = 0) -> int:
        """递归统计文案条目总数"""
        if depth > 5:
            return 0
        if isinstance(data, dict):
            return sum(self._count_entries(v, depth + 1) for v in data.values())
        if isinstance(data, list):
            return len(data)
        if isinstance(data, str):
            return 1
        return 0

    def reload(self):
        """热重载文案文件（管理员可通过 /重载配置 触发）"""
        self._load()
        logger.info("[ResponseManager] 文案已热重载")

    # ================================================================
    #  路径解析
    # ================================================================

    def _resolve_path(self, key_path: str) -> Any:
        """
        解析 dot 路径到对应数据

        示例：
          "cultivation.meditate_success"
          → self._data["cultivation"]["meditate_success"]

          "fortune_yi"
          → self._data["fortune_yi"]
        """
        keys = key_path.split(".")
        data = self._data
        for k in keys:
            if isinstance(data, dict):
                data = data.get(k)
            else:
                return None
            if data is None:
                return None
        return data

    # ================================================================
    #  公共接口
    # ================================================================

    async def get_text(
        self,
        key_path: str,
        args: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        获取文案文本

        如果目标是列表 → 随机选一条
        如果目标是字典 → 取 "normal" 键（兼容旧版多人格结构）
        最后进行模板变量填充

        :param key_path: dot 分隔路径，如 "cultivation.meditate_success"
        :param args: 模板变量字典，如 {"fortune": "大吉", "gain": 30}
        :return: 格式化后的文案文本
        """
        if args is None:
            args = {}

        text = self._resolve_path(key_path)

        if text is None:
            logger.warning(f"[ResponseManager] 文案缺失: {key_path}")
            return f"[文案缺失: {key_path}]"

        # 字典 → 取 normal 键（兼容旧版）
        if isinstance(text, dict):
            text = text.get("normal", str(text))

        # 列表 → 随机选一条
        if isinstance(text, list):
            text = random.choice(text) if text else ""

        # 确保是字符串
        if not isinstance(text, str):
            text = str(text)

        # 模板填充
        try:
            return text.format(**args)
        except (KeyError, IndexError, ValueError) as e:
            logger.warning(
                f"[ResponseManager] 格式化失败 "
                f"key={key_path} args={args}: {e}"
            )
            return text

    def get_list(self, key_path: str) -> List[str]:
        """
        获取列表型文案（不做随机选择，返回完整列表）

        用途：
          - fortune_yi / fortune_ji（宜忌池）
          - garden_whispers_thirsty / _happy（密语池）
          - garden_water_feedback（浇水反馈池）
          - cultivation.meditate_scene（场景池）

        :param key_path: dot 分隔路径
        :return: 字符串列表（路径不存在或非列表返回空列表）
        """
        data = self._resolve_path(key_path)
        if isinstance(data, list):
            return list(data)  # 浅拷贝
        return []

    def get_random_from(
        self,
        key_path: str,
        default: str = "",
        **kwargs
    ) -> str:
        """
        从列表中随机取一条并格式化

        便捷方法，等同于：
          pool = get_list(key_path)
          text = random.choice(pool)
          return text.format(**kwargs)

        :param key_path: 列表型文案路径
        :param default: 列表为空时的默认值
        :param kwargs: 模板变量
        :return: 格式化后的随机文本
        """
        pool = self.get_list(key_path)
        if not pool:
            return default or f"[列表为空: {key_path}]"

        text = random.choice(pool)
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    def get_value(self, key_path: str, default: Any = None) -> Any:
        """
        获取任意类型的值（不做格式化处理）
        用于获取非文案的配置数据

        :param key_path: dot 分隔路径
        :param default: 默认值
        :return: 原始值
        """
        result = self._resolve_path(key_path)
        return result if result is not None else default


# ==================== 全局单例 ====================
resp_manager = ResponseManager.get_instance()