"""
晋宁会馆·秃贝五边形 4.1
灵质修行系统

包含子模块：
  meditation   - 聚灵台（聚灵修行 + 每日灵签 + 个人档案）
  expedition   - 灵风传送（妖灵派遣 + 强制召回 + 自动结算）
  garden       - 妖灵药圃（查看 + 播种 + 灌溉 + 收获）
  altar        - 木头的催更祭坛
  items        - 灵质空间（储物袋 + 道具使用 + 法宝熔炼）
  achievement  - 成就系统 2.0（成就展柜 + 称号佩戴）
  ranking      - 排行榜系统（灵力/嘿咻/聚灵/厨房/派遣）
"""

from nonebot import get_driver
from nonebot.plugin import PluginMetadata

# 导入所有子模块
from . import meditation
from . import expedition
from . import garden
from . import altar
from . import items
from . import achievement
from . import ranking

__plugin_meta__ = PluginMetadata(
    name="灵质修行系统",
    description="聚灵/灵签/档案/派遣/药圃/祭坛/背包/熔炼/成就/称号/排行榜",
    usage="/聚灵, /求签, /档案, /派遣, /药圃, /祭坛, /背包, /熔炼, /成就, /称号, /排行榜",
)

driver = get_driver()


@driver.on_startup
async def _():
    from src.plugins.tubei_system.config import game_config

    locations_count = len(game_config.expedition_locations)
    plants_count = len(game_config.garden_plants)
    achievements_count = len(game_config.get("achievements", default={}))

    print("  ✅ [Tubei Cultivation] 修行模块加载完毕")
    print(f"     📍 派遣灵域: {locations_count} 个")
    print(f"     🌿 可种灵植: {plants_count} 种")
    print(f"     🏆 成就定义: {achievements_count} 条")
    print(f"     📊 排行榜: 5 种子榜")