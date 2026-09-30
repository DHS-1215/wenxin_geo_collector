from __future__ import annotations

import hashlib
import json
import struct
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


def _read_png_size_bytes(
    data: bytes,
) -> tuple[int, int]:
    signature = b"\x89PNG\r\n\x1a\n"

    if not data.startswith(
        signature
    ):
        raise ValueError(
            "Screenshot is not valid PNG"
        )

    if len(data) < 24:
        raise ValueError(
            "PNG data is too short"
        )

    return struct.unpack(
        ">II",
        data[16:24],
    )


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
            "checksums.json.files must be object"
        )

    expected_files = (
        set(raw_files)
        - {"checksums.json"}
    )

    if set(files) != expected_files:
        raise ValueError(
            "Checksum file set mismatch: "
            f"declared={sorted(files)}, "
            f"actual={sorted(expected_files)}"
        )

    for file_name in sorted(
        expected_files
    ):
        expected = str(
            files[file_name]
        ).lower()

        actual = _sha256_bytes(
            raw_files[file_name]
        ).lower()

        if expected != actual:
            raise ValueError(
                "SHA-256 mismatch: "
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


def _verify_screenshots(
    manifest: dict,
    answers: list[dict],
    raw_files: dict[str, bytes],
) -> None:
    capabilities = (
        manifest.get(
            "capabilities"
        )
        or {}
    )

    supports_screenshot = (
        capabilities.get(
            "supports_screenshot"
        )
        is True
    )

    screenshot_files = {
        name
        for name in raw_files
        if (
            name.startswith(
                "screenshots/"
            )
            and name.lower().endswith(
                ".png"
            )
        )
    }

    if (
        screenshot_files
        and not supports_screenshot
    ):
        raise ValueError(
            "Screenshot files exist but "
            "supports_screenshot is false"
        )

    referenced: set[str] = set()

    for index, answer in enumerate(
        answers,
        start=1,
    ):
        context = (
            f"answers[{index}]"
        )

        raw_path = answer.get(
            "screenshot_path"
        )

        if not raw_path:
            if supports_screenshot:
                raise ValueError(
                    f"{context}.screenshot_path "
                    "is required"
                )

            continue

        screenshot_path = (
            str(raw_path)
            .replace(
                "\\",
                "/",
            )
            .strip()
        )

        if not (
            screenshot_path.startswith(
                "screenshots/"
            )
            and screenshot_path.count(
                "/"
            ) == 1
            and screenshot_path.lower().endswith(
                ".png"
            )
        ):
            raise ValueError(
                "Invalid screenshot_path: "
                f"{screenshot_path}"
            )

        if screenshot_path not in raw_files:
            raise ValueError(
                "Screenshot file missing: "
                f"{screenshot_path}"
            )

        if screenshot_path in referenced:
            raise ValueError(
                "Duplicate screenshot reference: "
                f"{screenshot_path}"
            )

        referenced.add(
            screenshot_path
        )

        meta = answer.get(
            "platform_meta_json"
        )

        if not isinstance(
            meta,
            dict,
        ):
            raise ValueError(
                f"{context}.platform_meta_json "
                "must be object"
            )

        screenshot_data = (
            raw_files[
                screenshot_path
            ]
        )

        expected_sha = str(
            meta.get(
                "screenshot_sha256"
            )
            or ""
        ).lower()

        actual_sha = _sha256_bytes(
            screenshot_data
        ).lower()

        if (
            not expected_sha
            or expected_sha
            != actual_sha
        ):
            raise ValueError(
                "Screenshot SHA-256 mismatch: "
                f"{screenshot_path}"
            )

        try:
            expected_size = int(
                meta[
                    "screenshot_size_bytes"
                ]
            )
            expected_width = int(
                meta[
                    "screenshot_width"
                ]
            )
            expected_height = int(
                meta[
                    "screenshot_height"
                ]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Invalid screenshot metadata: "
                f"{screenshot_path}"
            ) from exc

        if (
            expected_size
            != len(screenshot_data)
        ):
            raise ValueError(
                "Screenshot size mismatch: "
                f"{screenshot_path}"
            )

        actual_width, actual_height = (
            _read_png_size_bytes(
                screenshot_data
            )
        )

        if (
            expected_width
            != actual_width
            or expected_height
            != actual_height
        ):
            raise ValueError(
                "Screenshot dimensions mismatch: "
                f"{screenshot_path}"
            )

    if screenshot_files != referenced:
        raise ValueError(
            "Screenshot file/reference set mismatch: "
            f"files={sorted(screenshot_files)}, "
            f"referenced={sorted(referenced)}"
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

    _verify_screenshots(
        manifest,
        answers,
        raw_files,
    )


def verify_package_directory(
    package_dir: str | Path,
) -> None:
    package_dir = Path(
        package_dir
    )

    if not package_dir.is_dir():
        raise FileNotFoundError(
            f"Package directory not found: "
            f"{package_dir}"
        )

    package_paths = {
        path.relative_to(
            package_dir
        ).as_posix(): path
        for path in package_dir.rglob(
            "*"
        )
        if path.is_file()
    }

    names = set(
        package_paths
    )

    missing = (
        PACKAGE_FILES
        - names
    )

    if missing:
        raise ValueError(
            "Missing package files: "
            f"{sorted(missing)}"
        )

    unexpected = {
        name
        for name in names
        if (
            name not in PACKAGE_FILES
            and not (
                name.startswith(
                    "screenshots/"
                )
                and name.count(
                    "/"
                ) == 1
                and name.lower().endswith(
                    ".png"
                )
            )
        )
    }

    if unexpected:
        raise ValueError(
            "Unexpected package files: "
            f"{sorted(unexpected)}"
        )

    raw_files = {
        name: path.read_bytes()
        for name, path
        in package_paths.items()
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
            f"ZIP not found: "
            f"{package_path}"
        )

    if not zipfile.is_zipfile(
        package_path
    ):
        raise ValueError(
            "File is not a valid ZIP"
        )

    with zipfile.ZipFile(
        package_path,
        "r",
    ) as archive:
        names = {
            name
            for name
            in archive.namelist()
            if not name.endswith("/")
        }

        missing = (
            PACKAGE_FILES
            - names
        )

        if missing:
            raise ValueError(
                "ZIP missing files: "
                f"{sorted(missing)}"
            )

        unexpected = {
            name
            for name in names
            if (
                name not in PACKAGE_FILES
                and not (
                    name.startswith(
                        "screenshots/"
                    )
                    and name.count(
                        "/"
                    ) == 1
                    and name.lower().endswith(
                        ".png"
                    )
                )
            )
        }

        if unexpected:
            raise ValueError(
                "Unexpected ZIP files: "
                f"{sorted(unexpected)}"
            )

        raw_files = {
            file_name: archive.read(
                file_name
            )
            for file_name in names
        }

    _verify_raw_files(
        raw_files
    )