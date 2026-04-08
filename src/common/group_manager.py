"""
晋宁会馆·秃贝五边形 4.1
群分级管理器

三级群分类：
  Tier 0 - CORE:   核心群（晋宁会馆主群、管理组官群、调试群）
  Tier 1 - ALLIED: 联盟群（合作社群、友好粉丝群）
  Tier 2 - PUBLIC: 公开群（任何其他群，默认等级）

每个核心群还有子类型：
  main:  会馆主群（主要活动场所）
  admin: 管理组官群（管理指令可用）
  debug: 调试群（调试指令可用，日报不统计）
"""

import yaml
import logging
from pathlib import Path
from typing import Optional, Set, Dict, Any

logger = logging.getLogger("tubei.group")

GROUPS_CONFIG_PATH = Path("config/groups.yaml")

# 群等级常量
TIER_CORE = "core"
TIER_ALLIED = "allied"
TIER_PUBLIC = "public"
TIER_DANGER = "danger"

# 群子类型常量
TYPE_MAIN = "main"
TYPE_ADMIN = "admin"
TYPE_DEBUG = "debug"


class GroupManager:
    """
    群分级管理器（单例）

    从 config/groups.yaml 加载群配置
    为系统提供群等级查询、权限判断等能力
    """
    _instance: Optional["GroupManager"] = None

    def __init__(self):
        # {group_id: {"name": str, "type": str}}
        self._core_groups: Dict[int, Dict[str, str]] = {}
        self._allied_groups: Dict[int, Dict[str, str]] = {}

        # 宣传配置
        self._promotion: Dict[str, Any] = {}

        # 缓存：所有核心群 ID 集合
        self._core_group_ids: Set[int] = set()
        self._allied_group_ids: Set[int] = set()
        self._main_group_ids: Set[int] = set()
        self._danger_group_ids = set() 
        self._danger_groups: Dict[int, Dict[str, str]] = {}

        # 加载配置
        self._load()

    @classmethod
    def get_instance(cls) -> "GroupManager":
        if cls._instance is None:
            cls._instance = GroupManager()
        return cls._instance

    def _load(self):
        """从 groups.yaml 加载配置"""
        if not GROUPS_CONFIG_PATH.exists():
            logger.warning(f"[GroupManager] {GROUPS_CONFIG_PATH} 不存在，使用默认配置")
            self._load_defaults()
            return

        try:
            with open(GROUPS_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"[GroupManager] 加载配置失败: {e}，使用默认配置")
            self._load_defaults()
            return

        # 解析核心群
        for gid_str, info in data.get("core_groups", {}).items():
            gid = int(gid_str)
            group_info = {
                "name": info.get("name", f"核心群{gid}"),
                "type": info.get("type", TYPE_MAIN),
            }
            self._core_groups[gid] = group_info
            self._core_group_ids.add(gid)
            if group_info["type"] == TYPE_MAIN:
                self._main_group_ids.add(gid)

        # 解析联盟群
        for gid_str, info in (data.get("allied_groups") or {}).items():
            gid = int(gid_str)
            self._allied_groups[gid] = {
                "name": info.get("name", f"联盟群{gid}"),
            }
            self._allied_group_ids.add(gid)

        # 解析危险群
        self._danger_groups: Dict[int, Dict[str, str]] = {}  # 在__init__中也要加这行
        for gid_str, info in (data.get("danger_groups") or {}).items():
            gid = int(gid_str)
            self._danger_group_ids.add(gid)
            self._danger_groups[gid] = {
                "name": info.get("name", f"危险群{gid}"),
            }

        # 解析宣传配置
        self._promotion = data.get("promotion", {})

        logger.info(
            f"[GroupManager] 群配置加载完成 | "
            f"核心群: {len(self._core_groups)} | "
            f"联盟群: {len(self._allied_groups)}"
        )

    def _load_defaults(self):
        """默认配置（硬编码兜底）"""
        default_cores = {
            564234162: {"name": "晋宁会馆主群", "type": TYPE_MAIN},
            210383914: {"name": "管理组官群", "type": TYPE_ADMIN},
            805930992: {"name": "功能调试群", "type": TYPE_DEBUG},
        }
        for gid, info in default_cores.items():
            self._core_groups[gid] = info
            self._core_group_ids.add(gid)
            if info["type"] == TYPE_MAIN:
                self._main_group_ids.add(gid)
                # 默认没有危险群

        self._promotion = {
            "main_group_id": 564234162,
            "main_group_name": "晋宁会馆",
            "slogan": "基于《罗小黑战记》的温馨同人社群",
            "website": " ",
        }

    def reload(self):
        """热重载群配置"""
        self._core_groups.clear()
        self._allied_groups.clear()
        self._core_group_ids.clear()
        self._allied_group_ids.clear()
        self._main_group_ids.clear()
        self._danger_group_ids.clear()
        self._danger_groups.clear()
        self._load()

    # ================================================================
    #  查询接口
    # ================================================================

    def get_group_tier(self, group_id: int) -> str:
        """
        获取群等级
        :return: "core" / "allied" / "public"
        """
        if group_id in self._core_group_ids:
            return TIER_CORE
        if group_id in self._allied_group_ids:
            return TIER_ALLIED
        if group_id in self._danger_group_ids:
            return TIER_DANGER
        return TIER_PUBLIC

    def get_group_type(self, group_id: int) -> Optional[str]:
        """
        获取核心群的子类型
        :return: "main" / "admin" / "debug" / None（非核心群返回None）
        """
        info = self._core_groups.get(group_id)
        return info["type"] if info else None

    def get_group_name(self, group_id: int) -> str:
        """获取群名称（配置中的名称）"""
        if group_id in self._core_groups:
            return self._core_groups[group_id]["name"]
        if group_id in self._allied_groups:
            return self._allied_groups[group_id]["name"]
        if group_id in self._danger_groups:
            return self._danger_groups[group_id]["name"]
        return f"外部群({group_id})"

    def is_core_group(self, group_id: int) -> bool:
        """是否是核心群"""
        return group_id in self._core_group_ids

    def is_allied_group(self, group_id: int) -> bool:
        """是否是联盟群"""
        return group_id in self._allied_group_ids

    def is_main_group(self, group_id: int) -> bool:
        """是否是会馆主群"""
        return group_id in self._main_group_ids

    def is_debug_group(self, group_id: int) -> bool:
        """是否是调试群"""
        return self.get_group_type(group_id) == TYPE_DEBUG

    def is_admin_group(self, group_id: int) -> bool:
        """是否是管理组官群"""
        return self.get_group_type(group_id) == TYPE_ADMIN

    @property
    def core_group_ids(self) -> Set[int]:
        """所有核心群 ID 集合"""
        return self._core_group_ids.copy()

    @property
    def main_group_ids(self) -> Set[int]:
        """所有主群 ID 集合"""
        return self._main_group_ids.copy()

    @property
    def all_known_group_ids(self) -> Set[int]:
        """所有已配置的群 ID（核心 + 联盟 + 危险）"""
        return self._core_group_ids | self._allied_group_ids | self._danger_group_ids

    # ================================================================
    #  宣传相关
    # ================================================================

    @property
    def main_group_id(self) -> int:
        """主群群号"""
        return self._promotion.get("main_group_id", 564234162)

    @property
    def website(self) -> str:
        """官网地址"""
        return self._promotion.get("website", "jinninghuiguan.cn")

    @property
    def slogan(self) -> str:
        """宣传语"""
        return self._promotion.get("slogan", "基于《罗小黑战记》的温馨同人社群")

    def get_about_text(self) -> str:
        """
        生成「关于晋宁会馆」的文本
        用于 /关于 指令和宣传场景
        """
        from src.plugins.tubei_system.config import TUBEI_FULL_NAME
        return (
            "晋宁会馆是一个基于《罗小黑战记》\n"
            "的同人架空社群。\n"
            "\n"
            "这里的妖灵们以会馆为家，\n"
            "修行、种植、探索、切磋...\n"
            "在温馨和谐的氛围中共同成长。\n"
            "\n"
            "🏠 决策组：析沐、吉熙\n"
            "🌱 核心：温馨、和谐、治愈\n"
            "🤖 管家：{TUBEI_FULL_NAME}"
        )

    def get_join_text(self) -> str:
        """
        生成加入会馆的引导文本
        仅在用户主动请求时使用（如私聊"加入会馆"）
        """
        return (
            f"很高兴你对会馆感兴趣~ (嘿咻)\n"
            f"\n"
            f"📮 主群号：{self.main_group_id}\n"
            f"\n"
            f"加入后发送 /登记 即可\n"
            f"建立你的灵力档案，解锁全部功能！"
        )

    def get_feature_locked_text(self, feature_name: str) -> str:
        """
        生成功能锁定提示文本
        当馆外用户触发馆内专属功能时使用
        不直接放群号，引导用户通过 /关于 了解
        """
        return (
            f"💜 {feature_name} 是秃贝在晋宁会馆\n"
            f"   为馆内妖灵们准备的专属玩法~\n"
            f"\n"
            f"📿 发送 /关于 可以了解晋宁会馆"
        )


# ==================== 全局单例 ====================
group_manager = GroupManager.get_instance()