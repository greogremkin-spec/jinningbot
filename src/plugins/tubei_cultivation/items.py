"""
晋宁会馆·秃贝五边形 4.1
灵质空间 —— 储物袋 + 道具使用 + 法宝熔炼 + 灵域解锁

3.2 改动：
1. 道具体系全面重构（碎碎念描述系统）
2. 清茶一壶 → 清心露（厨房成功率+20%）
3. 聚灵花改为即时消耗（+15灵力）
4. 上古秘卷改为永久派遣+3
5. 嘿咻毛球改为可复用灵物
6. 虚空结晶：熔炼时品质提升一档
7. 露水凝珠：灌溉时浇水效果翻倍（移至garden.py处理）
8. 三大决策组信物：析沐的钥匙 / 吉熙的信羽 / 焚的残火
9. 新增 /解锁 指令（配合析沐的钥匙）
10. 熔炼系统接入虚空结晶升档
11. 万宝如意 / 混沌残片 保持
12. 接入成就系统
"""

import random
import time
import asyncio
from collections import Counter

from nonebot import on_command, get_bot
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.adapters import Message

from src.common.utils import check_blessing

from src.common.data_manager import data_manager
from src.common.ui_renderer import ui
from src.common.permission import check_permission
from src.plugins.tubei_system.config import game_config
from src.plugins.tubei_system.recorder import recorder
from src.plugins.tubei_cultivation.achievement import achievement_engine


# ==================== 物品定义（含碎碎念） ====================

ARTIFACTS = {
    # ========== 🌿 灵植（药圃产出） ==========
    "灵心草": {
        "desc": "下次聚灵总收益×1.5",
        "type": "buff",
        "lore": (
            "据说是会馆后山最常见的杂草。"
            "但不知道为什么，嚼一片再去聚灵，"
            "灵气就像不要钱似的往身体里灌。"
            "析沐大人曾经试图拔光它们来美化环境，"
            "结果第二天又长满了。生命力真强。"
        ),
    },
    "蓝玉果": {
        "desc": "下次聚灵基础值锁定最大值",
        "type": "buff",
        "lore": (
            "蓝得不太正常的果子，咬一口满嘴灵气。"
            "传说是从灵溪上游漂下来的，"
            "没人知道上游到底有什么。"
            "吉熙馆长说她小时候拿这个当弹珠玩，"
            "浪费了多少修行资源啊这位。"
        ),
    },
    "鸾草": {
        "desc": "下次灵质鉴定必出稀有词条",
        "type": "buff",
        "lore": (
            "叶片上天然带着奇怪的纹路，"
            "像是谁在上面写了字又擦掉了。"
            "鉴定师说这种草能和灵质产生共振，"
            "所以拿着它做鉴定特别准。"
            "秃贝曾经偷吃了一片，"
            "结果打嗝打了三天，每个嗝都带火花。"
        ),
    },
    "凤羽花": {
        "desc": "下次派遣必掉落法宝碎片",
        "type": "buff",
        "lore": (
            "花瓣是橙红色的，逆光看像在燃烧。"
            "鸠老说这花只在有宝物的地方绽放，"
            "所以带着它出去探索，"
            "总能找到好东西。"
            "唯一的缺点是太好看了，"
            "经常被采回来插花瓶，浪费了。"
        ),
    },
    "忘忧草": {
        "desc": "立即消除[味蕾丧失]状态",
        "type": "active",
        "lore": (
            "闻一下就觉得世界美好了。"
            "发明这个的人一定吃过无限大人做的饭。"
            "事实上，整个忘忧草的培育项目"
            "就是管理组专门为'无限大人的厨房'"
            "配套开发的应急预案。"
            "无限本人对此表示：'我做的饭明明很好吃。'"
        ),
    },
    "聚灵花": {
        "desc": "使用后立即获得15灵力",
        "type": "active",
        "lore": (
            "把花瓣碾碎就能释放出纯净的灵气。"
            "很多小妖嫌聚灵太慢就嚼这个，"
            "相当于灵界的功能饮料。"
            "但老一辈的妖精觉得这样不踏实，"
            "'修行哪有走捷径的？'"
            "然后他们自己偷偷也嚼。"
        ),
    },

    # ========== 💊 丹药（熔炼/派遣产出） ==========
    "涪灵丹": {
        "desc": "抵消下次厨房失败惩罚",
        "type": "buff",
        "lore": (
            "专门给要去无限大人厨房吃饭的勇士准备的。"
            "提前服用，可在胃壁形成灵力保护膜。"
            "发明者是焚大人，"
            "因为她是第一个因为'给面子'"
            "而吃完无限的料理的妖精。"
            "她活了几亿年，那是她最接近死亡的一次。"
        ),
    },
    "玄清丹": {
        "desc": "重置今日聚灵次数",
        "type": "active",
        "lore": (
            "吃了之后灵脉里堵住的灵气一下子通了。"
            "感觉就像被人拍了一下后背。"
            "制作工艺据说失传了，"
            "但不知道为什么派遣的时候偶尔能捡到。"
            "也许古人也有'今天还想再练一次'的烦恼。"
        ),
    },
    "清心露": {
        "desc": "今日厨房成功率+20%",
        "type": "buff",
        "lore": (
            "一小瓶透明的液体，喝了心特别静。"
            "面对无限大人端出来的不明物体时，"
            "你能用更平和的心态去品尝。"
            "当然，平和不代表好吃。"
            "只是你不那么害怕了而已。"
            "生产商：云隐茶楼 · 监制：管理组。"
        ),
    },

    # ========== ⚡ 法宝（熔炼稀有/派遣高级产出） ==========
    "空间简片": {
        "desc": "下次派遣耗时减半",
        "type": "buff",
        "lore": (
            "一片薄如蝉翼的透明碎片，"
            "据说是上古空间法宝破碎后的残余。"
            "贴在身上可以短暂折叠空间，"
            "赶路速度翻倍。"
            "副作用是会晕车。"
            "嗯，晕空间。"
        ),
    },
    "引灵香": {
        "desc": "立即在群内召唤一只野生嘿咻",
        "type": "active_group",
        "lore": (
            "点燃后会散发出嘿咻们无法抗拒的香气。"
            "成分是个谜，据说包含了三种嘿咻喜欢的味道："
            "阳光的味道、树叶的味道、"
            "以及析沐大人洗完头的味道。"
            "析沐：'最后一个是谁加的？？？'"
        ),
    },
    "万宝如意": {
        "desc": "下次熔炼品质至少为稀有",
        "type": "buff",
        "lore": (
            "如意造型的小法宝，放在熔炉旁边"
            "就能让炉火变得温顺听话。"
            "它不保证你能炼出什么，"
            "但保证炼出来的东西不会太差。"
            "'至少是个稀有。'——这是它的底线。"
            "'但也可能只是个稀有。'——这也是它的底线。"
        ),
    },
    "五行灵核": {
        "desc": "药圃任意一株瞬间成熟",
        "type": "active",
        "lore": (
            "五种颜色交替闪烁的小球，"
            "拿在手里微微发烫。"
            "埋进土里可以瞬间催熟一株灵植。"
            "代价是周围半径三米的草全秃了。"
            "所以请不要在析沐大人头上使用。"
            "不是，他头上的是树枝不是草——算了。"
        ),
    },
    "护身符": {
        "desc": "下次派遣灵力收益+20%",
        "type": "buff",
        "lore": (
            "管理组统一制作的黄色符纸，"
            "上面画着看不懂的符文。"
            "据事泽大人说，这些符文的意思是"
            "'出门在外注意安全早点回来'。"
            "很朴实，但确实有用。"
            "有种被老妈塞红包的感觉。"
        ),
    },

    # ========== 🔮 秘宝（永久效果，极稀有） ==========
    "完整天明珠": {
        "desc": "使用后永久聚灵收益+5",
        "type": "permanent",
        "lore": (
            "龙脉深处凝结的灵气结晶，"
            "发出温暖的白光。"
            "融入灵脉后，你的身体会永远记住"
            "这种'被灵气包围'的感觉，"
            "从此聚灵效率永久提升。"
            "持有者感言：'我觉得我开挂了。'"
            "管理组回应：'你没有，这是合法的。'"
        ),
    },
    "上古秘卷": {
        "desc": "使用后永久派遣收益+3",
        "type": "permanent",
        "lore": (
            "泛黄的卷轴上记载着古代妖灵的探索经验。"
            "读完之后你会发现，"
            "原来那些灵域的好东西都藏在你想不到的地方。"
            "'原来要翻开第三块石板啊...'"
            "从此每次派遣都能多带点好东西回来。"
            "知识就是力量，诚不欺我。"
        ),
    },

    # ========== 🧱 材料（不可直接使用） ==========
    "法宝碎片": {
        "desc": "熔炼主材料（10个熔炼一次）",
        "type": "material",
        "lore": (
            "到处都能捡到的法宝残骸。"
            "单独一片没什么用，"
            "但攒够十片扔进熔炉，"
            "说不定能炼出比原来更好的东西。"
            "'垃圾是放错位置的资源'"
            "——某位不愿透露姓名的炼器师。"
        ),
    },
    "神秘种子": {
        "desc": "药圃播种消耗品",
        "type": "seed",
        "lore": (
            "不知道是什么植物的种子，"
            "但种下去一定会长出有用的东西。"
            "有人怀疑这些种子是析沐大人"
            "从头上撇下来的树枝变的。"
            "析沐：'别什么都往我头上安。'"
            "种子：（沉默但发芽了）"
        ),
    },
    "虚空结晶": {
        "desc": "熔炼时自动消耗，产物品质提升一档",
        "type": "material",
        "lore": (
            "从镜中世界带回来的透明结晶，"
            "里面好像封着一小块扭曲的空间。"
            "扔进熔炉里可以提升产物品质。"
            "原理是什么？没人知道。"
            "'也许是因为虚空中什么都有可能发生吧。'"
            "——秃贝如是说（其实它也不懂）。"
        ),
    },
    "露水凝珠": {
        "desc": "灌溉时自动消耗，浇水效果翻倍",
        "type": "material",
        "lore": (
            "清晨从灵溪浅滩收集的灵露，"
            "凝结成珍珠大小的水滴。"
            "用它浇灌植物，一次顶两次。"
            "植物们特别喜欢这个，"
            "大概就像人类觉得"
            "矿泉水比自来水高级一样吧。"
        ),
    },

    # ========== 🐾 灵物（可复用/特殊） ==========
    "嘿咻毛球": {
        "desc": "可反复使用，随机小惊喜",
        "type": "active_reusable",
        "lore": (
            "从嘿咻身上薅下来的一团毛。"
            "别担心，嘿咻掉毛比猫还快，"
            "薅完第二天就长回来了。"
            "捏在手里软绵绵的，"
            "心情不好的时候揉一揉，"
            "会获得一种莫名的治愈感。"
            "据说这就是'嘿咻疗法'。"
            "疗效因人而异，但不会更差。"
        ),
    },

    # ========== 🏆 决策组信物（派遣极低概率掉落） ==========
    "析沐的钥匙": {
        "desc": "永久解锁一个等级不足的派遣灵域",
        "type": "special_key",
        "lore": (
            "妖王析沐为了锻炼小妖们的胆量，"
            "故意把自己的空间钥匙'遗失'在各个灵域。"
            "'年轻人就该多出去闯闯。'"
            "'但是大人，有些区域很危险——'"
            "'闯闯就知道了。'"
            "'......'"
            "使用后可选择一个等级不足的区域永久解锁。"
        ),
    },
    "吉熙的信羽": {
        "desc": "获得「吉兆」Buff(24h)，每个系统各一次最佳结果",
        "type": "blessing_feather",
        "lore": (
            "前馆长吉熙的喜鹊之羽，"
            "洁白的羽毛上流转着淡淡的金光。"
            "据说拿着它做任何事都会特别顺利。"
            "'喜鹊报喜嘛，这是种族天赋。'"
            "吉熙本人如是说，然后得意地拍了拍翅膀。"
            "持此羽毛任何项目均可获最佳结果！"
            "24小时后效果自动消失。"
        ),
    },
    "焚的残火": {
        "desc": "立即获得当前灵力×25%",
        "type": "ancient_flame",
        "lore": (
            "焚大人指尖偶然落下的一缕残火。"
            "几亿年的岁月都没能将它熄灭，"
            "可见其中蕴含的力量有多深厚。"
            "古老的火焰会燃烧掉灵力中的杂质，"
            "纯化后的灵力反而更加充沛。"
            "焚大人：'不过是指缝间漏出的余烬罢了。'"
            "小妖们：（看着暴涨25%的灵力感动哭了）"
        ),
    },

    # ========== 熔炉彩蛋专属 ==========
    "破碎星核": {
        "desc": "使用后永久聚灵收益+3",
        "type": "permanent",
        "lore": (
            "熔炉爆炸时偶尔产生的奇异结晶。"
            "理论上不应该存在，"
            "但它就是出现了。"
            "吸收后会感觉灵脉里多了一个小太阳，"
            "暖暖的，每次聚灵都比以前多一点点。"
            "'失败是成功之母'的最佳代言。"
        ),
    },
    "混沌残片": {
        "desc": "下次熔炼必出传说品质",
        "type": "buff",
        "lore": (
            "熔炉彩蛋中的彩蛋，"
            "一块不断变换颜色的碎片。"
            "拿着它靠近熔炉时，"
            "炉火会变成七彩色。"
            "此时熔炼出来的东西..."
            "必定是传说级别的。"
            "'运气这种东西，偶尔也会站在你这边。'"
        ),
    },
}


# ==================== 指令注册 ====================

bag_cmd = on_command("我的背包", aliases={"背包", "储物袋"}, priority=5, block=True)
use_cmd = on_command("使用", priority=5, block=True)
smelt_cmd = on_command("法宝熔炼", aliases={"熔炼"}, priority=5, block=True)
lore_cmd = on_command("图鉴", aliases={"道具图鉴", "碎碎念"}, priority=5, block=True)
unlock_cmd = on_command("解锁", aliases={"解锁灵域"}, priority=5, block=True)


# ==================== 背包 ====================
@bag_cmd.handle()
async def handle_bag(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "灵质空间 · 储物袋",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await bag_cmd.finish(perm.deny_message)

    data = await data_manager.get_spirit_data(uid)
    items = data.get("items", {})
    valid_items = {k: v for k, v in items.items() if v > 0}

    if not valid_items:
        await bag_cmd.finish(ui.render_panel(
            "灵质空间 · 储物袋",
            "🎒 背包空空如也~\n\n📌 通过派遣、药圃、熔炼可以获得道具",
            footer="👉输入  派遣 | 药圃 | 熔炼"
        ))
        return

    if len(valid_items) != len(items):
        await data_manager.update_spirit_data(uid, {"items": valid_items})

    lines = []
    for name, count in valid_items.items():
        desc = ARTIFACTS.get(name, {}).get("desc", "未知物品")
        lines.append(ui.render_bag_item(name, count, desc))

    content = "\n".join(lines)
    card = ui.render_panel(
        f"灵质空间 · 储物袋 ({sum(valid_items.values())}件)",
        content,
        footer="👉输入  使用 [物品名] | 图鉴 [物品名] | 熔炼"
    )
    await bag_cmd.finish(card)


# ==================== 道具图鉴（碎碎念） ====================
@lore_cmd.handle()
async def handle_lore(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    item_name = args.extract_plain_text().strip()

    if not item_name:
        # 列出所有道具分类
        categories = {
            "🌿 灵植": ["灵心草", "蓝玉果", "鸾草", "凤羽花", "忘忧草", "聚灵花"],
            "💊 丹药": ["涪灵丹", "玄清丹", "清心露"],
            "⚡ 法宝": ["空间简片", "引灵香", "万宝如意", "五行灵核", "护身符"],
            "🔮 秘宝": ["完整天明珠", "上古秘卷", "破碎星核"],
            "🧱 材料": ["法宝碎片", "神秘种子", "虚空结晶", "露水凝珠"],
            "🐾 灵物": ["嘿咻毛球", "混沌残片"],
            "🏆 决策组信物": ["析沐的钥匙", "吉熙的信羽", "焚的残火"],
        }
        lines = []
        for cat, names in categories.items():
            lines.append(f"\n{cat}")
            for n in names:
                lines.append(f"  · {n}")
        content = "\n".join(lines)
        await lore_cmd.finish(ui.render_panel(
            "📖 道具图鉴",
            content,
            footer="👉输入  图鉴 [道具名] 查看碎碎念"
        ))
        return

    info = ARTIFACTS.get(item_name)
    if not info:
        await lore_cmd.finish(ui.error(f"未找到「{item_name}」的图鉴。"))

    lore_text = info.get("lore", "这个道具很神秘，连秃贝也不了解它。")
    desc = info.get("desc", "未知效果")

    card = ui.render_panel(
        f"📖 {item_name}",
        f"📌 效果：{desc}\n\n💬 {lore_text}",
        footer="👉输入  背包 | 使用 [道具名]"
    )
    await lore_cmd.finish(card)



# ==================== 使用道具 ====================
@use_cmd.handle()
async def handle_use(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    uid = str(event.user_id)
    item_name = args.extract_plain_text().strip()

    if not item_name:
        await use_cmd.finish(ui.info("请指定道具名称。\n📌 用法：/使用 [道具名]"))

    perm = await check_permission(event, "道具使用",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await use_cmd.finish(perm.deny_message)

    data = await data_manager.get_spirit_data(uid)
    items = data.get("items", {})

    if items.get(item_name, 0) < 1:
        await use_cmd.finish(ui.error(f"没有【{item_name}】。"))

    info = ARTIFACTS.get(item_name)
    if not info:
        await use_cmd.finish(ui.error("未知物品。"))

    item_type = info.get("type")
    buffs = data.get("buffs", {})
    daily = data.get("daily_counts", {})
    result_msg = ""

    # ===== 不可直接使用的类型 =====
    if item_type in ("material", "seed"):
        await use_cmd.finish(ui.info(f"【{item_name}】无法直接使用。\n📌 {info['desc']}"))

    # ===== 特殊道具：析沐的钥匙 =====
    if item_type == "special_key":
        user_level = data.get("level", 1)
        unlocked = data.get("unlocked_locations", [])
        all_locations = game_config.expedition_locations

        # 找出所有需要钥匙解锁的区域
        # 找出下一个等级的区域（不能跳级）
        # 确定下一个等级是多少
        all_levels = sorted(set(loc_cfg.get("level", 1) for loc_cfg in all_locations.values()))
        next_level = None
        for lv in all_levels:
            if lv > user_level:
                next_level = lv
                break

        lockable = []
        if next_level is not None:
            for loc_name, loc_cfg in all_locations.items():
                req_lv = loc_cfg.get("level", 1)
                if req_lv == next_level and loc_name not in unlocked:
                    lockable.append((loc_name, req_lv, loc_cfg.get("desc", "")))

        if not lockable:
            await use_cmd.finish(ui.info(
                "你已经可以进入所有区域了，钥匙暂时无处可用~\n"
                "📌 等级提升后所有区域自动解锁，无需钥匙。"
            ))
            return

        # 构建选择列表
        lines = ["这把古老的钥匙在你手中微微发光...\n"]
        lines.append("请发送 /解锁 [区域名] 来选择要解锁的灵域：\n")

        # 按等级分组
        groups = {}
        for loc_name, req_lv, desc in lockable:
            if req_lv not in groups:
                groups[req_lv] = []
            groups[req_lv].append((loc_name, desc))

        for lv in sorted(groups.keys()):
            lines.append(f"🔒 Lv.{lv} 区域：")
            for loc_name, desc in groups[lv]:
                lines.append(f"  · {loc_name}")
                lines.append(f"    {desc[:30]}...")
            lines.append("")

        card = ui.render_panel(
            "析沐的钥匙 · 灵域解锁",
            "\n".join(lines),
            footer="👉输入  解锁 [区域名]  |  发送其他内容取消"
        )
        await use_cmd.finish(card)

    # ===== 特殊道具：吉熙的信羽 =====
    if item_type == "blessing_feather":
        # 检查是否已有吉兆
        existing = buffs.get("blessing")
        if existing and isinstance(existing, dict) and time.time() < existing.get("expire", 0):
            await use_cmd.finish(ui.info("「吉兆」Buff 尚未消散，请先享用当前的好运~"))
            return

        # 消耗道具
        items[item_name] -= 1
        if items[item_name] <= 0:
            del items[item_name]

        # 设置吉兆buff（24小时，四个系统各一次）
        buffs["blessing"] = {
            "expire": time.time() + 86400,
            "kitchen": True,
            "meditation": True,
            "resonance": True,
            "smelting": True,
        }

        await data_manager.update_spirit_data(uid, {"items": items, "buffs": buffs})

        await recorder.add_event("use_item", int(uid), {"item": item_name})

        # 成就检查
        await achievement_engine.try_unlock(uid, "吉祥之人", bot, event)

        result_msg = (
            "🪶 信羽化为金光融入了你的灵脉...\n\n"
            "✨ 获得「吉兆」Buff！(24小时)\n\n"
            "接下来的每个系统各享一次最佳结果：\n"
            "  🍳 厨房 → 必定美味\n"
            "  🧘 聚灵 → 必定大吉\n"
            "  🔍 鉴定 → 必出稀有\n"
            "  🔥 熔炼 → 品质升档\n\n"
            "📌 每个系统触发一次后该系统的吉兆消失"
        )
        await use_cmd.finish(ui.render_result_card(
            "吉熙的信羽 · 喜鹊报喜",
            result_msg,
            footer="👉输入  好运已就位，去闯荡吧！"
        ))

    # ===== 特殊道具：焚的残火 =====
    if item_type == "ancient_flame":
        current_sp = data.get("sp", 0)
        gain = int(current_sp * 0.25)

        if gain <= 0:
            await use_cmd.finish(ui.info(
                "你当前灵力太低了，残火找不到足够的杂质来燃烧...\n"
                "📌 先去聚灵攒点灵力再来吧！"
            ))
            return

        # 消耗道具
        items[item_name] -= 1
        if items[item_name] <= 0:
            del items[item_name]

        new_sp = current_sp + gain
        await data_manager.update_spirit_data(uid, {"sp": new_sp, "items": items})

        await recorder.add_event("use_item", int(uid), {
            "item": item_name, "gain": gain, "before": current_sp, "after": new_sp
        })

        # 成就检查
        await achievement_engine.try_unlock(uid, "焚之眷顾", bot, event)

        result_msg = (
            "🔥 残火在掌心燃起，古老的力量灼烧着灵脉中的杂质...\n\n"
            f"灵力杂质被净化，纯度大幅提升！\n\n"
        )
        await use_cmd.finish(ui.render_result_card(
            "焚的残火 · 灵力纯化",
            result_msg,
            stats=[
                ("🔥 纯化前", f"{current_sp} 灵力"),
                ("✨ 纯化后", f"{new_sp} 灵力"),
                ("📈 净增", f"+{gain} 灵力 (+25%)"),
            ],
            footer="焚大人：'不过是余烬罢了。'"
        ))

    # ===== 可复用灵物：嘿咻毛球 =====
    if item_type == "active_reusable":
        if item_name == "嘿咻毛球":
            # 不消耗数量！
            roll = random.random()

            if roll < 0.3:
                # 30%：缩短味蕾丧失
                if buffs.get("taste_loss_expire", 0) > time.time():
                    buffs["taste_loss_expire"] = buffs["taste_loss_expire"] - 3600
                    await data_manager.update_spirit_data(uid, {"buffs": buffs})
                    result_msg = (
                        "你揉了揉嘿咻毛球...软绵绵的...\n"
                        "💚 味蕾丧失时间缩短了1小时！\n"
                        "嘿咻毛球似乎很满意被揉。"
                    )
                else:
                    # 没有味蕾丧失，改为给灵力
                    sp_gain = random.randint(1, 3)
                    new_sp = data.get("sp", 0) + sp_gain
                    await data_manager.update_spirit_data(uid, {"sp": new_sp})
                    result_msg = (
                        "你揉了揉嘿咻毛球...软绵绵的...\n"
                        f"✨ 心情变好了！灵力 +{sp_gain}\n"
                        "嘿咻毛球发出了满足的声音。"
                    )
            elif roll < 0.7:
                # 40%：给灵力
                sp_gain = random.randint(1, 3)
                new_sp = data.get("sp", 0) + sp_gain
                await data_manager.update_spirit_data(uid, {"sp": new_sp})
                result_msg = (
                    "你揉了揉嘿咻毛球...软绵绵的...\n"
                    f"✨ 灵力 +{sp_gain}\n"
                    "它在你手心里蹭了蹭。"
                )
            else:
                # 30%：暖心话
                warm_words = [
                    "你揉了揉嘿咻毛球...什么也没发生。\n但心里暖暖的。\n'(嘿咻嘿咻)' ——毛球如是说。",
                    "你揉了揉嘿咻毛球...它打了个小小的哈欠。\n莫名觉得被治愈了。",
                    "你揉了揉嘿咻毛球...它缩成了一个更圆的球。\n好可爱。今天也要加油。",
                    "你揉了揉嘿咻毛球...它蹭了蹭你的手指。\n'谢谢你一直带着我。' (大概是这个意思)",
                    "你揉了揉嘿咻毛球...它发出了'咕噜咕噜'的声音。\n这是嘿咻表示开心的方式。",
                    "你揉了揉嘿咻毛球...突然觉得，\n不管发生什么，只要有这团毛就够了。",
                ]
                result_msg = random.choice(warm_words)

            await use_cmd.finish(ui.render_result_card(
                "🐾 嘿咻毛球",
                result_msg,
                footer="📌 嘿咻毛球不会消耗，可以反复揉~"
            ))

    # ===== 以下为消耗品逻辑 =====
    # 消耗物品
    items[item_name] -= 1
    if items[item_name] <= 0:
        del items[item_name]

    # ===== Buff 类型 =====
    if item_type == "buff":
        buffs[item_name] = True
        result_msg = f"✨ 【{item_name}】效果已激活！\n📌 {info['desc']}"

    # ===== 主动类型 =====
    elif item_type == "active":
        if item_name == "玄清丹":
            daily["meditation"] = 0
            result_msg = "✨ 玄清丹生效！今日聚灵次数已重置。"

        elif item_name == "忘忧草":
            if buffs.get("taste_loss_expire", 0) > time.time():
                buffs["taste_loss_expire"] = 0
                result_msg = "🌿 忘忧草生效！味蕾已恢复~"
            else:
                # 退还
                items[item_name] = items.get(item_name, 0) + 1
                await data_manager.update_spirit_data(uid, {"items": items})
                await use_cmd.finish(ui.info("你当前没有[味蕾丧失]状态。"))
                return

        elif item_name == "聚灵花":
            sp_gain = 15
            new_sp = data.get("sp", 0) + sp_gain
            await data_manager.update_spirit_data(uid, {"sp": new_sp, "items": items, "buffs": buffs, "daily_counts": daily})
            result_msg = f"🌸 聚灵花绽放！花瓣中的灵气融入体内。\n✨ 灵力 +{sp_gain} (当前: {new_sp})"
            await use_cmd.finish(ui.render_result_card(
                "灵质空间 · 道具使用",
                result_msg,
                footer="👉输入  背包 查看剩余道具"
            ))

        elif item_name == "五行灵核":
            garden = data.get("garden", [])
            matured = False
            if isinstance(garden, list):
                for slot in garden:
                    if slot.get("status") in ("sprout", "growing", "seed"):
                        slot["status"] = "mature"
                        matured = True
                        break
            if matured:
                await data_manager.update_spirit_data(uid, {"garden": garden, "items": items, "buffs": buffs, "daily_counts": daily})
                result_msg = "✨ 五行灵核生效！一株灵植瞬间成熟！"
                await use_cmd.finish(ui.render_result_card(
                    "灵质空间 · 道具使用",
                    result_msg,
                    footer="👉输入  药圃 查看状态 | 收获"
                ))
            else:
                items[item_name] = items.get(item_name, 0) + 1
                await data_manager.update_spirit_data(uid, {"items": items})
                await use_cmd.finish(ui.info("药圃中没有需要催熟的植物。"))
                return

    # ===== 群内主动类型（引灵香） =====
    elif item_type == "active_group":
        if item_name == "引灵香":
            if not isinstance(event, GroupMessageEvent):
                items[item_name] = items.get(item_name, 0) + 1
                await data_manager.update_spirit_data(uid, {"items": items})
                await use_cmd.finish(ui.info("引灵香只能在群内使用~"))
                return
            result_msg = "🔥 引灵香点燃！一股奇异的香气弥漫开来..."
            # 异步召唤嘿咻
            from src.plugins.tubei_entertainment.heixiu_catcher import spawn_heixiu_in_group
            asyncio.create_task(spawn_heixiu_in_group(event.group_id))

    # ===== 永久类型 =====
    elif item_type == "permanent":
        if item_name == "完整天明珠":
            perm_bonus = data.get("permanent_meditation_bonus", 0) + 5
            await data_manager.update_spirit_data(uid, {"permanent_meditation_bonus": perm_bonus})
            result_msg = f"🌟 天明珠光芒绽放！\n📈 永久聚灵收益 +5 (当前加成: +{perm_bonus})"

        elif item_name == "上古秘卷":
            perm_bonus = data.get("permanent_expedition_bonus", 0) + 3
            await data_manager.update_spirit_data(uid, {"permanent_expedition_bonus": perm_bonus})
            result_msg = f"📜 秘卷化为灵光融入灵识！\n📈 永久派遣收益 +3 (当前加成: +{perm_bonus})"

        elif item_name == "破碎星核":
            perm_bonus = data.get("permanent_meditation_bonus", 0) + 3
            await data_manager.update_spirit_data(uid, {"permanent_meditation_bonus": perm_bonus})
            result_msg = f"💫 破碎的星光融入了灵脉！\n📈 永久聚灵收益 +3 (当前加成: +{perm_bonus})"

        else:
            items[item_name] = items.get(item_name, 0) + 1
            await data_manager.update_spirit_data(uid, {"items": items})
            await use_cmd.finish(ui.info("该物品无法直接使用。"))
            return

    await data_manager.update_spirit_data(uid, {
        "items": items,
        "buffs": buffs,
        "daily_counts": daily,
    })

    await use_cmd.finish(ui.render_result_card(
        "灵质空间 · 道具使用",
        result_msg,
        footer="👉输入  背包 查看剩余道具"
    ))


# ==================== 解锁灵域（配合析沐的钥匙） ====================
@unlock_cmd.handle()
async def handle_unlock(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    uid = str(event.user_id)
    target_loc = args.extract_plain_text().strip()

    if not target_loc:
        await unlock_cmd.finish(ui.info(
            "请指定要解锁的区域名称。\n"
            "📌 用法：/解锁 [区域名]\n"
            "📌 先使用 /使用 析沐的钥匙 查看可解锁的区域"
        ))

    perm = await check_permission(event, "灵域解锁",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await unlock_cmd.finish(perm.deny_message)

    data = await data_manager.get_spirit_data(uid)
    items = data.get("items", {})
    user_level = data.get("level", 1)
    unlocked = data.get("unlocked_locations", [])
    all_locations = game_config.expedition_locations

    # 检查是否有钥匙
    if items.get("析沐的钥匙", 0) < 1:
        await unlock_cmd.finish(ui.error("你没有【析沐的钥匙】。\n📌 通过派遣探索有几率获得。"))

    # 检查区域是否存在
    if target_loc not in all_locations:
        await unlock_cmd.finish(ui.error(f"未知区域「{target_loc}」。\n📌 请使用 /使用 析沐的钥匙 查看可解锁区域。"))

    loc_cfg = all_locations[target_loc]
    req_level = loc_cfg.get("level", 1)

    # 检查是否已经可以进入
    if user_level >= req_level:
        await unlock_cmd.finish(ui.info(f"你的等级已经足够进入【{target_loc}】了，不需要钥匙~"))

    # 检查是否是下一个等级（不能跳级）
    all_levels = sorted(set(
        cfg.get("level", 1) for cfg in game_config.expedition_locations.values()
    ))
    next_level = None
    for lv in all_levels:
        if lv > user_level:
            next_level = lv
            break

    if next_level is not None and req_level > next_level:
        await unlock_cmd.finish(ui.error(
            f"【{target_loc}】需要 Lv.{req_level}，但你只能解锁 Lv.{next_level} 的区域。\n"
            f"📌 先提升等级或解锁 Lv.{next_level} 区域吧~"
        ))

    # 检查是否已经用钥匙解锁过
    if target_loc in unlocked:
        await unlock_cmd.finish(ui.info(f"【{target_loc}】已经被钥匙解锁过了~"))

    # 消耗钥匙
    items["析沐的钥匙"] -= 1
    if items["析沐的钥匙"] <= 0:
        del items["析沐的钥匙"]

    # 解锁区域
    unlocked.append(target_loc)

    await data_manager.update_spirit_data(uid, {
        "items": items,
        "unlocked_locations": unlocked,
    })

    await recorder.add_event("unlock_location", int(uid), {"location": target_loc})

    # 成就检查
    await achievement_engine.try_unlock(uid, "钥匙守护者", bot, event)

    desc = loc_cfg.get("desc", "")

    card = ui.render_result_card(
        "析沐的钥匙 · 灵域解锁",
        f"✨ 钥匙化为光芒融入了【{target_loc}】的封印...\n\n"
        f"🔓 {target_loc} 已永久解锁！\n"
        f"📍 {desc}\n\n"
        f"即使等级不足也可以前往探索~",
        stats=[
            ("🔑 消耗", "析沐的钥匙 ×1"),
            ("🗺 解锁", target_loc),
            ("⚠ 需要等级", f"Lv.{req_level} (你当前 Lv.{user_level})"),
        ],
        footer="👉输入  派遣 " + target_loc
    )
    await unlock_cmd.finish(card)


# ==================== 法宝熔炼（3.2 重构） ====================
@smelt_cmd.handle()
async def handle_smelt(bot: Bot, event: MessageEvent):
    uid = str(event.user_id)

    perm = await check_permission(event, "君阁工坊 · 法宝熔炼",
                                  min_tier="allied", require_registered=True)
    if not perm.allowed:
        await smelt_cmd.finish(perm.deny_message)

    data = await data_manager.get_spirit_data(uid)
    items = data.get("items", {})
    buffs = data.get("buffs", {})
    cost = game_config.smelt_cost

    if items.get("法宝碎片", 0) < cost:
        await smelt_cmd.finish(ui.render_data_card(
            "君阁工坊 · 法宝熔炼",
            [
                ("📦 需要", f"法宝碎片 x{cost}"),
                ("📦 持有", f"法宝碎片 x{items.get('法宝碎片', 0)}"),
                ("", ""),
                ("📊 概率", "45%普通 | 35%稀有 | 15%传说 | 5%彩蛋"),
                ("💎 加持", "虚空结晶可提升一档品质"),
            ],
            footer="👉输入  通过派遣获取法宝碎片"
        ))
        return

    # 消耗碎片
    items["法宝碎片"] -= cost
    if items["法宝碎片"] <= 0:
        del items["法宝碎片"]

    # 统计
    await data_manager.increment_stat(uid, "total_smelt_count")

    # ===== 确定品质 =====
    tiers = game_config.get("smelting", "tiers", default={})

    # Buff 覆写
    forced_tier = None
    if buffs.pop("混沌残片", None):
        forced_tier = "legendary"
    elif buffs.pop("万宝如意", None):
        # 至少稀有
        forced_tier = random.choices(
            ["rare", "legendary", "easter_egg"],
            weights=[60, 30, 10],
            k=1
        )[0]

    # 吉兆buff检查：品质升一档
    blessing_upgrade = False
    if check_blessing(buffs, "smelting"):
        blessing_upgrade = True

    if forced_tier:
        selected_tier = forced_tier
    else:
        tier_names = list(tiers.keys())
        tier_rates = [tiers[t].get("rate", 0) for t in tier_names]
        selected_tier = random.choices(tier_names, weights=tier_rates, k=1)[0]

    # 虚空结晶：品质升一档
    crystal_used = False
    if items.get("虚空结晶", 0) > 0 and not forced_tier:
        items["虚空结晶"] -= 1
        if items["虚空结晶"] <= 0:
            del items["虚空结晶"]
        crystal_used = True

    # 应用升档（虚空结晶或吉兆）
    upgrade_count = 0
    if crystal_used:
        upgrade_count += 1
    if blessing_upgrade:
        upgrade_count += 1

    tier_order = ["normal", "rare", "legendary", "easter_egg"]
    for _ in range(upgrade_count):
        idx = tier_order.index(selected_tier) if selected_tier in tier_order else 0
        if idx < len(tier_order) - 1:
            selected_tier = tier_order[idx + 1]

    tier_config = tiers.get(selected_tier, {})
    pool = tier_config.get("pool", [])
    if not pool:
        pool = ["涪灵丹"]

    prize = random.choice(pool)
    items[prize] = items.get(prize, 0) + 1

    await data_manager.update_spirit_data(uid, {"items": items, "buffs": buffs})

    # ===== 构建反馈 =====
    tier_display = {
        "normal": ("✨", "普通"),
        "rare": ("💎", "稀有"),
        "legendary": ("🌟", "传说"),
        "easter_egg": ("🎁", "命运彩蛋"),
    }
    icon, tier_name = tier_display.get(selected_tier, ("✨", "普通"))

    # 构建额外说明
    extra_notes = []
    if crystal_used:
        extra_notes.append("💎 虚空结晶：品质提升一档！")
    if blessing_upgrade:
        extra_notes.append("🪶 吉兆加持：品质提升一档！")

    if selected_tier == "easter_egg":
        description = (
            "炉火猛然熄灭... 碎片化为了灰烬。\n"
            "但灰烬中，有什么在微微发光...\n\n"
            f"🎁 获得了【{prize}】！\n"
            f"📌 {ARTIFACTS.get(prize, {}).get('desc', '')}\n\n"
            "...这或许才是最珍贵的馈赠。"
        )
        # 成就
        await achievement_engine.try_unlock(uid, "否极泰来", bot, event)
    elif selected_tier == "legendary":
        description = f"🌟 奇迹降临！熔炼出了传说中的【{prize}】！"
        await achievement_engine.try_unlock(uid, "命运眷顾", bot, event)
    elif selected_tier == "rare":
        description = f"💎 炉火闪烁，凝结出了稀有法宝【{prize}】！"
    else:
        description = f"✨ 熔炼完成，获得了【{prize}】。"

    # 成就
    await achievement_engine.try_unlock(uid, "炼器学徒", bot, event)
    await achievement_engine.check_stat_achievements(uid, bot, event)

    extra_text = "\n".join(extra_notes) if extra_notes else None

    card = ui.render_result_card(
        f"君阁工坊 · 熔炼结果 [{tier_name}]",
        description,
        stats=[
            ("🔧 消耗", f"法宝碎片 x{cost}"),
            ("📊 品质", f"{icon} {tier_name}"),
            ("🎁 产物", prize),
        ],
        extra=extra_text,
        footer="👉输入  背包 查看道具 | 熔炼 再来一次"
    )
    await smelt_cmd.finish(card)