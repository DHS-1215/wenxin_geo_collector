from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

from app.wenxin.geo_contract import (
    GEO_BATCH_VERSION,
    GEO_SCHEMA_VERSION,
    WENXIN_PLATFORM_CODE,
)


PACKAGE_FILES = {
    "manifest.json",
    "tasks.jsonl",
    "answers.jsonl",
    "sources.jsonl",
    "checksums.json",
}

CHECKSUM_FILES = {
    "manifest.json",
    "tasks.jsonl",
    "answers.jsonl",
    "sources.jsonl",
}


def _sha256_bytes(
    data: bytes,
) -> str:
    return hashlib.sha256(
        data
    ).hexdigest()


def _read_json_bytes(
    data: bytes,
    file_name: str,
) -> dict:
    try:
        value = json.loads(
            data.decode("utf-8")
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            f"无效 JSON: {file_name}"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"{file_name} 顶层必须是对象"
        )

    return value


def _read_jsonl_bytes(
    data: bytes,
    file_name: str,
) -> list[dict]:
    try:
        text = data.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"无效 UTF-8: {file_name}"
        ) from exc

    rows: list[dict] = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            row = json.loads(
                line
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"无效 JSONL: "
                f"{file_name}, "
                f"line={line_number}"
            ) from exc

        if not isinstance(
            row,
            dict,
        ):
            raise ValueError(
                f"{file_name} "
                f"第 {line_number} 行"
                "必须是 JSON 对象"
            )

        rows.append(
            row
        )

    return rows


def _require_non_empty(
    row: dict,
    key: str,
    context: str,
) -> str:
    value = row.get(
        key
    )

    if value is None:
        raise ValueError(
            f"{context} 缺少 {key}"
        )

    value = str(
        value
    ).strip()

    if not value:
        raise ValueError(
            f"{context}.{key} 不能为空"
        )

    return value


def _verify_checksums(
    checksums: dict,
    raw_files: dict[str, bytes],
) -> None:
    files = checksums.get(
        "files"
    )

    if not isinstance(
        files,
        dict,
    ):
        raise ValueError(
            "checksums.json.files "
            "必须是对象"
        )

    if set(files) != CHECKSUM_FILES:
        raise ValueError(
            "checksum 文件集合错误: "
            f"{sorted(files)}"
        )

    for file_name in CHECKSUM_FILES:
        expected = str(
            files[file_name]
        ).lower()

        actual = _sha256_bytes(
            raw_files[file_name]
        ).lower()

        if expected != actual:
            raise ValueError(
                "SHA-256 不一致: "
                f"{file_name}"
            )


def _verify_records(
    manifest: dict,
    tasks: list[dict],
    answers: list[dict],
    sources: list[dict],
) -> None:
    if (
        manifest.get(
            "schema_version"
        )
        != GEO_SCHEMA_VERSION
    ):
        raise ValueError(
            "schema_version 错误"
        )

    if (
        manifest.get(
            "geo_batch_version"
        )
        != GEO_BATCH_VERSION
    ):
        raise ValueError(
            "geo_batch_version 错误"
        )

    if (
        manifest.get(
            "platform_code"
        )
        != WENXIN_PLATFORM_CODE
    ):
        raise ValueError(
            "platform_code 错误"
        )

    _require_non_empty(
        manifest,
        "batch_id",
        "manifest",
    )

    _require_non_empty(
        manifest,
        "product_id",
        "manifest",
    )

    _require_non_empty(
        manifest,
        "product_name",
        "manifest",
    )

    capabilities = manifest.get(
        "capabilities"
    )

    if not isinstance(
        capabilities,
        dict,
    ):
        raise ValueError(
            "manifest.capabilities "
            "必须是对象"
        )

    for key in (
        "supports_sources",
        "supports_multiple_modes",
        "supports_screenshot",
    ):
        if not isinstance(
            capabilities.get(key),
            bool,
        ):
            raise ValueError(
                f"capabilities.{key} "
                "必须是 bool"
            )

    if not tasks:
        raise ValueError(
            "tasks.jsonl 不能为空"
        )

    if not answers:
        raise ValueError(
            "answers.jsonl 不能为空"
        )

    if (
        manifest.get(
            "task_count"
        )
        != len(tasks)
    ):
        raise ValueError(
            "manifest.task_count "
            "与实际不一致"
        )

    if (
        manifest.get(
            "answer_count"
        )
        != len(answers)
    ):
        raise ValueError(
            "manifest.answer_count "
            "与实际不一致"
        )

    if (
        manifest.get(
            "source_count"
        )
        != len(sources)
    ):
        raise ValueError(
            "manifest.source_count "
            "与实际不一致"
        )

    # -------------------------------------------------
    # Task
    # -------------------------------------------------

    task_ids: set[str] = set()
    task_map: dict[str, dict] = {}

    for index, task in enumerate(
        tasks,
        start=1,
    ):
        context = (
            f"tasks[{index}]"
        )

        task_id = _require_non_empty(
            task,
            "task_id",
            context,
        )

        if task_id in task_ids:
            raise ValueError(
                "重复 task_id: "
                f"{task_id}"
            )

        task_ids.add(
            task_id
        )

        task_map[
            task_id
        ] = task

        _require_non_empty(
            task,
            "question_id",
            context,
        )

        _require_non_empty(
            task,
            "question",
            context,
        )

        mode = _require_non_empty(
            task,
            "mode_code",
            context,
        )

        if mode not in {
            "quick",
            "expert",
        }:
            raise ValueError(
                f"非法 mode_code: "
                f"{mode}"
            )

        status = _require_non_empty(
            task,
            "task_status",
            context,
        )

        if status not in {
            "success",
            "failed",
            "running",
        }:
            raise ValueError(
                f"非法 task_status: "
                f"{status}"
            )

    # -------------------------------------------------
    # Answer
    # -------------------------------------------------

    answer_ids: set[str] = set()
    answer_map: dict[str, dict] = {}

    for index, answer in enumerate(
        answers,
        start=1,
    ):
        context = (
            f"answers[{index}]"
        )

        answer_id = _require_non_empty(
            answer,
            "answer_id",
            context,
        )

        if answer_id in answer_ids:
            raise ValueError(
                "重复 answer_id: "
                f"{answer_id}"
            )

        answer_ids.add(
            answer_id
        )

        answer_map[
            answer_id
        ] = answer

        task_id = _require_non_empty(
            answer,
            "task_id",
            context,
        )

        if task_id not in task_map:
            raise ValueError(
                "answer 引用了不存在的 "
                f"task_id: {task_id}"
            )

        task = task_map[
            task_id
        ]

        question_id = (
            _require_non_empty(
                answer,
                "question_id",
                context,
            )
        )

        mode_code = (
            _require_non_empty(
                answer,
                "mode_code",
                context,
            )
        )

        if (
            question_id
            != task["question_id"]
        ):
            raise ValueError(
                "Task / Answer "
                "question_id 不一致"
            )

        if (
            mode_code
            != task["mode_code"]
        ):
            raise ValueError(
                "Task / Answer "
                "mode_code 不一致"
            )

        clean_text = str(
            answer.get(
                "answer_text_clean"
            )
            or ""
        ).strip()

        if not clean_text:
            raise ValueError(
                f"{answer_id} "
                "answer_text_clean 为空"
            )

        if (
            answer.get(
                "is_complete"
            )
            is not True
        ):
            raise ValueError(
                f"{answer_id} "
                "is_complete != true"
            )

    # -------------------------------------------------
    # Sources
    # -------------------------------------------------

    occurrence_ids: set[str] = set()

    source_key_set: set[
        tuple[str, int, str]
    ] = set()

    answer_order_urls: dict[
        tuple[str, int],
        str,
    ] = {}

    source_counts: Counter = (
        Counter()
    )

    for index, source in enumerate(
        sources,
        start=1,
    ):
        context = (
            f"sources[{index}]"
        )

        answer_id = (
            _require_non_empty(
                source,
                "answer_id",
                context,
            )
        )

        if answer_id not in answer_map:
            raise ValueError(
                "source 引用了不存在的 "
                f"answer_id: {answer_id}"
            )

        raw_order = source.get(
            "source_order"
        )

        try:
            source_order = int(
                raw_order
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                f"{context}.source_order "
                "必须是整数"
            ) from exc

        if source_order < 1:
            raise ValueError(
                f"{context}.source_order "
                "必须 >= 1"
            )

        source_url = (
            _require_non_empty(
                source,
                "source_url_raw",
                context,
            )
        )

        occurrence_id = (
            _require_non_empty(
                source,
                "occurrence_id",
                context,
            )
        )

        if (
            occurrence_id
            in occurrence_ids
        ):
            raise ValueError(
                "重复 occurrence_id: "
                f"{occurrence_id}"
            )

        occurrence_ids.add(
            occurrence_id
        )

        key = (
            answer_id,
            source_order,
            source_url,
        )

        if key in source_key_set:
            raise ValueError(
                "重复 Source occurrence: "
                f"{key}"
            )

        source_key_set.add(
            key
        )

        order_key = (
            answer_id,
            source_order,
        )

        previous_url = (
            answer_order_urls.get(
                order_key
            )
        )

        if (
            previous_url is not None
            and previous_url != source_url
        ):
            raise ValueError(
                "同一个 answer_id + "
                "source_order "
                "出现不同 URL"
            )

        answer_order_urls[
            order_key
        ] = source_url

        source_counts[
            answer_id
        ] += 1

    # -------------------------------------------------
    # Answer source_count_raw
    # -------------------------------------------------

    for answer_id, answer in (
        answer_map.items()
    ):
        declared = int(
            answer.get(
                "source_count_raw",
                0,
            )
        )

        actual = (
            source_counts[
                answer_id
            ]
        )

        if declared != actual:
            raise ValueError(
                f"{answer_id} "
                "source_count_raw "
                f"不一致: "
                f"declared={declared}, "
                f"actual={actual}"
            )


def _verify_raw_files(
    raw_files: dict[str, bytes],
) -> None:
    manifest = _read_json_bytes(
        raw_files[
            "manifest.json"
        ],
        "manifest.json",
    )

    checksums = _read_json_bytes(
        raw_files[
            "checksums.json"
        ],
        "checksums.json",
    )

    tasks = _read_jsonl_bytes(
        raw_files[
            "tasks.jsonl"
        ],
        "tasks.jsonl",
    )

    answers = _read_jsonl_bytes(
        raw_files[
            "answers.jsonl"
        ],
        "answers.jsonl",
    )

    sources = _read_jsonl_bytes(
        raw_files[
            "sources.jsonl"
        ],
        "sources.jsonl",
    )

    _verify_checksums(
        checksums,
        raw_files,
    )

    _verify_records(
        manifest,
        tasks,
        answers,
        sources,
    )


def verify_package_directory(
    package_dir: str | Path,
) -> None:
    package_dir = Path(
        package_dir
    )

    if not package_dir.is_dir():
        raise FileNotFoundError(
            f"标准包目录不存在: "
            f"{package_dir}"
        )

    missing = [
        file_name
        for file_name
        in PACKAGE_FILES
        if not (
            package_dir
            / file_name
        ).exists()
    ]

    if missing:
        raise ValueError(
            "缺少标准包文件: "
            f"{sorted(missing)}"
        )

    raw_files = {
        file_name: (
            package_dir
            / file_name
        ).read_bytes()
        for file_name
        in PACKAGE_FILES
    }

    _verify_raw_files(
        raw_files
    )


def verify_package_zip(
    package_path: str | Path,
) -> None:
    package_path = Path(
        package_path
    )

    if not package_path.exists():
        raise FileNotFoundError(
            f"ZIP 不存在: "
            f"{package_path}"
        )

    if not zipfile.is_zipfile(
        package_path
    ):
        raise ValueError(
            "文件不是有效 ZIP"
        )

    with zipfile.ZipFile(
        package_path,
        "r",
    ) as archive:
        names = set(
            archive.namelist()
        )

        if names != PACKAGE_FILES:
            raise ValueError(
                "ZIP 文件集合错误: "
                f"{sorted(names)}"
            )

        raw_files = {
            file_name: (
                archive.read(
                    file_name
                )
            )
            for file_name
            in PACKAGE_FILES
        }

    _verify_raw_files(
        raw_files
    )