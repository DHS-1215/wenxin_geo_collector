from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from app.wenxin.types import (
    GeoMode,
    WenxinMode,
    WenxinTask,
)

GEO_MODE_MAPPING = {
    GeoMode.QUICK: WenxinMode.FAST,
}


@dataclass(slots=True)
class SkippedInputTask:
    """因平台能力不支持而跳过的输入任务。"""

    question_id: str
    question: str
    geo_mode: str
    reason: str


@dataclass(slots=True)
class InputLoadResult:
    """题库加载结果。"""

    tasks: list[WenxinTask]
    skipped: list[SkippedInputTask]


def load_tasks(
        csv_path: str | Path,
) -> InputLoadResult:
    """读取 GEO 标准 CSV，并转换为文心任务。"""

    path = Path(csv_path)

    if not path.exists():
        raise FileNotFoundError(
            f"题库不存在: {path}"
        )

    tasks: list[WenxinTask] = []
    skipped: list[SkippedInputTask] = []

    seen_task_ids: set[str] = set()

    with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
    ) as file:
        reader = csv.DictReader(
            file
        )

        required_columns = {
            "question_id",
            "question",
            "mode",
        }

        actual_columns = set(
            reader.fieldnames or []
        )

        missing = (
                required_columns
                - actual_columns
        )

        if missing:
            raise ValueError(
                "CSV 缺少字段: "
                + ", ".join(
                    sorted(missing)
                )
            )

        for row_number, row in enumerate(
                reader,
                start=2,
        ):
            question_id = (
                    row["question_id"]
                    or ""
            ).strip()

            question = (
                    row["question"]
                    or ""
            ).strip()

            raw_mode = (
                    row["mode"]
                    or ""
            ).strip().lower()

            if not question_id:
                raise ValueError(
                    f"第 {row_number} 行 "
                    "question_id 为空"
                )

            if not question:
                raise ValueError(
                    f"第 {row_number} 行 "
                    "question 为空"
                )

            try:
                geo_mode = GeoMode(
                    raw_mode
                )
            except ValueError:
                raise ValueError(
                    f"第 {row_number} 行 "
                    f"存在未知 mode: "
                    f"{raw_mode}"
                )

            wenxin_mode = (
                GEO_MODE_MAPPING.get(
                    geo_mode
                )
            )

            if wenxin_mode is None:
                skipped.append(
                    SkippedInputTask(
                        question_id=question_id,
                        question=question,
                        geo_mode=geo_mode.value,
                        reason=(
                            "文心当前尚未确认该 "
                            "GEO 模式的等价网页模式"
                        ),
                    )
                )

                continue

            task_id = (
                f"{question_id}_"
                f"{geo_mode.value}"
            )

            if task_id in seen_task_ids:
                raise ValueError(
                    f"发现重复 task_id: "
                    f"{task_id}"
                )

            seen_task_ids.add(
                task_id
            )

            tasks.append(
                WenxinTask(
                    task_id=task_id,
                    question_id=question_id,
                    question=question,
                    geo_mode=geo_mode,
                    mode=wenxin_mode,
                )
            )

    return InputLoadResult(
        tasks=tasks,
        skipped=skipped,
    )
