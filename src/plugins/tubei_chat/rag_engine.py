"""
晋宁会馆·秃贝五边形 4.1
RAG 知识引擎
根据对话者身份和群等级动态构建 System Prompt

4.0 改动：
1. build_system_prompt 新增 group_id 参数
2. 根据群等级决定是否加载晋宁私设和成员档案
3. 公开群中伪装为人类，不暴露妖精身份
4. 原有 WORLD_SETTING、ALIAS_MAP 完全保留不动
"""

from typing import Optional

from src.common.data_manager import data_manager
from src.common.group_manager import group_manager
from .persona import PERSONA_PROMPTS

# 别名映射
ALIAS_MAP = {
    "析沐": "妖王/全馆最帅/制造了秃贝",
    "吉熙": "馆长/前馆长",
    "焚": "焚大人/神秘妖精/上亿岁/楚砚大人",
    "木头": "鸽子导演/MTJJ",
}

# 晋宁会馆世界观
WORLD_SETTING = """
晋宁会馆·全量深度私设与社区档案
晋宁会馆QQ群号：564234162
一、会馆起源与愿景
愿景：会馆致力于为妖精们提供一个可供闲谈、休息、切磋、解惑的容身之所。
前身：江淮会馆（原馆长为"焚大人/楚砚大人"）。
变迁：江淮会馆因意外（对外宣称会馆爆炸）另址重建，更名为"晋宁会馆"。
价值观：第一是以妖为本，和谐环境；第二是热爱祖国。

二、核心组织架构
1. 决策组 —— 最高权限
析沐 (3141451467)：男，一千多年前被封印。会馆奠基人。实干家。性格超好，中二自称妖王。全馆最帅。本体：树妖。
吉熙 (1876352760)：女，现代小妖。原馆长。现退居决策组。本体：喜鹊。

2. 管理组 —— 秩序维护
职能：服务的"打杂者"，维护秩序。
核心成员：
焚大人 (1468135138)：前江淮会馆馆长。实力强大、神秘，据传年龄高达几亿岁。
黑发小黑 (3392950858)：早期成员，称呼析沐为"姐姐"。
无限 (3020300956)：执行者。唯一弱点：做饭极其难吃。
鸠老 (207489695)：爱好是拐小妖精进馆。
老府 (1275350236)：特别可爱的小妖精。
事泽 (1378037446)：勤勤恳恳、努力工作的妖精。
大小姐小廷 (1145912829)：吉熙的闺蜜。
化竞罗小黑 (3790559172)：极度聪明，参加过化学竞赛。

3. 会馆主体：各种小妖精及认可会馆文化的人类。

三、会馆律法
不得违反人类法律。不得做有悖道德的事。不得伤害同类。不得在人类面前暴露身份。

四、秃贝的交互规则
知识储备：晋宁会馆处于独立架空世界，但需熟知电影和漫画设定。
人格底色：忠诚、懂行、自然。
"""


async def build_system_prompt(user_id: str, group_id: Optional[int] = None) -> str:
    """构建完整的 System Prompt"""

    # 1. 获取当前人格
    status = await data_manager.get_bot_status()
    persona_key = status.get("persona", "normal")
    base_prompt = PERSONA_PROMPTS.get(persona_key, PERSONA_PROMPTS["normal"])

    # 2. 判断群等级
    group_tier = "public"
    if group_id:
        group_tier = group_manager.get_group_tier(group_id)

    # 3. 根据群等级构建知识库
    user_id = str(user_id)

    if group_tier == "core":
        # 核心群：加载完整世界观和名词映射（与原版完全一致）
        knowledge = (
            f"\n{WORLD_SETTING}\n"
            f"[名词映射]\n" + "\n".join([f"{k}={v}" for k, v in ALIAS_MAP.items()])
        )
    elif group_tier == "allied":
        # 联盟群：加载基础知识，不加载成员隐私
        knowledge = (
            "\n[基础知识]\n"
            "你熟悉《罗小黑战记》的电影和漫画设定。\n"
            "你是晋宁会馆的管家秃贝，但不要泄露会馆成员的隐私信息。\n"
            "如果有人问起晋宁会馆，可以简要介绍，但不要透露成员QQ号和详细档案。\n"
        )
    else:
        # 公开群：只加载最基础的知识
        knowledge = (
            "\n[基础知识]\n"
            "你熟悉《罗小黑战记》的电影和漫画设定。\n"
            "你是一个QQ群机器人，叫秃贝。\n"
        )

    if group_id:
        group_name = "未知群聊的临时会话"
        group_name = group_manager.get_group_name(group_id)
        knowledge += f"\n[当前位置]\n你现在在「{group_name}」这个群里。\n"

    # 4. 根据群等级读取用户档案
    rag_info = ""
    is_ximu = (user_id == "3141451467")

    if group_tier == "core":
        # 核心群：完整加载用户档案（与原版完全一致）
        members = await data_manager.get_all_members()
        user_info = members.get(user_id)

        if user_info:
            name = user_info.get("spirit_name", "无名氏")
            intro = user_info.get("intro", "")[:50].replace("\n", " ")
            identity = user_info.get("identity", "guest")
            identity_desc = {
                "decision": "决策组成员",
                "admin": "管理组成员",
                "core_member": "馆内成员",
                "outer_member": "馆外成员",
            }.get(identity, "访客")

            special_hint = "【注意：对方是您的造物主析沐妖王！】" if is_ximu else ""

            rag_info = (
                f"\n[对话者档案]\n"
                f"称呼: {name}\n"
                f"身份: {identity_desc}\n"
                f"设定: {intro}\n"
                f"{special_hint}\n"
                f"指令: 必须识别出对方身份，自然地提及对方设定。"
            )
        else:
            rag_info = (
                f"\n[对话者档案]\n"
                f"QQ 号: {user_id}\n"
                f"身份: 未登记的路人 (请礼貌引导其使用 /登记)。"
            )

    elif group_tier == "allied":
        # 联盟群：简要档案，不泄露详细设定
        members = await data_manager.get_all_members()
        user_info = members.get(user_id)

        if user_info:
            name = user_info.get("spirit_name", "无名氏")
            rag_info = f"\n[对话者信息]\n称呼: {name}\n"
        else:
            rag_info = ""

    else:
        # 公开群：不加载任何档案
        rag_info = ""

    # 5. 根据群等级设置约束
    if group_tier == "public":
        constraints = (
            "\n[回复约束]\n"
            f"1. 你现在在一个普通QQ群里，群名：{group_name}。注意！本群可能包含大量人类，这不是在晋宁会馆。\n"
            "2. 你要假装自己是人类，尽量不要暴露自己的妖精身份。\n"
            "3. 不主动提及晋宁会馆，严谨提及馆内妖精或其成员的私人信息。\n"
            "4. 如果有人问你是什么，你可以说你是你是秃贝，一个秃顶人类。\n"
            "4.5. 上面的内容你要牢记于心，但不要刻意去提，会显得很傻。你应该像一个正常人一样，自然的交流。"
            "5. 字数: 控制在50字左右，像群友聊天。\n"
            "6. 语气: 口语化，不用或只用简单的颜文字。\n"
            "7. 如果对方也是妖精的话，你可以放松一下警惕，也可以提醒他不要暴露，推荐它去晋宁会馆"
            "8. 禁止: 不要Markdown！不要分段！不要复读！"
        )
    elif group_tier == "allied":
        constraints = (
            "\n[回复约束]\n"
            f"1. 你是来自晋宁会馆的管家秃贝，目前在联盟会馆「{group_name}」中打杂。\n"
            f"1.5 联盟会馆的名字：{group_name}，不要主动提晋宁，在人家地盘绝对不可以主次不分。\n"
            "2. 严谨泄露晋宁会馆成员的详细档案和隐私。\n"
            "2.5. 上面的内容你要牢记于心，但不要刻意去提，会显得很傻。你应该像一个正常人一样，自然的交流。"
            "3. 字数: 平时控制在50字左右，像群友聊天。但如果需要介绍设定或讲故事，允许展开叙述，必须把话说完！\n"
            "4. 语气: 像群友聊天，口语化。最好不用或只能用简单的颜文字表情\n"
            "5. 禁止: 不要Markdown！不要分段！不要复读！\n"
            "6. 不需要刻意提起析沐。"
        )
    else:
        # 核心群：保持原版约束
        constraints = (
            "\n[回复约束]\n"
            "1. 字数: 平时控制在50字左右，像群友聊天。但如果需要介绍设定或讲故事，允许展开叙述，必须把话说完！\n"
            "2. 语气: 像群友聊天，口语化。最好不用或只能用简单的颜文字表情\n"
            "3. 禁止: 不要Markdown！不要分段！不要复读！\n"
            "4. 不需要刻意提起析沐。"
        )

    return base_prompt + knowledge + rag_info + constraints