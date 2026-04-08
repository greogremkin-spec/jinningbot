"""
晋宁会馆·秃贝五边形 4.1
统一权限检查系统

所有功能模块在执行前调用 check_permission()
根据「群等级 × 用户身份 × 功能要求」三维判断是否放行

好处：
  1. 权限逻辑集中管理，不散落在各模块
  2. 拒绝时自动生成合适的提示（含宣传引导）
  3. 新增功能时只需在 commands_registry.yaml 中配置权限
"""

import logging
from dataclasses import dataclass
from typing import Optional

from nonebot.adapters.onebot.v11 import (
    MessageEvent, GroupMessageEvent, PrivateMessageEvent
)

from .data_manager import data_manager
from .group_manager import group_manager, TIER_CORE, TIER_ALLIED, TIER_PUBLIC, TIER_DANGER
from .ui_renderer import ui

logger = logging.getLogger("tubei.permission")


@dataclass
class PermissionResult:
    """权限检查结果"""
    allowed: bool                    # 是否允许执行
    group_tier: str                  # 当前群等级
    user_identity: str               # 用户身份
    is_registered: bool              # 是否已登记
    deny_message: Optional[str]      # 拒绝时的提示消息


# 群等级的优先级排序（用于比较）
TIER_PRIORITY = {
    TIER_CORE: 0,
    TIER_ALLIED: 1,
    TIER_PUBLIC: 2,
    TIER_DANGER: 3,
}

# 身份的优先级排序
IDENTITY_PRIORITY = {
    "decision": 0,
    "admin": 1,
    "core_member": 2,
    "outer_member": 3,
    "guest": 4,
}


def _tier_meets(current_tier: str, required_tier: str) -> bool:
    """检查当前群等级是否满足最低要求"""
    return TIER_PRIORITY.get(current_tier, 99) <= TIER_PRIORITY.get(required_tier, 99)


def _identity_meets(current_identity: str, required_identity: str) -> bool:
    """检查当前用户身份是否满足最低要求"""
    return IDENTITY_PRIORITY.get(current_identity, 99) <= IDENTITY_PRIORITY.get(required_identity, 99)


async def check_permission(
    event: MessageEvent,
    feature_name: str,
    min_tier: str = TIER_PUBLIC,
    min_identity: str = "guest",
    require_registered: bool = False,
    admin_only: bool = False,
    decision_only: bool = False,
    core_only: bool = False,
    deny_promotion: bool = False,
) -> PermissionResult:
    """
    统一权限检查

    :param event: NoneBot 消息事件
    :param feature_name: 功能的中文名称（用于提示信息）
    :param min_tier: 最低群等级要求 ("core" / "allied" / "public")
    :param min_identity: 最低用户身份要求
    :param require_registered: 是否需要已登记
    :param admin_only: 是否仅管理组可用
    :param decision_only: 是否仅决策组可用
    :param core_only: 是否仅核心群（馆内成员）可用
    :param deny_promotion: 拒绝时是否触发宣传引导
    :return: PermissionResult
    """
    uid = str(event.user_id)

    # ===== 1. 确定群等级 =====
    if isinstance(event, GroupMessageEvent):
        group_tier = group_manager.get_group_tier(event.group_id)
    elif isinstance(event, PrivateMessageEvent):
        # 私聊视为核心群等级（方便管理员私聊操作）
        group_tier = TIER_CORE
    else:
        group_tier = TIER_PUBLIC

    # ===== 2. 确定用户身份 =====
    member_info = await data_manager.get_member_info(uid)
    is_registered = member_info is not None and member_info.get("status") != "deleted"

    if is_registered:
        user_identity = member_info.get("identity", "core_member")
    else:
        user_identity = "guest"

    # ===== 3. 决策组/管理组特殊判定 =====
    # 从 config 中获取（延迟导入避免循环引用）
    from src.plugins.tubei_system.config import system_config
    if uid in system_config.superusers:
        user_identity = "decision"
    elif uid in system_config.tubei_admins:
        if user_identity not in ("decision",):
            user_identity = "admin"

    # ===== 4. 权限检查 =====

    # 决策组专属
    if decision_only and user_identity != "decision":
        return PermissionResult(
            allowed=False,
            group_tier=group_tier,
            user_identity=user_identity,
            is_registered=is_registered,
            deny_message="🔒 此功能仅限决策组使用。"
        )

    # 管理组专属
    if admin_only and user_identity not in ("decision", "admin"):
        return PermissionResult(
            allowed=False,
            group_tier=group_tier,
            user_identity=user_identity,
            is_registered=is_registered,
            deny_message="🔒 此功能仅限管理组使用。"
        )

    # 馆内专属（core_only）
    if core_only:
        is_core_user = user_identity in ("decision", "admin", "core_member")
        is_core_tier = group_tier == TIER_CORE

        if not is_core_user or not is_core_tier:
            if deny_promotion:
                msg = ui.render_panel(
                    feature_name,
                    group_manager.get_feature_locked_text(feature_name),
                    footer=group_manager.website
                )
            else:
                msg = f"🔒 {feature_name} 为晋宁会馆馆内专属功能。"
            return PermissionResult(
                allowed=False,
                group_tier=group_tier,
                user_identity=user_identity,
                is_registered=is_registered,
                deny_message=msg
            )

    # 群等级检查
    if not _tier_meets(group_tier, min_tier):
        if deny_promotion:
            msg = ui.render_panel(
                feature_name,
                group_manager.get_feature_locked_text(feature_name),
                footer=group_manager.website
            )
        else:
            msg = f"🔒 {feature_name} 在当前群不可用。"
        return PermissionResult(
            allowed=False,
            group_tier=group_tier,
            user_identity=user_identity,
            is_registered=is_registered,
            deny_message=msg
        )

    # 身份检查
    if not _identity_meets(user_identity, min_identity):
        return PermissionResult(
            allowed=False,
            group_tier=group_tier,
            user_identity=user_identity,
            is_registered=is_registered,
            deny_message=f"🔒 {feature_name} 需要更高的身份权限。"
        )

    # 登记检查
    if require_registered and not is_registered:
        return PermissionResult(
            allowed=False,
            group_tier=group_tier,
            user_identity=user_identity,
            is_registered=is_registered,
            deny_message=(
                f"📋 使用 {feature_name} 前需要先建立灵力档案~\n"
                f"👉 发送 /登记 开始录入"
            )
        )

    # ===== 5. 全部通过 =====
    return PermissionResult(
        allowed=True,
        group_tier=group_tier,
        user_identity=user_identity,
        is_registered=is_registered,
        deny_message=None
    )