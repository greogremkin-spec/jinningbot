"""
晋宁会馆·秃贝五边形 4.1
互斥锁系统

防止冲突操作（如派遣期间不能聚灵）
"""

import time
from src.common.data_manager import data_manager
from src.common.utils import format_duration


class MutexError(Exception):
    """互斥锁异常"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def check_mutex(user_id: str, action_type: str):
    """
    检查用户状态是否允许执行某动作

    :param user_id: 用户QQ号
    :param action_type: 动作类型
        - 'meditation': 聚灵（受派遣锁影响）
        - 'entertainment': 娱乐（受派遣锁影响）
        - 'kitchen': 厨房（受派遣锁影响）
        - 'resonance': 鉴定（受派遣锁影响）
        - 'garden': 药圃（不受派遣锁影响）
        - 'registry': 登记（不受任何锁影响）
    :raises MutexError: 如果被锁
    """
    # 药圃和登记不受派遣锁影响
    if action_type in ("garden", "registry"):
        return True

    spirit_data = await data_manager.get_spirit_data(user_id)

    # 检查派遣状态
    expedition = spirit_data.get("expedition", {})
    if expedition.get("status") == "exploring":
        locked_actions = {"meditation", "entertainment", "kitchen", "resonance"}
        if action_type in locked_actions:
            loc = expedition.get("location", "未知之地")
            end_time = expedition.get("end_time", 0)
            remaining = int(end_time - time.time())

            if remaining > 0:
                time_str = format_duration(remaining)
                raise MutexError(
                    f"🚫 你的灵体正在【{loc}】探索中！\n"
                    f"⏳ 剩余时间：{time_str}\n"
                    f"💡 可使用 /召回 强制返回（消耗5灵力）"
                )

    return True