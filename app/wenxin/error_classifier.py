from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.wenxin.exceptions import (
    WenxinLoginRequiredError,
    WenxinQuotaExhaustedError,
    WenxinRiskControlError,
)


class WenxinControlKind(
    str,
    Enum,
):
    QUOTA = "quota"
    RISK_CONTROL = "risk_control"
    LOGIN_REQUIRED = "login_required"


@dataclass(
    frozen=True,
    slots=True,
)
class WenxinControlMatch:
    kind: WenxinControlKind
    pattern: str


QUOTA_PATTERNS = (
    "今日对话次数已达上限",
    "今日使用次数已达上限",
    "今日次数已达上限",
    "今日次数已用完",
    "对话次数已达上限",
    "使用次数已达上限",
    "今日对话额度已用完",
    "今日额度已用完",
    "暂无可用次数",
    "当前账号暂无可用次数",
    "本次服务次数已用完",
)


RISK_PATTERNS = (
    "操作频繁",
    "请求频繁",
    "访问过于频繁",
    "访问受限",
    "检测到异常访问",
    "请完成安全验证",
    "请进行安全验证",
    "需要完成安全验证",
    "需要进行安全验证",
    "请输入验证码",
    "服务繁忙",
    "系统繁忙",
)


LOGIN_PATTERNS = (
    "请先登录",
    "登录后继续",
    "登录已失效",
    "登录状态已失效",
    "当前账号已退出",
    "请重新登录",
    "重新登录后继续",
)


def normalize_control_text(
    text: str | None,
) -> str:
    if not text:
        return ""

    return " ".join(
        text.strip().split()
    )


def _match_patterns(
    text: str,
    patterns: tuple[str, ...],
) -> str | None:
    for pattern in patterns:
        if pattern in text:
            return pattern

    return None


def classify_wenxin_text(
    *texts: str | None,
) -> WenxinControlMatch | None:
    """
    从回答、错误信息或页面提示中识别
    需要改变批次执行流程的异常。

    优先级：
    quota > risk > login

    安全验证同时出现“重新登录”时，
    应按 risk 处理，而不是普通登录失效。
    """

    content = normalize_control_text(
        "\n".join(
            text or ""
            for text in texts
        )
    )

    if not content:
        return None

    quota_pattern = _match_patterns(
        content,
        QUOTA_PATTERNS,
    )

    if quota_pattern:
        return WenxinControlMatch(
            kind=WenxinControlKind.QUOTA,
            pattern=quota_pattern,
        )

    risk_pattern = _match_patterns(
        content,
        RISK_PATTERNS,
    )

    if risk_pattern:
        return WenxinControlMatch(
            kind=(
                WenxinControlKind
                .RISK_CONTROL
            ),
            pattern=risk_pattern,
        )

    login_pattern = _match_patterns(
        content,
        LOGIN_PATTERNS,
    )

    if login_pattern:
        return WenxinControlMatch(
            kind=(
                WenxinControlKind
                .LOGIN_REQUIRED
            ),
            pattern=login_pattern,
        )

    return None


def raise_for_wenxin_control(
    *texts: str | None,
) -> None:
    match = classify_wenxin_text(
        *texts
    )

    if match is None:
        return

    if (
        match.kind
        == WenxinControlKind.QUOTA
    ):
        raise WenxinQuotaExhaustedError(
            "检测到文心账号额度耗尽："
            f"{match.pattern}"
        )

    if (
        match.kind
        == WenxinControlKind.RISK_CONTROL
    ):
        raise WenxinRiskControlError(
            "检测到文心风控或安全验证："
            f"{match.pattern}"
        )

    if (
        match.kind
        == WenxinControlKind.LOGIN_REQUIRED
    ):
        raise WenxinLoginRequiredError(
            "检测到文心登录状态异常："
            f"{match.pattern}"
        )