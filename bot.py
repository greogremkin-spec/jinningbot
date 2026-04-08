"""
晋宁会馆·秃贝五边形 4.1
程序入口

插件加载顺序很重要：
  1. apscheduler  → 定时任务支持
  2. tubei_system → 系统底座（数据加载、拦截器、配置）
  3. tubei_admin  → 行政管理
  4. tubei_cultivation → 修行系统
  5. tubei_entertainment → 娱乐系统
  6. tubei_guide  → 引导系统（菜单）
  7. tubei_chat   → AI 核心（priority=99，最后兜底）
"""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter

# 初始化 NoneBot
nonebot.init()

# 注册协议适配器
driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)

# 加载定时任务插件
nonebot.load_plugin("nonebot_plugin_apscheduler")

# 加载秃贝六大模块（顺序重要）
nonebot.load_plugin("src.plugins.tubei_system")        # 系统底座
nonebot.load_plugin("src.plugins.tubei_admin")          # 行政管理
nonebot.load_plugin("src.plugins.tubei_cultivation")    # 修行系统
nonebot.load_plugin("src.plugins.tubei_entertainment")  # 娱乐系统
nonebot.load_plugin("src.plugins.tubei_guide")          # 引导系统
nonebot.load_plugin("src.plugins.tubei_chat")           # AI 核心（最后加载）

if __name__ == "__main__":
    nonebot.run()