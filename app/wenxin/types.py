from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GeoMode(str, Enum):
    """GEO 标准采集模式。"""

    QUICK = "quick"
    EXPERT = "expert"


class WenxinMode(str, Enum):
    """文心网页真实回答模式。"""

    FAST = "fast"
    TASK = "task"


class AnswerStatus(str, Enum):
    """文心回答生成状态。"""

    GENERATING = "GENERATING"
    COMPLETE = "COMPLETE"


class TaskStatus(str, Enum):
    """单个采集任务执行状态。"""

    SUCCESS = "success"
    FAILED = "failed"


@dataclass(slots=True)
class WenxinSource:
    """单条文心信源。"""

    rank: int
    title: str
    url: str
    domain: str
    tags: list[str] = field(
        default_factory=list
    )


@dataclass(slots=True)
class WenxinAnswer:
    question: str
    text: str
    session_id: str
    mode: WenxinMode
    raw_text: str = ""
    conversation_url: str = ""
    collected_at: str = ""
    model_name: str | None = None
    deep_search: bool | None = None
    sources: list[WenxinSource] = field(
        default_factory=list
    )
    screenshot_path: str | None = None
    screenshot_sha256: str | None = None
    screenshot_size_bytes: int | None = None
    screenshot_width: int | None = None
    screenshot_height: int | None = None


@dataclass(slots=True)
class WenxinTask:
    """单个文心采集任务。"""

    task_id: str
    question: str

    mode: WenxinMode = WenxinMode.FAST

    question_id: str = ""
    geo_mode: GeoMode = GeoMode.QUICK


@dataclass(slots=True)
class WenxinTaskResult:
    """单个文心采集任务执行结果。"""

    task_id: str
    question: str
    status: TaskStatus

    question_id: str = ""
    geo_mode: GeoMode = GeoMode.QUICK
    mode: WenxinMode = WenxinMode.FAST

    answer: WenxinAnswer | None = None
    error: str | None = None

    screenshot_path: str | None = None
    screenshot_sha256: str | None = None
    screenshot_size_bytes: int | None = None
    screenshot_width: int | None = None
    screenshot_height: int | None = None