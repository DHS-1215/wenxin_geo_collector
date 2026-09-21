from __future__ import annotations

from dataclasses import dataclass

from app.wenxin.error_classifier import (
    classify_wenxin_text,
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
    return (
            classify_wenxin_text(
                *texts
            )
            is not None
    )
