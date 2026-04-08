"""
晋宁会馆·秃贝五边形 4.1
数据管理器 —— 全系统心脏

架构：
  启动时一次性加载全部数据到内存
  运行时所有读写操作只操作内存（零磁盘I/O）
  修改后标记 dirty，由定时任务统一原子写回磁盘
  关闭时强制落盘，确保数据安全

改进点（相对2.0）：
  1. 消灭了「每次操作都读写文件」的性能问题
  2. 原子写入（tmp→rename），杜绝断电导致的JSON损坏
  3. 自动备份机制
  4. 药圃数据启动时自动迁移为统一的 list 格式
  5. 新增 identity 相关字段支持（馆内/馆外区分）
  6. 新增 export_for_web() 官网数据导出接口
  7. 新增统计字段（total_meditation_count 等），为官网预留
"""

import ujson as json
import aiofiles
import asyncio
import logging
import shutil
import time
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from copy import deepcopy
from datetime import datetime

logger = logging.getLogger("tubei.data")

# ==================== 路径常量 ====================

DATA_DIR = Path("data")
BACKUP_DIR = DATA_DIR / "backups"
MEMBERS_DB_PATH = DATA_DIR / "members_db.json"
SPIRIT_DB_PATH = DATA_DIR / "spirit_db.json"
BOT_STATUS_PATH = DATA_DIR / "bot_status.json"

# 持久化间隔（秒）
PERSIST_INTERVAL = 30


class DataManager:
    """
    单例数据管理器

    核心原则：
    - 读操作：直接读内存，返回深拷贝（防止外部意外修改原数据）
    - 写操作：修改内存 + 标记 dirty
    - 持久化：定时任务检查 dirty 标记，有变更才写磁盘
    - 写磁盘：原子写入（先写 .tmp，再 rename 覆盖）
    """
    _instance: Optional["DataManager"] = None

    def __init__(self):
        # 异步锁（保护内存数据的并发修改）
        self._lock = asyncio.Lock()

        # 三个核心数据表（内存态）
        self._members: Dict[str, Any] = {}
        self._spirits: Dict[str, Any] = {}
        self._status: Dict[str, Any] = {}

        # 脏标记（True 表示内存数据已修改，需要写回磁盘）
        self._dirty_members = False
        self._dirty_spirits = False
        self._dirty_status = False

        # 定时持久化任务句柄
        self._persist_task: Optional[asyncio.Task] = None

        # 路径常量（供外部模块引用）
        self.BOT_STATUS_PATH = BOT_STATUS_PATH
        self.MEMBERS_DB_PATH = MEMBERS_DB_PATH
        self.SPIRIT_DB_PATH = SPIRIT_DB_PATH

        # 确保目录和文件存在
        self._ensure_infrastructure()

    @classmethod
    def get_instance(cls) -> "DataManager":
        """获取全局单例"""
        if cls._instance is None:
            cls._instance = DataManager()
        return cls._instance

    # ================================================================
    #  初始化与基础设施
    # ================================================================

    def _ensure_infrastructure(self):
        """确保所有必需的目录和文件存在"""
        # 创建目录
        for d in [DATA_DIR, BACKUP_DIR, DATA_DIR / "logs"]:
            if not d.exists():
                d.mkdir(parents=True)

        # 创建默认数据文件
        defaults = {
            MEMBERS_DB_PATH: {},
            SPIRIT_DB_PATH: {},
            BOT_STATUS_PATH: {
                "altar_energy": 0,
                "persona": "normal",
                "ritual_buff_active": False,
                "ritual_start_time": 0,
            },
        }
        for path, default_data in defaults.items():
            if not path.exists():
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_data, f, ensure_ascii=False, indent=2)
                logger.info(f"[DataManager] 创建默认文件: {path}")

    def _load_json_sync(self, path: Path) -> dict:
        """
        同步读取 JSON 文件（仅启动时使用一次）
        如果文件损坏，尝试从备份恢复
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    logger.warning(f"[DataManager] {path.name} 为空文件，使用空字典")
                    return {}
                return json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"[DataManager] {path.name} 解析失败: {e}，尝试备份恢复...")
            return self._try_restore_from_backup(path)
        except FileNotFoundError:
            logger.warning(f"[DataManager] {path.name} 不存在，使用空字典")
            return {}
        except Exception as e:
            logger.error(f"[DataManager] {path.name} 读取异常: {e}")
            return self._try_restore_from_backup(path)

    def _try_restore_from_backup(self, path: Path) -> dict:
        """尝试从备份文件恢复数据"""
        bak_path = path.with_suffix(".json.bak")
        if bak_path.exists():
            try:
                with open(bak_path, "r", encoding="utf-8") as f:
                    data = json.loads(f.read())
                logger.info(f"[DataManager] 从备份 {bak_path.name} 恢复成功")
                # 用备份覆盖损坏的文件
                shutil.copy2(str(bak_path), str(path))
                return data
            except Exception as e2:
                logger.error(f"[DataManager] 备份也无法读取: {e2}")
        logger.warning(f"[DataManager] {path.name} 无法恢复，使用空字典")
        return {}

    # ================================================================
    #  启动与关闭
    # ================================================================

    def load_all_sync(self):
        """
        启动时同步加载所有数据到内存
        在 tubei_system/__init__.py 的 on_startup 中调用
        """
        self._members = self._load_json_sync(MEMBERS_DB_PATH)
        self._spirits = self._load_json_sync(SPIRIT_DB_PATH)
        self._status = self._load_json_sync(BOT_STATUS_PATH)

        logger.info(
            f"[DataManager] 数据加载完成 | "
            f"成员: {len(self._members)} | "
            f"灵力档案: {len(self._spirits)} | "
            f"全局状态键: {list(self._status.keys())}"
        )

    def start_persist_loop(self):
        """启动定时持久化后台任务"""
        if self._persist_task is None or self._persist_task.done():
            self._persist_task = asyncio.create_task(self._persist_loop())
            logger.info(f"[DataManager] 持久化循环已启动 (间隔 {PERSIST_INTERVAL}s)")

    async def _persist_loop(self):
        """后台循环：定时检查并持久化脏数据"""
        while True:
            try:
                await asyncio.sleep(PERSIST_INTERVAL)
                await self.persist_all()
            except asyncio.CancelledError:
                # 任务被取消（关闭时），执行最后一次持久化
                await self.persist_all()
                break
            except Exception as e:
                logger.error(f"[DataManager] 持久化循环异常: {e}")

    async def shutdown(self):
        """
        关闭时调用：取消持久化任务 + 强制落盘
        在 tubei_system/__init__.py 的 on_shutdown 中调用
        """
        # 取消定时任务
        if self._persist_task and not self._persist_task.done():
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass

        # 强制落盘
        await self.persist_all()
        logger.info("[DataManager] 关闭完成，所有数据已安全落盘")

    # ================================================================
    #  原子写入与持久化
    # ================================================================

    async def _atomic_write(self, path: Path, data: dict):
        """
        原子写入 JSON 文件

        流程：
        1. 将数据写入临时文件 xxx.json.tmp
        2. 调用 fsync 确保数据落盘
        3. 将当前文件备份为 xxx.json.bak
        4. 将临时文件 rename 为目标文件（原子操作）

        这样即使在写入过程中断电：
        - 如果 rename 之前断电 → 原文件完好
        - 如果 rename 之后断电 → 新文件完好
        - 无论如何都有 .bak 备份兜底
        """
        tmp_path = path.with_suffix(".json.tmp")
        bak_path = path.with_suffix(".json.bak")

        # 1. 序列化数据
        content = json.dumps(data, ensure_ascii=False, indent=2)

        # 2. 写入临时文件
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            await f.write(content)
            await f.flush()
            os.fsync(f.fileno())

        # 3. 备份当前文件
        if path.exists():
            try:
                shutil.copy2(str(path), str(bak_path))
            except Exception as e:
                logger.warning(f"[DataManager] 备份 {path.name} 失败: {e}")

        # 4. 原子替换（在同一文件系统上，rename 是原子操作）
        os.replace(str(tmp_path), str(path))

    async def persist_all(self):
        """将所有脏数据写回磁盘"""
        async with self._lock:
            tasks = []

            if self._dirty_members:
                tasks.append(("members_db", MEMBERS_DB_PATH, self._members))
                self._dirty_members = False

            if self._dirty_spirits:
                tasks.append(("spirit_db", SPIRIT_DB_PATH, self._spirits))
                self._dirty_spirits = False

            if self._dirty_status:
                tasks.append(("bot_status", BOT_STATUS_PATH, self._status))
                self._dirty_status = False

        # 在锁外执行 I/O（减少锁持有时间）
        for name, path, data in tasks:
            try:
                await self._atomic_write(path, data)
                logger.debug(f"[DataManager] {name} 已持久化")
            except Exception as e:
                logger.error(f"[DataManager] {name} 持久化失败: {e}")
                # 重新标记为脏，下次重试
                async with self._lock:
                    if path == MEMBERS_DB_PATH:
                        self._dirty_members = True
                    elif path == SPIRIT_DB_PATH:
                        self._dirty_spirits = True
                    elif path == BOT_STATUS_PATH:
                        self._dirty_status = True

    # ================================================================
    #  成员数据 API (members_db)
    # ================================================================

    async def get_all_members(self) -> Dict[str, Any]:
        """获取全部成员数据（深拷贝）"""
        return deepcopy(self._members)

    async def get_member_info(self, qq: str) -> Optional[Dict[str, Any]]:
        """获取单个成员信息（深拷贝），不存在返回 None"""
        data = self._members.get(str(qq))
        return deepcopy(data) if data else None

    async def update_member_info(self, qq: str, data: Dict[str, Any]):
        """写入/覆盖单个成员信息"""
        async with self._lock:
            self._members[str(qq)] = data
            self._dirty_members = True

    async def delete_member(self, qq: str):
        """软删除成员（标记 status=deleted，不物理删除）"""
        async with self._lock:
            if str(qq) in self._members:
                self._members[str(qq)]["status"] = "deleted"
                self._dirty_members = True

    async def get_members_by_identity(self, identity: str) -> Dict[str, Any]:
        """
        按身份筛选成员
        :param identity: "core_member" / "outer_member" / "admin" / "decision"
        :return: 符合条件的成员字典
        """
        result = {}
        for qq, data in self._members.items():
            if data.get("status") == "deleted":
                continue
            if data.get("identity") == identity:
                result[qq] = deepcopy(data)
        return result

    async def get_active_members(self) -> Dict[str, Any]:
        """获取所有未删除的活跃成员"""
        result = {}
        for qq, data in self._members.items():
            if data.get("status") != "deleted":
                result[qq] = deepcopy(data)
        return result

    async def get_core_members(self) -> Dict[str, Any]:
        """获取所有馆内成员（core_member + admin + decision）"""
        core_identities = {"core_member", "admin", "decision"}
        result = {}
        for qq, data in self._members.items():
            if data.get("status") == "deleted":
                continue
            if data.get("identity") in core_identities:
                result[qq] = deepcopy(data)
        return result

    async def update_member_identity(self, qq: str, new_identity: str) -> bool:
        """
        更新成员身份标识
        :return: 是否发生了实际变更
        """
        async with self._lock:
            member = self._members.get(str(qq))
            if member is None:
                return False
            old_identity = member.get("identity", "guest")
            if old_identity == new_identity:
                return False
            member["identity"] = new_identity
            member["identity_updated_at"] = int(time.time())
            self._dirty_members = True
            return True

    async def update_member_last_active(self, qq: str):
        """更新成员最后活跃时间（轻量操作，不加锁，容忍竞态）"""
        member = self._members.get(str(qq))
        if member:
            member["last_active"] = int(time.time())
            self._dirty_members = True

    # ================================================================
    #  灵力数据 API (spirit_db)
    # ================================================================

    async def get_spirit_data(self, qq: str) -> Dict[str, Any]:
        """获取用户灵力数据（深拷贝），不存在返回空字典"""
        data = self._spirits.get(str(qq), {})
        return deepcopy(data)

    async def update_spirit_data(self, qq: str, updates: Dict[str, Any]):
        """
        增量更新灵力数据
        只更新 updates 中包含的字段，不影响其他字段
        """
        async with self._lock:
            user_data = self._spirits.get(str(qq), {})
            user_data.update(updates)
            self._spirits[str(qq)] = user_data
            self._dirty_spirits = True

    async def get_all_spirits(self) -> Dict[str, Any]:
        """获取全部灵力数据（深拷贝，用于批量操作如全员福利）"""
        return deepcopy(self._spirits)

    async def increment_stat(self, qq: str, stat_key: str, amount: int = 1):
        """
        增量统计字段（如 total_meditation_count += 1）
        用于官网数据统计
        """
        async with self._lock:
            user_data = self._spirits.get(str(qq), {})
            user_data[stat_key] = user_data.get(stat_key, 0) + amount
            self._spirits[str(qq)] = user_data
            self._dirty_spirits = True

    # ================================================================
    #  全局状态 API (bot_status)
    # ================================================================

    async def get_bot_status(self) -> Dict[str, Any]:
        """获取全局状态（深拷贝）"""
        return deepcopy(self._status)

    async def update_bot_status(self, updates: Dict[str, Any]):
        """增量更新全局状态"""
        async with self._lock:
            self._status.update(updates)
            self._dirty_status = True

    async def update_altar_energy(self, delta: int):
        """更新祭坛能量"""
        async with self._lock:
            current = self._status.get("altar_energy", 0)
            self._status["altar_energy"] = max(0, current + delta)
            self._dirty_status = True

    async def get_altar_energy(self) -> int:
        """获取祭坛能量（轻量读，不拷贝）"""
        return self._status.get("altar_energy", 0)

    # ================================================================
    #  兼容层（保留旧代码的调用方式）
    # ================================================================

    async def _write_json(self, path: Path, data: dict):
        """
        兼容旧代码的写入接口
        console.py 中的 persona 切换等地方会直接调用此方法
        实际上是更新内存 + 标记脏
        """
        async with self._lock:
            if path == BOT_STATUS_PATH:
                self._status = data
                self._dirty_status = True
            elif path == MEMBERS_DB_PATH:
                self._members = data
                self._dirty_members = True
            elif path == SPIRIT_DB_PATH:
                self._spirits = data
                self._dirty_spirits = True
            else:
                # 未知路径，直接原子写入文件
                await self._atomic_write(path, data)

    # ================================================================
    #  数据迁移
    # ================================================================

    async def migrate_all_gardens(self):
        """
        一次性将所有用户的药圃数据迁移为统一的 4 格 list 格式

        旧版格式（dict）：
          {"status": "mature", "plant_name": "鸾草", "water_count": 3, ...}

        新版格式（list）：
          [
            {"status": "empty", "water_count": 0, "last_water": ""},
            {"status": "empty", "water_count": 0, "last_water": ""},
            {"status": "empty", "water_count": 0, "last_water": ""},
            {"status": "empty", "water_count": 0, "last_water": ""},
          ]
        """
        migrated_count = 0

        async with self._lock:
            for uid, data in self._spirits.items():
                garden = data.get("garden")
                if garden is None:
                    # 没有药圃数据，跳过
                    continue

                needs_migration = False

                if isinstance(garden, dict):
                    # 旧版 dict → 转换为 list
                    slots = []
                    if garden.get("status", "empty") != "empty":
                        # 保留有效的种植数据
                        slot = dict(garden)
                        # 统一 last_water 字段名
                        if "last_water" not in slot:
                            slot["last_water"] = slot.pop("last_water_date", "")
                        slots.append(slot)
                    # 补齐到 4 格
                    while len(slots) < 4:
                        slots.append({
                            "status": "empty",
                            "water_count": 0,
                            "last_water": ""
                        })
                    data["garden"] = slots
                    needs_migration = True

                elif isinstance(garden, list):
                    # 已经是 list，检查是否需要补齐或修复
                    while len(garden) < 4:
                        garden.append({
                            "status": "empty",
                            "water_count": 0,
                            "last_water": ""
                        })
                        needs_migration = True

                    for slot in garden:
                        if "last_water" not in slot:
                            slot["last_water"] = slot.pop("last_water_date", "")
                            needs_migration = True

                if needs_migration:
                    migrated_count += 1

            if migrated_count > 0:
                self._dirty_spirits = True
                logger.info(
                    f"[DataManager] 药圃数据迁移完成，"
                    f"修正 {migrated_count} 位用户的数据格式"
                )

    async def migrate_member_identities(self, core_group_ids: set):
        """
        启动时为所有成员补充 identity 字段

        规则：
        - 如果已有 identity 字段 → 不覆盖
        - 如果 register_group 在核心群列表中 → core_member
        - 否则 → outer_member
        - 决策组/管理组成员的 identity 在 identity.py 中单独处理
        """
        updated_count = 0

        async with self._lock:
            for qq, data in self._members.items():
                if data.get("status") == "deleted":
                    continue

                if "identity" not in data:
                    reg_group = data.get("register_group", 0)
                    if reg_group in core_group_ids:
                        data["identity"] = "core_member"
                    else:
                        # 旧数据没有 register_group，默认视为馆内
                        data["identity"] = "core_member"
                    updated_count += 1

            if updated_count > 0:
                self._dirty_members = True
                logger.info(
                    f"[DataManager] 成员身份迁移完成，"
                    f"补充 {updated_count} 位成员的 identity 字段"
                )

    # ================================================================
    #  官网数据导出
    # ================================================================

    async def export_for_web(self, core_only: bool = True) -> Dict[str, Any]:
        """
        导出官网所需的标准化数据包

        :param core_only: 是否只导出馆内成员
        :return: 可直接 JSON 序列化的数据包
        """
        if core_only:
            members = await self.get_core_members()
        else:
            members = await self.get_active_members()

        # 组装导出数据
        export_members = []
        for qq, member in members.items():
            spirit = self._spirits.get(qq, {})

            # 检查是否允许公开展示
            if not member.get("public_visible", True):
                continue

            export_members.append({
                "qq": qq,
                "spirit_name": member.get("spirit_name", ""),
                "nickname": member.get("nickname", ""),
                "intro": member.get("intro", ""),
                "identity": member.get("identity", "guest"),
                "register_time": member.get("register_time", 0),
                "oc_details": member.get("oc_details", {}),
                "level": spirit.get("level", 1),
                "sp": spirit.get("sp", 0),
                "achievements": spirit.get("achievements", []),
                "total_meditation_count": spirit.get("total_meditation_count", 0),
                "total_sp_earned": spirit.get("total_sp_earned", 0),
                "join_date": spirit.get("join_date", ""),
                "title_history": spirit.get("title_history", []),
            })

        return {
            "version": "3.0",
            "exported_at": datetime.now().isoformat(),
            "member_count": len(export_members),
            "members": export_members,
            "altar_energy": self._status.get("altar_energy", 0),
        }

    # ================================================================
    #  内部数据直接访问（仅限系统模块使用）
    # ================================================================

    @property
    def members_raw(self) -> Dict[str, Any]:
        """直接访问内存中的成员数据（不拷贝，仅限只读场景）"""
        return self._members

    @property
    def spirits_raw(self) -> Dict[str, Any]:
        """直接访问内存中的灵力数据（不拷贝，仅限只读场景）"""
        return self._spirits

    @property
    def status_raw(self) -> Dict[str, Any]:
        """直接访问内存中的状态数据（不拷贝，仅限只读场景）"""
        return self._status


# ==================== 全局单例 ====================
data_manager = DataManager.get_instance()