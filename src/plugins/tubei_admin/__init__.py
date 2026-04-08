"""
晋宁会馆·秃贝五边形 4.1
行政管理系统

包含：
  registry - 在馆人员登记（区分馆内/馆外）
  manager  - 名录管理（查看/修改/发放/除名）
"""

from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from . import registry
from . import manager

__plugin_meta__ = PluginMetadata(
    name="秃贝行政系统",
    description="档案登记与名录管理",
    usage="/登记, /档案, /查看名录, /查看名单",
)

driver = get_driver()


@driver.on_startup
async def _():
    print("  ✅ [Tubei Admin] 档案室已开启")