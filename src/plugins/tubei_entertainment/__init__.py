"""
晋宁会馆·秃贝五边形 4.1
趣味娱乐系统

包含：
  kitchen        - 无限大人的厨房 · 生存挑战
  resonance      - 灵力宿命（灵伴）+ 灵质鉴定
  duel           - 灵质空间 · 演武场
  heixiu_catcher - 嘿咻捕获计划
  truth_dare     - 真心话大冒险
"""

from nonebot import get_driver
from nonebot.plugin import PluginMetadata

from . import kitchen
from . import resonance
from . import duel
from . import heixiu_catcher
from . import truth_dare

__plugin_meta__ = PluginMetadata(
    name="秃贝娱乐系统",
    description="厨房/灵伴/鉴定/切磋/嘿咻/真心话",
    usage="/厨房, /灵伴, /鉴定, /切磋, /真心话, /大冒险",
)

driver = get_driver()


@driver.on_startup
async def _():
    print("  ✅ [Tubei Entertainment] 娱乐场所已开放")