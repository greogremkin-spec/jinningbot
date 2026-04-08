"""
晋宁会馆·秃贝五边形 4.1
统一指令注册中心

所有指令的元数据定义。
菜单和说明从这里自动生成。
加指令只需在此文件中添加条目。

设计原则：
  - slash 列表第一个 = 菜单中展示的 /指令
  - text  列表第一个 = 菜单中展示的 纯文字指令
  - text  为空 = 该指令不支持纯文字触发
  - handler_id = 用于 text_dispatcher 路由到对应的处理函数
  - section = 所属板块（admin/cultivation/entertainment）
  - hidden = True 表示不在菜单中显示（彩蛋类）
"""

from typing import List, Optional, Dict, Any


# ================================================================
# 板块定义
# ================================================================

MENU_SECTIONS = {
    "admin": {
        "name": "行政板块",
        "icon": "📋",
        "title": "灵册大厅 · 在馆人员登记与档案管理",
        "subtitle": "建立你的灵力档案，成为在册妖灵。",
        "slash_trigger": "行政板块",
        "text_trigger": "行政板块",
        "display_in_public": False,
    },
    "cultivation": {
        "name": "修行板块",
        "icon": "🧘",
        "title": "灵质修行 · 聚灵派遣药圃道具祭坛",
        "subtitle": "聚集天地灵气，探索九大灵域，培育灵植，熔炼法宝。",
        "slash_trigger": "修行板块",
        "text_trigger": "修行板块",
        "display_in_public": False,
    },
    "entertainment": {
        "name": "娱乐板块",
        "icon": "🎮",
        "title": "趣味玩法 · 厨房鉴定切磋嘿咻灵伴",
        "subtitle": "无限厨房、鉴定、切磋、捕捉嘿咻、寻找今日灵伴！",
        "slash_trigger": "娱乐板块",
        "text_trigger": "娱乐板块",
        "display_in_public": True,
    },
        "console": {
        "name": "管理板块",
        "icon": "⚙",
        "title": "管理控制台 · 决策组/管理组专用",
        "subtitle": "人格切换、广播、封印、福利发放、配置管理。",
        "slash_trigger": "管理板块",
        "text_trigger": "管理板块",
        "display_in_public": False,
    },
}


# ================================================================
# 指令定义
# ================================================================

COMMANDS: List[Dict[str, Any]] = [

    # ==================== 📋 行政 ====================

    {
        "id": "register_guide",
        "slash": ["登记", "在馆登记"],
        "text": ["登记", "在馆登记"],
        "help_keywords": ["登记", "在馆登记", "灵册大厅"],
        "section": "admin",
        "display_name": "在馆登记",
        "description": "录入灵力档案，成为在册妖灵",
        "min_tier": "allied",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "📋 【灵册大厅 · 在馆人员登记】\n"
            "• 发送 登记 获取登记模板\n"
            "• 复制模板填写后发送即可\n"
            "• 登记后解锁全部修行功能\n"
            "• 建议私聊发送（保护隐私）\n"
            "─────────────────\n"
            "👉 登记"
        ),
    },
    {
        "id": "register_submit",
        "slash": ["在馆人员登记"],
        "text": [],
        "section": "admin",
        "display_name": "提交登记",
        "description": "提交填写好的登记表单",
        "min_tier": "allied",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "profile",
        "slash": ["档案", "我的档案", "个人信息", "妖灵档案", "个人档案"],
        "text": ["我的档案", "档案", "妖灵档案", "个人档案"],
        "help_keywords": ["档案", "我的档案", "个人档案"],
        "section": "admin",
        "display_name": "妖灵档案",
        "description": "查看个人修行面板",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "📋 【灵册大厅 · 妖灵档案】\n"
            "• 发送 档案 查看个人修行面板\n"
            "• 包含：境界、灵力、背包、成就、状态等\n"
            "• 佩戴称号会显示在名字旁边\n"
            "─────────────────\n"
            "👉 档案"
        ),
    },
    {
        "id": "member_list",
        "slash": ["查看名单", "名单"],
        "text": ["查看名单"],
        "section": "admin",
        "display_name": "查看名单",
        "description": "查看全部在册人员",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": True,
        "core_only": False,
        "hidden": False,
        "help_detail": None,
    },
    {
        "id": "modify",
        "slash": ["修改", "改数值"],
        "text": [],
        "section": "admin",
        "display_name": "修改数值",
        "description": "修改指定成员的属性",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": True,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "give",
        "slash": ["发放", "发东西"],
        "text": [],
        "section": "admin",
        "display_name": "发放物品",
        "description": "给指定成员发放道具",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": True,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "delete_member",
        "slash": ["删除名单", "除名"],
        "text": [],
        "section": "admin",
        "display_name": "除名",
        "description": "将成员从名单中移除",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": True,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },

    # ==================== 🧘 修行 ====================

    {
        "id": "meditate",
        "slash": ["聚灵", "聚灵修行"],
        "text": ["聚灵", "聚灵修行"],
        "help_keywords": ["聚灵", "聚灵修行", "灵质修行",  "聚灵台"],
        "section": "cultivation",
        "display_name": "聚灵台 · 灵质修行",
        "description": "汲取天地灵气，每日修行",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🧘 【聚灵台 · 灵质修行】\n"
            "• 每日可执行 1 次\n"
            "• 收益 = (基础 + 等级加成 + 永久加成) × (1 + 运势 + 道具)\n"
            "• 灵潮爆发时额外 +30%\n"
            "• 祭坛税收：自动上缴 1%\n"
            "• 未登记者灵力上限 99\n"
            "─────────────────\n"
            "👉 聚灵"
        ),
    },
    {
        "id": "fortune",
        "slash": ["求签", "每日灵签"],
        "text": ["求签", "每日灵签", "灵签"],
        "help_keywords": ["求签", "灵签", "每日灵签"],
        "section": "cultivation",
        "display_name": "每日灵签",
        "description": "今日运势宜忌",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🎴 【聚灵台 · 每日灵签】\n"
            "• 每日一次，测测今日运势\n"
            "• 运势影响聚灵收益\n"
            "• 大吉+50% 中吉+20% 小吉+10% 平±0 末凶-10%\n"
            "─────────────────\n"
            "👉 求签"
        ),
    },
    {
        "id": "expedition",
        "slash": ["派遣", "妖灵派遣", "灵风传送"],
        "text": ["派遣", "妖灵派遣", "灵风传送"],
        "help_keywords": ["派遣", "妖灵派遣", "灵风传送", "探索", "灵域"],
        "section": "cultivation",
        "display_name": "灵风传送 · 妖灵派遣",
        "description": "探索九大灵域",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "has_args": True,
        "help_detail": (
            "🚀 【灵风传送 · 妖灵派遣】\n"
            "• 派遣 查看九大灵域\n"
            "• 派遣 [地点名] 出发\n"
            "• Lv.2 区域 3 个 | Lv.4 区域 3 个 | Lv.6 区域 3 个\n"
            "• 派遣期间无法聚灵\n"
            "• 探索全部 9 区域可解锁成就\n"
            "• 🔑 析沐的钥匙可提前解锁高阶区域\n"
            "─────────────────\n"
            "👉 派遣"
        ),
    },
    {
        "id": "recall",
        "slash": ["召回", "强制召回"],
        "text": ["召回", "强制召回"],
        "section": "cultivation",
        "display_name": "强制召回",
        "description": "中止探索，召回灵体",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": None,
    },
    {
        "id": "garden",
        "slash": ["药圃", "我的药圃", "妖灵药圃", "灵植小院"],
        "text": ["药圃", "我的药圃", "妖灵药圃", "灵植小院"],
        "help_keywords": ["药圃", "我的药圃", "妖灵药圃", "灵植小院"],
        "section": "cultivation",
        "display_name": "妖灵药圃 · 灵植小院",
        "description": "四块灵田，播种灌溉收获",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🌿 【妖灵药圃 · 灵植小院】\n"
            "• 4 块灵田，独立种植\n"
            "• 流程：播种→灌溉(日限1次)→收获\n"
            "• 种子→嫩芽(1水)→生长(2水)→成熟(5水)\n"
            "• 产出：灵心草、蓝玉果等强力道具\n"
            "• 💧 露水凝珠：灌溉时自动消耗，效果翻倍\n"
            "─────────────────\n"
            "👉 药圃"
        ),
    },
    {
        "id": "sow",
        "slash": ["播种"],
        "text": ["播种"],
        "section": "cultivation",
        "display_name": "播种",
        "description": "消耗种子种下灵植",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "water",
        "slash": ["灌溉", "浇水"],
        "text": ["灌溉", "浇水"],
        "section": "cultivation",
        "display_name": "灌溉",
        "description": "为灵植浇灌灵泉",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "harvest",
        "slash": ["收获"],
        "text": ["收获"],
        "section": "cultivation",
        "display_name": "收获",
        "description": "采摘成熟灵植",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "bag",
        "slash": ["储物袋", "背包", "我的背包"],
        "text": ["储物袋", "背包", "我的背包"],
        "section": "cultivation",
        "display_name": "灵质空间 · 储物袋",
        "description": "查看道具一览",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": None,
    },
    {
        "id": "use_item",
        "slash": ["使用"],
        "text": ["使用"],
        "section": "cultivation",
        "display_name": "使用道具",
        "description": "使用背包中的道具",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "has_args": True,
        "help_detail": None,
    },
    {
        "id": "smelt",
        "slash": ["熔炼", "法宝熔炼"],
        "text": ["熔炼", "法宝熔炼"],
        "help_keywords": ["熔炼", "法宝熔炼",  "君阁工坊"],
        "section": "cultivation",
        "display_name": "君阁工坊 · 法宝熔炼",
        "description": "法宝碎片重铸",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🔥 【君阁工坊 · 法宝熔炼】\n"
            "• 消耗法宝碎片 x10\n"
            "• 45% 普通 | 35% 稀有 | 15% 传说 | 5% 彩蛋\n"
            "• 💎 虚空结晶：自动消耗，品质升一档\n"
            "• 🪶 吉兆加持：品质额外升一档\n"
            "─────────────────\n"
            "👉 熔炼"
        ),
    },
    {
        "id": "lore",
        "slash": ["图鉴", "道具图鉴"],
        "text": ["图鉴", "道具图鉴"],
        "help_keywords": ["图鉴", "道具图鉴", "道具说明"],
        "section": "cultivation",
        "display_name": "道具图鉴",
        "description": "查看道具碎碎念描述",
        "min_tier": "allied",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "has_args": True,
        "help_detail": (
            "📖 【道具图鉴 · 碎碎念】\n"
            "• 图鉴 查看所有道具分类\n"
            "• 图鉴 [道具名] 查看碎碎念描述\n"
            "─────────────────\n"
            "👉 图鉴 灵心草"
        ),
    },
    {
        "id": "unlock",
        "slash": ["解锁", "解锁灵域"],
        "text": ["解锁"],
        "section": "cultivation",
        "display_name": "灵域解锁",
        "description": "使用析沐的钥匙解锁灵域",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "has_args": True,
        "help_detail": None,
    },
    {
        "id": "altar",
        "slash": ["祭坛", "催更祭坛"],
        "text": ["催更祭坛", "祭坛"],
        "help_keywords": ["祭坛", "催更祭坛", "催更", "木头的催更祭坛"],
        "section": "cultivation",
        "display_name": "木头的催更祭坛",
        "description": "汇集了全部小妖的催更怨气",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": True,
        "hidden": False,
        "help_detail": (
            "⛩ 【木头的催更祭坛】\n"
            "• 每次聚灵自动上缴 1% 灵力\n"
            "• 能量满 1000 时触发全服加成\n"
            "• 馆内专属功能\n"
            "─────────────────\n"
            "👉 祭坛"
        ),
    },
    {
        "id": "achievement",
        "slash": ["成就", "我的成就"],
        "text": ["我的成就", "成就系统"],
        "help_keywords": ["成就", "我的成就", "成就系统"],
        "section": "cultivation",
        "display_name": "会馆成就系统",
        "description": "查看已解锁的成就",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🏆 【成就系统】\n"
            "• 通过修行/探索/战斗解锁成就\n"
            "• 分为：⭐普通 💎稀有 🌟史诗 🏆传说\n"
            "• 部分成就解锁专属称号\n"
            "─────────────────\n"
            "👉 我的成就"
        ),
    },
    {
        "id": "title",
        "slash": ["称号", "我的称号"],
        "text": ["我的称号", "称号系统"],
        "help_keywords": ["称号", "我的称号", "称号系统"],
        "section": "cultivation",
        "display_name": "称号系统",
        "description": "佩戴解锁的称号",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "has_args": True,
        "help_detail": None,
    },
    {
        "id": "ranking",
        "slash": ["排行榜", "排行", "榜单",
                "灵力排行榜", "灵力榜",
                "嘿咻排行榜", "嘿咻榜",
                "聚灵排行榜", "聚灵榜",
                "厨房排行榜", "厨房榜",
                "派遣排行榜", "派遣榜"],
        "text": ["排行榜",
                "灵力排行榜", "灵力榜",
                "嘿咻排行榜", "嘿咻榜",
                "聚灵排行榜", "聚灵榜",
                "厨房排行榜", "厨房榜",
                "派遣排行榜", "派遣榜"],
        "section": "cultivation",
        "display_name": "会馆排行榜",
        "description": "灵力/嘿咻/聚灵/厨房/派遣多榜",
        "min_tier": "allied",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "has_args": True,
        "help_keywords": ["排行榜", "排行", "榜单",
                        "灵力排行榜", "灵力榜",
                        "嘿咻排行榜", "嘿咻榜",
                        "聚灵排行榜", "聚灵榜",
                        "厨房排行榜", "厨房榜",
                        "派遣排行榜", "派遣榜"],
        "help_detail": (
            "🏆 【会馆排行榜系统】\n"
            "五大排行榜，直接发送即可：\n\n"
            "  🏆 灵力排行榜（灵力榜）\n"
            "  🐾 嘿咻排行榜（嘿咻榜）\n"
            "  🧘 聚灵排行榜（聚灵榜）\n"
            "  🍽 厨房排行榜（厨房榜）\n"
            "  🚩 派遣排行榜（派遣榜）\n\n"
            "也可以：排行榜 嘿咻\n"
            "─────────────────\n"
            "💡 灵力排行榜"
        ),
    },
    {
        "id": "world_event",
        "slash": ["世界事件", "事件", "灵潮"],
        "text": ["世界事件"],
        "section": "cultivation",
        "display_name": "世界事件",
        "description": "查看当前活跃事件",
        "min_tier": "allied",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🌍 【世界事件系统】\n"
            "• ⚡ 灵潮爆发：聚灵+30%，持续2小时\n"
            "• 🐾 嘿咻暴动：每30分钟刷嘿咻，持续2小时\n"
            "• 🔥 无限失控：厨房全美味，持续1小时\n"
            "• 每日随机触发\n"
            "─────────────────\n"
            "👉 世界事件"
        ),
    },

    # ==================== 🎮 娱乐 ====================

    {
        "id": "kitchen",
        "slash": ["厨房", "厨房挑战", "厨房生存", "厨房生存战"],
        "text": ["厨房", "厨房挑战", "厨房生存", "厨房生存战"],
        "help_keywords": ["厨房", "厨房挑战", "厨房生存", "无限大人的厨房"],
        "section": "entertainment",
        "display_name": "无限大人的厨房生存战",
        "description": "赌上味蕾的一餐",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🍳 【无限大人的厨房生存战】\n"
            "• 开放时间：06-09, 11-14, 16-21, 22-01\n"
            "• 30% 绝世珍馐 (+50灵力)\n"
            "• 70% 黑暗料理 (-10灵力, 味蕾丧失)\n"
            "• 连吃 3 次黑暗，下次必出美味\n"
            "• 每日限 4 次\n"
            "─────────────────\n"
            "👉 厨房挑战"
        ),
    },
    {
        "id": "appraise",
        "slash": ["鉴定", "灵质鉴定"],
        "text": ["鉴定", "灵质鉴定"],
        "help_keywords": ["鉴定", "灵质鉴定", "灵力鉴定", "灵力检测"],
        "section": "entertainment",
        "display_name": "灵质鉴定",
        "description": "检测灵力纯度与隐藏属性",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🔍 【灵质鉴定 · 隐藏属性】\n"
            "• 消耗 2 灵力\n"
            "• 随机灵力纯度与属性词条\n"
            "• 5% 概率出稀有词条\n"
            "• 持有[鸾草]必出华丽词条\n"
            "─────────────────\n"
            "👉 鉴定"
        ),
    },
    {
        "id": "duel",
        "slash": ["切磋", "灵力切磋", "PK", "领域较量"],
        "text": ["切磋"],
        "help_keywords": ["切磋", "PK", "灵力切磋", "演武场", "领域较量", "斗帅宫"],
        "section": "entertainment",
        "display_name": "灵质空间 · 演武场",
        "description": "与其他妖灵灵力比拼",
        "min_tier": "allied",
        "require_registered": True,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "has_args": True,
        "help_detail": (
            "⚔ 【灵质空间 · 演武场】\n"
            "• 切磋 @某人 进行灵力比拼\n"
            "• 灵力波动 ±20%\n"
            "• 胜者吸取对方 1% 灵力(上限20)\n"
            "• 败者无损失\n"
            "─────────────────\n"
            "👉 切磋 @某人"
        ),
    },
    {
        "id": "heixiu_catch",
        "slash": ["捕捉", "捕捉嘿咻"],
        "text": ["捕捉", "捕捉嘿咻"],
        "section": "entertainment",
        "display_name": "嘿咻捕获计划",
        "description": "野生嘿咻出没时发送捕捉",
        "min_tier": "allied",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
           "🐾 【嘿咻捕获计划】\n"
        "• 系统随机刷出嘿咻，先到先得\n"
        "• 捕捉成功率：80%\n"
        "• 失败则嘿咻逃跑，本轮结束\n"
        "• 成功后有概率揭晓稀有品种：\n"
        "　 85% 普通 | 8% 🌈彩虹 | 5% ⭐黄金 | 2% 🌑暗影\n"
        "• 凌晨 1-5 点馆禁期间不刷新\n"
        "• 收集 10 只解锁 [嘿咻牧场主]\n"
        "─────────────────\n"
        "💡 嘿咻出现时发送 捕捉"
        ),
    },
    {
        "id": "truth",
        "slash": ["真心话"],
        "text": [],
        "section": "entertainment",
        "display_name": "真心话",
        "description": "灵力诚实探测",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": None,
    },
    {
        "id": "dare",
        "slash": ["大冒险"],
        "text": [],
        "section": "entertainment",
        "display_name": "大冒险",
        "description": "灵压勇气挑战",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": None,
    },
    {
        "id": "soulmate",
        "slash": ["灵伴", "今日灵伴"],
        "text": ["今日灵伴"],
        "section": "entertainment",
        "display_name": "今日灵伴",
        "description": "每日灵力共鸣匹配",
        "min_tier": "allied",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "help_detail": (
            "🔮 【灵力宿命 · 今日灵伴】\n"
            "• 发送 今日灵伴 匹配今日灵伴\n"
            "• 从当前群全体成员中匹配\n"
            "• 双向锁定，每日刷新\n"
            "• 双方登记 → 完整共鸣加成\n"
            "• 仅自己登记 → 微弱共鸣（半额）\n"
            "• 每日首次触发给加成\n"
            "─────────────────\n"
            "👉 今日灵伴"
        ),
    },

    # ===== 隐藏彩蛋（不在菜单显示） =====
    {
        "id": "waifu",
        "slash": ["今日老婆",],
        "text": ["今日老婆"],
        "section": "entertainment",
        "display_name": "今日老婆",
        "description": "致敬萝卜前辈",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "quit_easter_egg",
        "slash": [],
        "text": ["退出此群"],
        "section": "entertainment",
        "display_name": "退出彩蛋",
        "description": "致敬萝卜",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },

    # ==================== 📖 引导类 ====================

    {
        "id": "menu",
        "slash": ["菜单"],
        "text": ["菜单"],
        "section": "_guide",
        "display_name": "功能菜单",
        "description": "查看所有功能",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "view_commands",
        "slash": ["指令", "查看指令", "所有指令"],
        "text": ["查看指令", "所有指令"],
        "section": "_guide",
        "display_name": "查看指令",
        "description": "查看所有可用指令",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "admin_commands",
        "slash": ["管理员指令", "管理指令"],
        "text": ["管理员指令", "管理指令"],
        "section": "_guide",
        "display_name": "管理员指令",
        "description": "查看管理组/决策组专属指令",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
        "help_keywords": ["管理员指令", "管理指令"],
    },
    {
        "id": "help",
        "slash": ["说明", "规则"],
        "text": ["说明"],
        "section": "_guide",
        "display_name": "功能说明",
        "description": "查看详细规则",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "has_args": True,
        "help_detail": None,
    },
    {
        "id": "manual",
        "slash": ["使用手册", "用户手册", "用户使用手册", "新手指南"],
        "text": ["使用手册", "用户手册", "用户使用手册", "新手指南"],
        "section": "_guide",
        "display_name": "使用手册",
        "description": "获取完整使用手册文件",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
        "help_keywords": ["使用手册", "手册", "帮助", "新手"],
    },
    {
        "id": "about",
        "slash": ["关于"],
        "text": [],
        "section": "_guide",
        "display_name": "关于会馆",
        "description": "会馆缘起与愿景",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
    {
        "id": "join_guide",
        "slash": [],
        "text": ["加入会馆", "加入晋宁", "加入晋宁会馆"],
        "section": "_guide",
        "display_name": "加入引导",
        "description": "如何加入晋宁会馆",
        "min_tier": "public",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": True,
        "help_detail": None,
    },
        # ==================== 管理控制台 ====================
    {
        "id": "persona",
        "slash": ["切换人格", "变身", "切换模式"],
        "text": [],
        "section": "console",
        "display_name": "人格切换",
        "description": "切换秃贝的性格模式",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "decision_only": True,
        "help_detail": (
            "⚙ 【人格切换】\n"
            "• /切换人格 查看可用模式\n"
            "• /切换人格 [代码] 切换\n"
            "• 模式：normal/middle_school/cold/secretary/overload\n"
            "─────────────────\n"
            "💡 /切换人格"
        ),
        "help_keywords": ["人格", "切换人格", "变身", "模式"],
    },
    {
        "id": "system_status",
        "slash": ["系统状态", "查看状态"],
        "text": [],
        "section": "console",
        "display_name": "系统状态",
        "description": "查看系统运行数据",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "decision_only": True,
        "help_detail": None,
        "help_keywords": ["系统状态", "状态"],
    },
    {
        "id": "broadcast",
        "slash": ["全员广播", "广播", "公告"],
        "text": [],
        "section": "console",
        "display_name": "全员广播",
        "description": "向所有核心群发送公告",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "decision_only": True,
        "help_detail": None,
        "help_keywords": ["广播", "公告"],
    },
    {
        "id": "ban",
        "slash": ["封印", "关小黑屋"],
        "text": [],
        "section": "console",
        "display_name": "封印",
        "description": "封禁指定用户的灵力回路",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "decision_only": True,
        "help_detail": None,
        "help_keywords": ["封印", "封禁", "小黑屋"],
    },
    {
        "id": "gift_all",
        "slash": ["全员福利", "发红包"],
        "text": [],
        "section": "console",
        "display_name": "全员福利",
        "description": "向全体成员发放灵力或道具",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "decision_only": True,
        "help_detail": (
            "⚙ 【全员福利】\n"
            "• /全员福利 sp 100 → 全员+100灵力\n"
            "• /全员福利 item 神秘种子 3 → 全员+3种子\n"
            "─────────────────\n"
            "💡 /全员福利 sp [数量]"
        ),
        "help_keywords": ["福利", "发红包", "全员福利"],
    },
    {
        "id": "reload_config",
        "slash": ["重载配置", "刷新配置", "reload"],
        "text": [],
        "section": "console",
        "display_name": "重载配置",
        "description": "热重载文案和数值配置",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "decision_only": True,
        "help_detail": None,
        "help_keywords": ["重载", "刷新配置", "reload"],
    },
    {
        "id": "force_save",
        "slash": ["强制保存", "保存数据", "save"],
        "text": [],
        "section": "console",
        "display_name": "强制保存",
        "description": "立即将内存数据写入磁盘",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "decision_only": True,
        "help_detail": None,
        "help_keywords": ["保存", "save"],
    },
    {
        "id": "promo_toggle",
        "slash": ["宣传开关"],
        "text": [],
        "section": "console",
        "display_name": "宣传开关",
        "description": "开启或关闭宣传功能",
        "min_tier": "core",
        "require_registered": False,
        "admin_only": False,
        "core_only": False,
        "hidden": False,
        "decision_only": True,
        "help_detail": None,
        "help_keywords": ["宣传"],
    },
]


# ================================================================
# 工具函数
# ================================================================

def get_commands_by_section(section: str) -> list:
    """获取某个板块下的所有非隐藏指令"""
    return [c for c in COMMANDS if c["section"] == section and not c.get("hidden", False)]


def get_all_text_triggers() -> dict:
    """
    构建纯文字触发词 → 指令ID的映射表
    用于 text_dispatcher 快速查找

    返回: {"今日灵伴": "soulmate", "聚灵": "meditate", ...}

    注意：带参数的指令（如"使用 天明珠"）需要特殊处理，
    这里只注册不带参数的精确匹配词。
    带参数的指令由 text_dispatcher 通过前缀匹配处理。
    """
    mapping = {}
    for cmd in COMMANDS:
        for t in cmd.get("text", []):
            mapping[t] = cmd["id"]
    return mapping


def get_text_prefix_triggers() -> dict:
    """
    构建带参数的纯文字指令的前缀映射

    返回: {"使用": "use_item", "派遣": "expedition", ...}
    """
    result = {}
    for cmd in COMMANDS:
        if cmd.get("has_args") and cmd.get("text"):
            for t in cmd["text"]:
                result[t] = cmd["id"]
    return result


def get_command_by_id(cmd_id: str) -> Optional[dict]:
    """根据ID获取指令定义"""
    for cmd in COMMANDS:
        if cmd["id"] == cmd_id:
            return cmd
    return None


def get_help_detail(keyword: str) -> Optional[str]:
    """根据关键词查找说明详情"""
    keyword = keyword.strip()

    for cmd in COMMANDS:
        if cmd.get("help_detail") is None:
            continue

        # 匹配 ID
        if keyword == cmd["id"]:
            return cmd["help_detail"]

        # 匹配 display_name（精确匹配）
        if keyword == cmd.get("display_name", ""):
            return cmd["help_detail"]

        # 匹配 display_name（子串匹配，如"嘿咻"匹配"嘿咻捕获计划"）
        dn = cmd.get("display_name", "")
        if dn and keyword in dn:
            return cmd["help_detail"]

        # 匹配 slash 触发词
        if keyword in cmd.get("slash", []):
            return cmd["help_detail"]

        # 匹配 text 触发词
        if keyword in cmd.get("text", []):
            return cmd["help_detail"]

        # 匹配 help_keywords（新增字段）
        if keyword in cmd.get("help_keywords", []):
            return cmd["help_detail"]

    return None


def get_section_help_keywords() -> list:
    """获取所有有说明详情的关键词列表（用于 /说明 无参数时展示）"""
    keywords = []
    for cmd in COMMANDS:
        if cmd.get("help_detail"):
            # 优先取 display_name 作为展示
            dn = cmd.get("display_name", "")
            if dn:
                keywords.append(dn)
            elif cmd.get("text"):
                keywords.append(cmd["text"][0])
            elif cmd.get("slash"):
                keywords.append(cmd["slash"][0])
    return keywords