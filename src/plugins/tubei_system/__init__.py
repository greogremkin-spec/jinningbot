"""
晋宁会馆·秃贝五边形 4.1
系统门神模块

启动流程：
1. 加载所有数据到内存
2. 执行数据迁移（药圃格式统一、身份字段补充）
3. 启动定时持久化循环

关闭流程：
1. 取消持久化循环
2. 强制将所有脏数据写回磁盘

包含子模块：
config         - 配置中心（系统配置 + 游戏数值）
interceptor    - 消息拦截器（群分级 + 防刷屏 + 身份感知）
mutex          - 互斥锁（防冲突操作）
recorder       - 灵质纪事记录器
reporter       - 每日运行报告
console        - 管理员控制台
world_event    - 世界事件系统
text_dispatcher - 纯文字指令分发器（4.0新增）
"""

from nonebot import get_driver
from nonebot.plugin import PluginMetadata
from .config import TUBEI_VERSION, TUBEI_FULL_NAME

# 导入所有子模块
from . import config
from . import interceptor
from . import recorder
from . import reporter
from . import console
from . import world_event
from . import text_dispatcher

from src.common.data_manager import data_manager
from src.common.group_manager import group_manager

__plugin_meta__ = PluginMetadata(
    name="秃贝系统门神",
    description="配置中心/消息拦截/事件记录/每日报告/管理控制台/世界事件/纯文字分发",
    usage="全局生效",
    config=config.SystemConfig,
)

driver = get_driver()


@driver.on_startup
async def startup():
    """系统启动初始化"""
    # 1. 加载所有数据到内存
    data_manager.load_all_sync()

    # 2. 数据迁移：药圃格式统一（dict → list）
    await data_manager.migrate_all_gardens()

    # 3. 数据迁移：补充成员 identity 字段
    await data_manager.migrate_member_identities(
        core_group_ids=group_manager.core_group_ids
    )

    # 4. 启动定时持久化循环（每 30 秒检查脏数据并写盘）
    data_manager.start_persist_loop()

    # 5. 启动完成日志
    member_count = len(data_manager.members_raw)
    spirit_count = len(data_manager.spirits_raw)
    core_count = len([
        m for m in data_manager.members_raw.values()
        if m.get("identity") in ("core_member", "admin", "decision")
        and m.get("status") != "deleted"
    ])
    outer_count = len([
        m for m in data_manager.members_raw.values()
        if m.get("identity") == "outer_member"
        and m.get("status") != "deleted"
    ])
    core_groups = len(group_manager.core_group_ids)
    allied_groups = len(group_manager._allied_group_ids)

    # 统计纯文字指令数量
    from src.common.command_registry import COMMANDS
    text_cmd_count = sum(1 for c in COMMANDS if c.get("text"))

    print("=" * 60)
    print(f"  [Tubei System] {TUBEI_FULL_NAME} · 灵力结界已展开")
    print("=" * 60)
    print(f"  📦 成员档案: {member_count} 条 (馆内{core_count} / 馆外{outer_count})")
    print(f"  📦 灵力档案: {spirit_count} 条")
    print(f"  🏘  核心群: {core_groups} 个")
    print(f"  🤝 联盟群: {allied_groups} 个")
    print(f"  🌐 群模式: 三级分类 (core/allied/public)")
    print(f"  ⏱  持久化间隔: 30s (原子写入)")
    print(f"  🌍 世界事件: 灵潮爆发 / 嘿咻暴动 / 无限失控")
    print(f"  🏆 成就系统: {len(config.game_config.get('achievements', default={}))} 条定义")
    print(f"  ⛩  祭坛能量: {data_manager.status_raw.get('altar_energy', 0)} / 1000")
    print(f"  🎭 当前人格: {data_manager.status_raw.get('persona', 'normal')}")
    print(f"  📝 纯文字指令: {text_cmd_count} 个")
    print("=" * 60)


@driver.on_shutdown
async def shutdown():
    """系统关闭：安全保存所有数据"""
    await data_manager.shutdown()
    print("=" * 60)
    print("  [Tubei System] 数据已安全落盘，灵力结界关闭")
    print("=" * 60)