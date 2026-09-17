from __future__ import annotations

import hashlib

GEO_SCHEMA_VERSION = "geo_package_v1"
GEO_BATCH_VERSION = "geo_batch_v1"

WENXIN_PLATFORM_CODE = "wenxin"
WENXIN_PLATFORM_NAME = "百度文心助手"

COLLECTOR_VERSION = "0.1.0"


def _stable_hash(
        *parts: object,
        length: int = 24,
) -> str:
    """生成确定性的短 SHA-256。"""

    payload = "\n".join(
        str(part)
        for part in parts
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:length]


def build_task_id(
        batch_id: str,
        question_id: str,
        mode_code: str,
) -> str:
    """生成 GEO 标准 task_id。"""

    digest = _stable_hash(
        WENXIN_PLATFORM_CODE,
        batch_id,
        question_id,
        mode_code,
    )

    return f"wx_t_{digest}"


def build_answer_id(
        batch_id: str,
        task_id: str,
) -> str:
    """生成 GEO 标准 answer_id。"""

    digest = _stable_hash(
        WENXIN_PLATFORM_CODE,
        batch_id,
        task_id,
    )

    return f"wx_a_{digest}"


def build_occurrence_id(
        batch_id: str,
        answer_id: str,
        source_order: int,
        source_url_raw: str,
) -> str:
    """生成单次信源 occurrence_id。"""

    digest = _stable_hash(
        WENXIN_PLATFORM_CODE,
        batch_id,
        answer_id,
        source_order,
        source_url_raw.strip(),
    )

    return f"wx_s_{digest}"
