from __future__ import annotations

from enum import Enum
from pathlib import Path

from app.wenxin.checksum import (
    generate_checksums,
)
from app.wenxin.geo_contract import (
    COLLECTOR_VERSION,
    GEO_BATCH_VERSION,
    GEO_SCHEMA_VERSION,
    WENXIN_PLATFORM_CODE,
    WENXIN_PLATFORM_NAME,
    build_answer_id,
    build_occurrence_id,
    build_task_id,
)
from app.wenxin.serialization import (
    write_json,
    write_jsonl,
)
from app.wenxin.types import (
    TaskStatus,
    WenxinTaskResult,
)


PACKAGE_FILES = (
    "manifest.json",
    "tasks.jsonl",
    "answers.jsonl",
    "sources.jsonl",
    "checksums.json",
)


def _value(value) -> str:
    """
    同时兼容 Enum 和普通字符串。
    """

    if isinstance(
        value,
        Enum,
    ):
        return str(
            value.value
        )

    return str(value)


class WenxinExporter:
    """
    将文心批量采集结果导出为
    GEO geo_package_v1 标准目录。
    """

    def export(
        self,
        *,
        results: list[WenxinTaskResult],
        output_dir: str | Path,
        batch_id: str,
        product_id: str,
        product_name: str,
        started_at: str = "",
        finished_at: str = "",
    ) -> Path:
        if not batch_id.strip():
            raise ValueError(
                "batch_id 不能为空"
            )

        if not product_id.strip():
            raise ValueError(
                "product_id 不能为空"
            )

        if not product_name.strip():
            raise ValueError(
                "product_name 不能为空"
            )

        output = Path(
            output_dir
        )

        output.mkdir(
            parents=True,
            exist_ok=True,
        )

        task_rows: list[dict] = []
        answer_rows: list[dict] = []
        source_rows: list[dict] = []

        for result in results:
            if not result.question_id:
                raise ValueError(
                    "WenxinTaskResult.question_id "
                    "不能为空"
                )

            geo_mode = _value(
                result.geo_mode
            )

            task_id = build_task_id(
                batch_id=batch_id,
                question_id=(
                    result.question_id
                ),
                mode_code=geo_mode,
            )

            task_status = _value(
                result.status
            )

            task_rows.append(
                {
                    "task_id": task_id,
                    "batch_id": batch_id,
                    "platform_code": (
                        WENXIN_PLATFORM_CODE
                    ),
                    "question_id": (
                        result.question_id
                    ),
                    "question": (
                        result.question
                    ),
                    "mode_code": geo_mode,
                    "task_status": (
                        task_status
                    ),
                    "error_code": (
                        None
                        if (
                            result.status
                            == TaskStatus.SUCCESS
                        )
                        else (
                            "collection_failed"
                        )
                    ),
                    "error_message": (
                        result.error
                        or None
                    ),
                }
            )

            # 失败任务没有回答，
            # 只保留 tasks.jsonl。
            if result.answer is None:
                continue

            answer = result.answer

            answer_id = build_answer_id(
                batch_id=batch_id,
                task_id=task_id,
            )

            clean_text = (
                answer.text.strip()
                if answer.text
                else ""
            )

            raw_text = (
                answer.raw_text
                if answer.raw_text
                else answer.text
            )

            valid_sources = [
                source
                for source in answer.sources
                if source.url.strip()
            ]

            platform_meta = {
                "collector_task_id": (
                    result.task_id
                ),
                "session_id": (
                    answer.session_id
                ),
                "model": (
                    answer.model_name
                ),
                "raw_mode": _value(
                    answer.mode
                ),
                "deep_search": (
                    answer.deep_search
                ),
                "conversation_url": (
                    answer.conversation_url
                ),
            }

            answer_rows.append(
                {
                    "answer_id": (
                        answer_id
                    ),
                    "task_id": (
                        task_id
                    ),
                    "question_id": (
                        result.question_id
                    ),
                    "mode_code": (
                        geo_mode
                    ),
                    "question_text": (
                        result.question
                    ),
                    "answer_text_raw": (
                        raw_text
                    ),
                    "answer_text_clean": (
                        clean_text
                    ),
                    "acquisition_status": (
                        "success"
                    ),
                    "validation_status": (
                        "PASS"
                        if clean_text
                        else "FAIL"
                    ),
                    "is_complete": (
                        bool(clean_text)
                    ),
                    "source_collection_status": (
                        "success"
                    ),
                    "source_count_raw": (
                        len(
                            valid_sources
                        )
                    ),
                    "screenshot_path": (
                        None
                    ),
                    "platform_meta_json": (
                        platform_meta
                    ),
                    "collected_at": (
                        answer.collected_at
                        or None
                    ),
                    "batch_id": (
                        batch_id
                    ),
                    "platform_code": (
                        WENXIN_PLATFORM_CODE
                    ),
                }
            )

            seen_urls: set[str] = set()

            for source in valid_sources:
                source_url = (
                    source.url.strip()
                )

                is_duplicate = (
                    source_url
                    in seen_urls
                )

                seen_urls.add(
                    source_url
                )

                source_order = int(
                    source.rank
                )

                occurrence_id = (
                    build_occurrence_id(
                        batch_id=(
                            batch_id
                        ),
                        answer_id=(
                            answer_id
                        ),
                        source_order=(
                            source_order
                        ),
                        source_url_raw=(
                            source_url
                        ),
                    )
                )

                source_rows.append(
                    {
                        "answer_id": (
                            answer_id
                        ),
                        "source_order": (
                            source_order
                        ),
                        "source_url_raw": (
                            source_url
                        ),
                        "source_title_raw": (
                            source.title
                            or None
                        ),
                        "source_site_name_raw": (
                            source.domain
                            or None
                        ),
                        "source_snippet": (
                            None
                        ),
                        "is_duplicate_in_answer": (
                            is_duplicate
                        ),
                        "occurrence_id": (
                            occurrence_id
                        ),
                    }
                )

        # -------------------------------------------------
        # JSONL
        # -------------------------------------------------

        write_jsonl(
            output / "tasks.jsonl",
            task_rows,
        )

        write_jsonl(
            output / "answers.jsonl",
            answer_rows,
        )

        # 即使没有来源，
        # sources.jsonl 也必须存在。
        write_jsonl(
            output / "sources.jsonl",
            source_rows,
        )

        # -------------------------------------------------
        # Manifest
        # -------------------------------------------------

        success_count = sum(
            1
            for result in results
            if (
                result.status
                == TaskStatus.SUCCESS
            )
        )

        failed_count = (
            len(results)
            - success_count
        )

        collection_modes = sorted(
            {
                _value(
                    result.geo_mode
                )
                for result
                in results
            }
        )

        manifest = {
            "schema_version": (
                GEO_SCHEMA_VERSION
            ),
            "geo_batch_version": (
                GEO_BATCH_VERSION
            ),
            "platform_code": (
                WENXIN_PLATFORM_CODE
            ),
            "platform_name": (
                WENXIN_PLATFORM_NAME
            ),
            "product_id": (
                product_id
            ),
            "product_name": (
                product_name
            ),
            "batch_id": (
                batch_id
            ),
            "collector_version": (
                COLLECTOR_VERSION
            ),
            "capabilities": {
                "supports_sources": True,

                # 当前网页实际只确认：
                # GEO quick -> 文心 fast
                "supports_multiple_modes": (
                    False
                ),

                "supports_screenshot": False,
            },
            "status": (
                "PASS"
                if failed_count == 0
                else "PASS_WITH_WARNINGS"
            ),
            "task_count": (
                len(task_rows)
            ),
            "answer_count": (
                len(answer_rows)
            ),
            "source_count": (
                len(source_rows)
            ),
            "success_tasks": (
                success_count
            ),
            "failed_tasks": (
                failed_count
            ),
            "collection_modes": (
                collection_modes
            ),
        }

        if started_at:
            manifest[
                "started_at"
            ] = started_at

        if finished_at:
            manifest[
                "finished_at"
            ] = finished_at

        write_json(
            output / "manifest.json",
            manifest,
        )

        # -------------------------------------------------
        # SHA-256
        # -------------------------------------------------

        checksum_files = [
            output / "manifest.json",
            output / "tasks.jsonl",
            output / "answers.jsonl",
            output / "sources.jsonl",
        ]

        checksums = (
            generate_checksums(
                checksum_files
            )
        )

        write_json(
            output / "checksums.json",
            checksums,
        )

        return output