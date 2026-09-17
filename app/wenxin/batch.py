from __future__ import annotations

from app.wenxin.checkpoint import (
    WenxinCheckpoint,
)
from app.wenxin.client import (
    WenxinClient,
)
from app.wenxin.types import (
    TaskStatus,
    WenxinTask,
    WenxinTaskResult,
)


class WenxinBatchRunner:
    """文心批量任务执行器。"""

    def __init__(
            self,
            client: WenxinClient,
            checkpoint: (
                    WenxinCheckpoint
                    | None
            ) = None,
    ) -> None:
        self.client = client
        self.checkpoint = checkpoint

    def run(
            self,
            tasks: list[WenxinTask],
            *,
            planned_count: int | None = None,
            finalize_checkpoint: bool = True,
    ) -> list[WenxinTaskResult]:
        """顺序执行一批文心采集任务。"""

        results: list[
            WenxinTaskResult
        ] = []

        total = len(tasks)

        if self.checkpoint:
            self.checkpoint.start(
                planned_count=(
                    planned_count
                    if planned_count is not None
                    else total
                )
            )

        try:
            for index, task in enumerate(
                    tasks,
                    start=1,
            ):
                print(
                    "\n"
                    + "=" * 80
                )

                print(
                    f"[WENXIN BATCH] "
                    f"{index}/{total}"
                )

                print(
                    "TASK ID:",
                    task.task_id,
                )

                print(
                    "QUESTION:",
                    task.question,
                )

                print(
                    "=" * 80
                )

                # ================================================
                # Checkpoint resume
                # ================================================

                cached = None

                if self.checkpoint:
                    cached = (
                        self.checkpoint
                        .load_success(
                            task.task_id
                        )
                    )

                if cached:
                    print(
                        "[CHECKPOINT] "
                        "已成功，跳过重新采集"
                    )

                    if cached.answer:
                        print(
                            "[RESTORED] "
                            f"answer="
                            f"{len(cached.answer.text)} "
                            f"sources="
                            f"{len(cached.answer.sources)} "
                            f"session="
                            f"{cached.answer.session_id}"
                        )

                    results.append(
                        cached
                    )

                    continue

                # ================================================
                # Real collection
                # ================================================

                try:
                    answer = (
                        self.client.collect(
                            question=(
                                task.question
                            ),
                            mode=task.mode,
                        )
                    )

                    result = (
                        WenxinTaskResult(
                            task_id=(
                                task.task_id
                            ),
                            question_id=(
                                task.question_id
                            ),
                            question=(
                                task.question
                            ),
                            geo_mode=(
                                task.geo_mode
                            ),
                            mode=(
                                task.mode
                            ),
                            status=(
                                TaskStatus.SUCCESS
                            ),
                            answer=answer,
                        )
                    )

                    print(
                        "[SUCCESS] "
                        f"answer="
                        f"{len(answer.text)} "
                        f"sources="
                        f"{len(answer.sources)} "
                        f"session="
                        f"{answer.session_id}"
                    )

                except Exception as exc:
                    result = (
                        WenxinTaskResult(
                            task_id=(
                                task.task_id
                            ),
                            question_id=(
                                task.question_id
                            ),
                            question=(
                                task.question
                            ),
                            geo_mode=(
                                task.geo_mode
                            ),
                            mode=(
                                task.mode
                            ),
                            status=(
                                TaskStatus.FAILED
                            ),
                            error=str(exc),
                        )
                    )

                    print(
                        "[FAILED]",
                        repr(exc),
                    )

                results.append(
                    result
                )

                # ================================================
                # 每题立即落盘
                # ================================================

                if self.checkpoint:
                    self.checkpoint.save_result(
                        result
                    )

                # ================================================
                # 任务间缓冲
                # ================================================

                if index < total:
                    self.client._random_action_delay(
                        1.0,
                        2.0,
                    )

        except BaseException:
            if self.checkpoint:
                self.checkpoint.mark_interrupted()

            raise

        if self.checkpoint:
            if finalize_checkpoint:
                self.checkpoint.mark_completed()
            else:
                self.checkpoint.refresh_meta(
                    status="partial"
                )

        return results
