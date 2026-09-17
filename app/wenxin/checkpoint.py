from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.wenxin.types import (
    GeoMode,
    TaskStatus,
    WenxinAnswer,
    WenxinMode,
    WenxinSource,
    WenxinTaskResult,
)


def utc_now_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class WenxinCheckpoint:
    """文心批次断点存储。"""

    def __init__(
            self,
            *,
            root_dir: str | Path,
            batch_id: str,
            product_id: str,
            product_name: str,
    ) -> None:
        self.batch_id = batch_id
        self.product_id = product_id
        self.product_name = product_name

        self.batch_dir = (
                Path(root_dir)
                / batch_id
        )

        self.results_dir = (
                self.batch_dir
                / "results"
        )

        self.meta_path = (
                self.batch_dir
                / "batch_meta.json"
        )

        self.results_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ============================================================
    # JSON
    # ============================================================

    @staticmethod
    def _write_json_atomic(
            path: Path,
            data: dict,
    ) -> None:
        """
        先写临时文件，再 replace，
        避免写一半程序被中断导致 JSON 损坏。
        """

        temp_path = path.with_suffix(
            path.suffix + ".tmp"
        )

        temp_path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temp_path.replace(
            path
        )

    @staticmethod
    def _read_json(
            path: Path,
    ) -> dict:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    # ============================================================
    # Result path
    # ============================================================

    def result_path(
            self,
            task_id: str,
    ) -> Path:
        return (
                self.results_dir
                / f"{task_id}.json"
        )

    # ============================================================
    # Batch meta
    # ============================================================

    def start(
            self,
            planned_count: int,
    ) -> None:
        """创建或恢复 batch_meta。"""

        if self.meta_path.exists():
            meta = self._read_json(
                self.meta_path
            )

            meta["status"] = "running"
            meta["planned_count"] = (
                planned_count
            )

            # 恢复执行时，旧的结束时间作废
            meta["finished_at"] = None

            meta["updated_at"] = (
                utc_now_iso()
            )

        else:
            now = utc_now_iso()

            meta = {
                "batch_id": self.batch_id,
                "product_id": self.product_id,
                "product_name": self.product_name,
                "started_at": now,
                "finished_at": None,
                "status": "running",
                "planned_count": planned_count,
                "completed_count": 0,
                "success_count": 0,
                "failed_count": 0,
                "updated_at": now,
            }

        self._write_json_atomic(
            self.meta_path,
            meta,
        )

        self.refresh_meta()

    def refresh_meta(
            self,
            *,
            status: str | None = None,
    ) -> None:
        if self.meta_path.exists():
            meta = self._read_json(
                self.meta_path
            )
        else:
            meta = {
                "batch_id": self.batch_id,
                "product_id": self.product_id,
                "product_name": self.product_name,
                "planned_count": 0,
                "started_at": utc_now_iso(),
            }

        results = (
            self.load_all_results()
        )

        success_count = sum(
            result.status
            == TaskStatus.SUCCESS
            for result in results
        )

        failed_count = sum(
            result.status
            == TaskStatus.FAILED
            for result in results
        )

        meta[
            "completed_count"
        ] = len(results)

        meta[
            "success_count"
        ] = success_count

        meta[
            "failed_count"
        ] = failed_count

        meta[
            "updated_at"
        ] = utc_now_iso()

        if status is not None:
            meta["status"] = status

        self._write_json_atomic(
            self.meta_path,
            meta,
        )

    def mark_completed(
            self,
    ) -> None:
        self.refresh_meta()

        meta = self._read_json(
            self.meta_path
        )

        if (
                meta.get(
                    "failed_count",
                    0,
                )
                > 0
        ):
            meta["status"] = (
                "completed_with_errors"
            )
        else:
            meta["status"] = (
                "completed"
            )

        meta["finished_at"] = (
            utc_now_iso()
        )

        meta["updated_at"] = (
            utc_now_iso()
        )

        self._write_json_atomic(
            self.meta_path,
            meta,
        )

    def mark_interrupted(
            self,
    ) -> None:
        self.refresh_meta(
            status="interrupted"
        )

    # ============================================================
    # Serialization
    # ============================================================

    @staticmethod
    def _result_to_dict(
            result: WenxinTaskResult,
    ) -> dict:
        answer_data = None

        if result.answer:
            answer = result.answer

            answer_data = {
                "question": (
                    answer.question
                ),
                "text": (
                    answer.text
                ),
                "raw_text": (
                    answer.raw_text
                ),
                "session_id": (
                    answer.session_id
                ),
                "mode": (
                    answer.mode.value
                ),
                "conversation_url": (
                    answer.conversation_url
                ),
                "collected_at": (
                    answer.collected_at
                ),
                "model_name": (
                    answer.model_name
                ),
                "deep_search": (
                    answer.deep_search
                ),
                "sources": [
                    {
                        "rank": source.rank,
                        "title": source.title,
                        "url": source.url,
                        "domain": source.domain,
                        "tags": source.tags,
                    }
                    for source
                    in answer.sources
                ],
            }

        return {
            "task_id": result.task_id,
            "question_id": (
                result.question_id
            ),
            "question": (
                result.question
            ),
            "geo_mode": (
                result.geo_mode.value
            ),
            "mode": (
                result.mode.value
            ),
            "status": (
                result.status.value
            ),
            "error": (
                result.error
            ),
            "answer": answer_data,
        }

    @staticmethod
    def _result_from_dict(
            data: dict,
    ) -> WenxinTaskResult:
        answer_data = data.get(
            "answer"
        )

        answer = None

        if answer_data:
            sources = [
                WenxinSource(
                    rank=int(
                        source["rank"]
                    ),
                    title=str(
                        source.get(
                            "title"
                        )
                        or ""
                    ),
                    url=str(
                        source.get(
                            "url"
                        )
                        or ""
                    ),
                    domain=str(
                        source.get(
                            "domain"
                        )
                        or ""
                    ),
                    tags=list(
                        source.get(
                            "tags"
                        )
                        or []
                    ),
                )
                for source
                in answer_data.get(
                    "sources",
                    [],
                )
            ]

            answer = WenxinAnswer(
                question=str(
                    answer_data.get(
                        "question"
                    )
                    or ""
                ),
                text=str(
                    answer_data.get(
                        "text"
                    )
                    or ""
                ),
                raw_text=str(
                    answer_data.get(
                        "raw_text"
                    )
                    or ""
                ),
                session_id=str(
                    answer_data.get(
                        "session_id"
                    )
                    or ""
                ),
                mode=WenxinMode(
                    answer_data[
                        "mode"
                    ]
                ),
                conversation_url=str(
                    answer_data.get(
                        "conversation_url"
                    )
                    or ""
                ),
                collected_at=str(
                    answer_data.get(
                        "collected_at"
                    )
                    or ""
                ),
                model_name=(
                    answer_data.get(
                        "model_name"
                    )
                ),
                deep_search=(
                    answer_data.get(
                        "deep_search"
                    )
                ),
                sources=sources,
            )

        return WenxinTaskResult(
            task_id=str(
                data["task_id"]
            ),
            question_id=str(
                data.get(
                    "question_id"
                )
                or ""
            ),
            question=str(
                data["question"]
            ),
            geo_mode=GeoMode(
                data["geo_mode"]
            ),
            mode=WenxinMode(
                data["mode"]
            ),
            status=TaskStatus(
                data["status"]
            ),
            answer=answer,
            error=data.get(
                "error"
            ),
        )

    # ============================================================
    # Save / Load
    # ============================================================

    def save_result(
            self,
            result: WenxinTaskResult,
    ) -> None:
        path = self.result_path(
            result.task_id
        )

        self._write_json_atomic(
            path,
            self._result_to_dict(
                result
            ),
        )

        self.refresh_meta()

    def load_result(
            self,
            task_id: str,
    ) -> WenxinTaskResult | None:
        path = self.result_path(
            task_id
        )

        if not path.exists():
            return None

        data = self._read_json(
            path
        )

        return self._result_from_dict(
            data
        )

    def load_all_results(
            self,
    ) -> list[WenxinTaskResult]:
        results: list[
            WenxinTaskResult
        ] = []

        for path in sorted(
                self.results_dir.glob(
                    "*.json"
                )
        ):
            data = self._read_json(
                path
            )

            results.append(
                self._result_from_dict(
                    data
                )
            )

        return results

    def load_success(
            self,
            task_id: str,
    ) -> WenxinTaskResult | None:
        result = self.load_result(
            task_id
        )

        if (
                result is not None
                and result.status
                == TaskStatus.SUCCESS
        ):
            return result

        return None
