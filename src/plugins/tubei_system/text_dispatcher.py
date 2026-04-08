"""
晋宁会馆·秃贝五边形 4.1
纯文字指令统一分发器

职责：
1. 监听所有群消息，检查是否匹配纯文字指令
2. 严格全文匹配（"聚灵"触发，"我要聚灵"不触发）
3. 支持带参数的纯文字指令（"派遣 晋宁老街"、"使用 天明珠"）
4. 根据群等级过滤不可用的指令
5. 路由到对应模块的 handler 函数

触发优先级：
  on_command（priority=5）先于本分发器（priority=8）
  所以 /聚灵 会被 on_command 处理，不会到这里
  纯文字 "聚灵" 不带/，不会被 on_command 捕获，由本分发器处理

注意：
  - block=False，不吞消息（让AI兜底仍然能工作）
  - 捕捉嘿咻的"捕捉"由 heixiu_catcher.py 自行处理（有状态判断）
  - "加入会馆"等关键词由 guide 的 on_keyword 处理
  - 本分发器只处理 command_registry 中 text 列表非空的指令
"""

import logging
import time

from nonebot import on_message
from nonebot.adapters.onebot.v11 import (
    Bot, GroupMessageEvent, PrivateMessageEvent, MessageEvent
)
from nonebot.exception import FinishedException
from src.common.command_registry import (
    COMMANDS, MENU_SECTIONS,
    get_all_text_triggers,
    get_text_prefix_triggers,
)
from src.common.group_manager import group_manager, TIER_CORE, TIER_ALLIED, TIER_PUBLIC, TIER_DANGER
logger = logging.getLogger("tubei.text_dispatcher")


# ==================== 构建触发词映射表（启动时一次性构建） ====================

# 精确匹配表：{"聚灵": "meditate", "今日灵伴": "soulmate", ...}
EXACT_TRIGGERS = get_all_text_triggers()

# 前缀匹配表：{"使用": "use_item", "派遣": "expedition", ...}
PREFIX_TRIGGERS = get_text_prefix_triggers()

# 板块触发表：{"行政板块": "admin", "修行板块": "cultivation", ...}
SECTION_TRIGGERS = {}
for section_id, section_info in MENU_SECTIONS.items():
    text_trigger = section_info.get("text_trigger", "")
    if text_trigger:
        SECTION_TRIGGERS[text_trigger] = section_id
        # 新增：自动注册 "版块" 别名
        if "板块" in text_trigger:
            variant = text_trigger.replace("板块", "版块")
            SECTION_TRIGGERS[variant] = section_id

# 指令ID → 指令定义的快速索引
CMD_INDEX = {cmd["id"]: cmd for cmd in COMMANDS}

# 需要跳过的指令ID（由其他模块自行处理）
SKIP_IDS = {
    "heixiu_catch",     # 嘿咻捕捉由 heixiu_catcher.py 的 on_message 处理（有HEIXIU_STATE状态判断）
    "join_guide",       # 加入引导由 guide 的 on_keyword 处理
    #"quit_easter_egg",  # 退出彩蛋由 resonance.py 处理
}


# ==================== 群等级检查 ====================

TIER_PRIORITY = {
    TIER_CORE: 0,
    TIER_ALLIED: 1,
    TIER_PUBLIC: 2,
    TIER_DANGER: 3,
}


def _tier_meets(current_tier: str, required_tier: str) -> bool:
    """检查当前群等级是否满足最低要求"""
    return TIER_PRIORITY.get(current_tier, 99) <= TIER_PRIORITY.get(required_tier, 99)


# ==================== 分发器注册 ====================

text_dispatcher = on_message(priority=8, block=False)


@text_dispatcher.handle()
async def handle_text_dispatch(bot: Bot, event: MessageEvent):
    """纯文字指令统一分发器"""

# 群消息和私聊都支持纯文字指令
# （严格全文匹配，不会误触发）

    text = event.get_plaintext().strip()

    # 空消息不处理
    if not text:
        return

    # danger群：只允许今日老婆和退出彩蛋，直接路由，不走正常流程
    if isinstance(event, GroupMessageEvent):
        _group_tier = group_manager.get_group_tier(event.group_id)
        if _group_tier == TIER_DANGER:
            if text == "今日老婆":
                await _route_to_handler(bot, event, "waifu", args_text="")
                raise FinishedException
            elif text == "退出此群":
                await _route_to_handler(bot, event, "quit_easter_egg", args_text="")
                raise FinishedException
            else:
                return  # 其他所有指令静默忽略

    # 带 / 开头的不处理（由 on_command 处理）
    if text.startswith("/") or text.startswith("／"):
        return

    # 包含多条指令的不处理（如 "聚灵 派遣"）
    # 但要排除带参数的情况（如 "派遣 晋宁老街"）
    # 策略：先尝试精确匹配，再尝试前缀匹配

    # ===== 1. 板块菜单触发 =====
    if text in SECTION_TRIGGERS:
        section_id = SECTION_TRIGGERS[text]
        # 导入放在这里避免循环引用
        from src.plugins.tubei_guide import _send_section_menu
        await _send_section_menu(bot, event, section_id)
        raise FinishedException

    # ===== 2. 精确匹配（无参数指令） =====
    if text in EXACT_TRIGGERS:
        cmd_id = EXACT_TRIGGERS[text]

        # 跳过由其他模块自行处理的指令
        if cmd_id in SKIP_IDS:
            return

        cmd_def = CMD_INDEX.get(cmd_id)
        if not cmd_def:
            return

        # 群等级检查
        if isinstance(event, GroupMessageEvent):
            group_tier = group_manager.get_group_tier(event.group_id)
        else:
            group_tier = "core"
        min_tier = cmd_def.get("min_tier", "public")
        if not _tier_meets(group_tier, min_tier):
            return  # 静默忽略，不提示（避免打扰聊天）

        # 路由到对应handler
        await _route_to_handler(bot, event, cmd_id, args_text="")
        raise FinishedException

    # ===== 3. 前缀匹配（带参数指令） =====
    for prefix, cmd_id in PREFIX_TRIGGERS.items():
        # 检查是否以 "前缀 " 开头（注意空格）
        if text == prefix:
            # 无参数的情况，也是精确匹配（已在上面处理）
            # 但如果精确匹配表里没有这个词，则在这里处理
            cmd_def = CMD_INDEX.get(cmd_id)
            if not cmd_def:
                continue

            if isinstance(event, GroupMessageEvent):
                group_tier = group_manager.get_group_tier(event.group_id)
            else:
                group_tier = "core"
            min_tier = cmd_def.get("min_tier", "public")
            if not _tier_meets(group_tier, min_tier):
                return

            await _route_to_handler(bot, event, cmd_id, args_text="")
            raise FinishedException

        if text.startswith(prefix + " "):
            # 有参数的情况
            args_text = text[len(prefix):].strip()

            if cmd_id in SKIP_IDS:
                return

            cmd_def = CMD_INDEX.get(cmd_id)
            if not cmd_def:
                continue

            if isinstance(event, GroupMessageEvent):
                group_tier = group_manager.get_group_tier(event.group_id)
            else:
                group_tier = "core"
            min_tier = cmd_def.get("min_tier", "public")
            if not _tier_meets(group_tier, min_tier):
                return

            await _route_to_handler(bot, event, cmd_id, args_text=args_text)
            raise FinishedException

    # 没有匹配到任何纯文字指令，静默返回（让后续handler处理，如AI聊天）


# ==================== 路由到对应handler ====================

async def _route_to_handler(bot: Bot, event: MessageEvent, cmd_id: str, args_text: str):
    """
    根据指令ID路由到对应模块的handler函数。

    由于各模块已经通过 on_command 注册了 /指令 的处理，
    纯文字触发需要直接调用它们的核心逻辑函数。

    策略：用 bot.send 模拟一条带 / 的消息让 NoneBot 重新处理。
    但这样会有副作用（重复触发拦截器等）。

    更好的策略：直接import并调用各模块的handler。
    但这需要各模块暴露核心逻辑函数。

    最简洁的策略：构造一条带 / 前缀的指令消息，
    通过 bot.send_group_msg 发送给自己再处理。
    但这也有问题。

    最终方案：直接调用 NoneBot 的 matcher。
    我们通过 on_command 注册的 matcher 的 slash[0] 来找到它，
    然后手动触发。但这在 NoneBot2 中不直接支持。

    实际最佳方案：各模块把核心逻辑抽成独立函数，
    on_command 和 text_dispatcher 都调用同一个函数。
    但这需要改所有模块，改动太大。

    折中方案（当前采用）：
    直接模拟触发对应的 on_command。
    NoneBot2 的 on_command 内部会检查 command_start，
    所以纯文字消息不会触发它。
    我们需要手动处理。

    最终实现：使用 handle_event 伪造事件。
    这是 NoneBot2 官方不推荐但可行的方式。

    ===== 实际采用的方案 =====
    我们使用最简单直接的方式：
    在各模块中，把核心逻辑抽到一个 async 函数中，
    on_command handler 调用它，text_dispatcher 也调用它。

    但由于我们承诺不大改现有模块的handler逻辑，
    所以这里用另一个方案：

    修改消息的 raw_message，在前面加上 /，
    然后用 nonebot.message.handle_event 重新处理。

    但这太hack了。

    ===== 真正采用的方案 =====
    最简单、最稳定、最少改动的方案：
    直接在 text_dispatcher 中 import 各模块的 handler 函数并调用。
    各模块的 handler 函数签名都是 (bot, event, ...) 形式，
    我们可以直接调用。

    唯一的问题是：on_command 的 handler 会在最后调用 cmd.finish()，
    而 finish() 会抛出异常。我们需要捕获它。
    """

    try:
        if cmd_id == "register_guide":
            from src.plugins.tubei_admin.registry import handle_guide
            await handle_guide(bot, event)
        
        elif cmd_id == "view_commands":
            from src.plugins.tubei_guide import _handle_view_commands
            await _handle_view_commands(bot, event)

        elif cmd_id == "profile":
            from src.plugins.tubei_cultivation.meditation import handle_profile
            await handle_profile(bot, event)

        elif cmd_id == "member_list":
            from src.plugins.tubei_admin.manager import handle_list
            await handle_list(bot, event)

        elif cmd_id == "meditate":
            from src.plugins.tubei_cultivation.meditation import handle_meditate
            await handle_meditate(bot, event)

        elif cmd_id == "fortune":
            from src.plugins.tubei_cultivation.meditation import handle_fortune
            await handle_fortune(bot, event)

        elif cmd_id == "expedition":
            from src.plugins.tubei_cultivation.expedition import handle_expedition
            # 需要模拟 CommandArg
            from nonebot.adapters import Message as NBMessage
            from nonebot.adapters.onebot.v11 import Message
            msg = Message(args_text) if args_text else Message()
            await handle_expedition(bot, event, msg)

        elif cmd_id == "recall":
            from src.plugins.tubei_cultivation.expedition import handle_recall
            await handle_recall(bot, event)

        elif cmd_id == "garden":
            from src.plugins.tubei_cultivation.garden import handle_garden
            await handle_garden(bot, event)

        elif cmd_id == "sow":
            from src.plugins.tubei_cultivation.garden import handle_sow
            from nonebot.adapters.onebot.v11 import Message
            msg = Message(args_text) if args_text else Message()
            await handle_sow(bot, event, msg)

        elif cmd_id == "water":
            from src.plugins.tubei_cultivation.garden import handle_water
            await handle_water(bot, event)

        elif cmd_id == "harvest":
            from src.plugins.tubei_cultivation.garden import handle_harvest
            await handle_harvest(bot, event)

        elif cmd_id == "bag":
            from src.plugins.tubei_cultivation.items import handle_bag
            await handle_bag(bot, event)

        elif cmd_id == "use_item":
            from src.plugins.tubei_cultivation.items import handle_use
            from nonebot.adapters.onebot.v11 import Message
            msg = Message(args_text) if args_text else Message()
            await handle_use(bot, event, msg)

        elif cmd_id == "smelt":
            from src.plugins.tubei_cultivation.items import handle_smelt
            await handle_smelt(bot, event)

        elif cmd_id == "lore":
            from src.plugins.tubei_cultivation.items import handle_lore
            from nonebot.adapters.onebot.v11 import Message
            msg = Message(args_text) if args_text else Message()
            await handle_lore(bot, event, msg)

        elif cmd_id == "unlock":
            from src.plugins.tubei_cultivation.items import handle_unlock
            from nonebot.adapters.onebot.v11 import Message
            msg = Message(args_text) if args_text else Message()
            await handle_unlock(bot, event, msg)

        elif cmd_id == "altar":
            from src.plugins.tubei_cultivation.altar import handle_altar
            await handle_altar(bot, event)

        elif cmd_id == "achievement":
            from src.plugins.tubei_cultivation.achievement import handle_achievement
            await handle_achievement(bot, event)

        elif cmd_id == "title":
            from src.plugins.tubei_cultivation.achievement import handle_title
            from nonebot.adapters.onebot.v11 import Message
            msg = Message(args_text) if args_text else Message()
            await handle_title(bot, event, msg)

        elif cmd_id == "ranking":
            from src.plugins.tubei_cultivation.ranking import _render_ranking, handle_ranking
            from nonebot.adapters.onebot.v11 import Message

            # 直达式排行榜：从原始文本判断类型
            text = event.get_plaintext().strip()
            direct_map = {
                "灵力排行榜": "灵力", "灵力榜": "灵力", "灵力排行": "灵力",
                "嘿咻排行榜": "嘿咻", "嘿咻榜": "嘿咻", "嘿咻排行": "嘿咻",
                "聚灵排行榜": "聚灵", "聚灵榜": "聚灵", "聚灵排行": "聚灵",
                "厨房排行榜": "厨房", "厨房榜": "厨房", "厨房排行": "厨房",
                "派遣排行榜": "派遣", "派遣榜": "派遣", "派遣排行": "派遣",
            }

            ranking_key = direct_map.get(text)
            if ranking_key:
                # 直达式：直接渲染对应榜单
                await _render_ranking(bot, event, ranking_key)
            else:
                # 参数式：排行榜 嘿咻
                msg = Message(args_text) if args_text else Message()
                await handle_ranking(bot, event, msg)

        elif cmd_id == "world_event":
            from src.plugins.tubei_system.world_event import handle_event_status
            await handle_event_status(bot, event)

        elif cmd_id == "kitchen":
            from src.plugins.tubei_entertainment.kitchen import handle_kitchen
            await handle_kitchen(bot, event)

        elif cmd_id == "appraise":
            from src.plugins.tubei_entertainment.resonance import handle_appraise
            await handle_appraise(bot, event)

        elif cmd_id == "duel":
            from src.plugins.tubei_entertainment.duel import handle_duel
            from nonebot.adapters.onebot.v11 import Message
            msg = Message(args_text) if args_text else Message()
            await handle_duel(bot, event, msg)

        elif cmd_id == "truth":
            from src.plugins.tubei_entertainment.truth_dare import handle_truth
            await handle_truth(bot, event)

        elif cmd_id == "dare":
            from src.plugins.tubei_entertainment.truth_dare import handle_dare
            await handle_dare(bot, event)

        elif cmd_id == "soulmate":
            from src.plugins.tubei_entertainment.resonance import _handle_soulmate
            await _handle_soulmate(bot, event)

        elif cmd_id == "waifu":
            from src.plugins.tubei_entertainment.resonance import _handle_waifu
            await _handle_waifu(bot, event)

        elif cmd_id == "menu":
            from src.plugins.tubei_guide import _handle_menu
            await _handle_menu(bot, event)

        elif cmd_id == "quit_easter_egg":
            from src.plugins.tubei_entertainment.resonance import _handle_quit_easter_egg
            await _handle_quit_easter_egg(bot, event)

        elif cmd_id == "help":
            from src.plugins.tubei_guide import _handle_help
            await _handle_help(bot, event, args_text)
        
        elif cmd_id == "manual":
            from src.plugins.tubei_guide import handle_manual
            await handle_manual(bot, event)

        elif cmd_id == "admin_commands":
            from src.plugins.tubei_guide import _handle_admin_commands
            await _handle_admin_commands(bot, event)

        else:
            logger.debug(f"[TextDispatcher] 未实现的指令路由: {cmd_id}")

    except Exception as e:
        # on_command 的 handler 会调用 cmd.finish() 抛出 FinishedException
        # 这是正常行为，不需要报错
        from nonebot.exception import FinishedException
        if isinstance(e, FinishedException):
            pass  # 正常结束
        else:
            logger.error(f"[TextDispatcher] 路由 {cmd_id} 执行异常: {e}")
            import traceback
            traceback.print_exc()