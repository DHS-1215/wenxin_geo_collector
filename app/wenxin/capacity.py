from __future__ import annotations

from dataclasses import dataclass

RISK_KEYWORDS = (
    "操作频繁",
    "请求频繁",
    "稍后再试",
    "服务繁忙",
    "系统繁忙",
    "访问受限",
    "安全验证",
    "验证码",
    "登录失效",
    "重新登录",
)


@dataclass(slots=True)
class CapacityResult:
    index: int
    question: str
    success: bool
    elapsed_seconds: float
    answer_length: int = 0
    source_count: int = 0
    session_id: str = ""
    error: str | None = None
    risk_detected: bool = False


def detect_risk(
        *texts: str | None,
) -> bool:
    content = "\n".join(
        text or ""
        for text in texts
    )

    return any(
        keyword in content
        for keyword in RISK_KEYWORDS
    )
