from __future__ import annotations

import csv
import json
from zipfile import ZipFile

from app.wenxin.capacity import detect_risk
from app.wenxin.checkpoint import WenxinCheckpoint
from app.wenxin.exporter import WenxinExporter
from app.wenxin.geo_contract import (
    build_answer_id,
    build_occurrence_id,
    build_task_id,
)
from app.wenxin.input_loader import load_tasks
from app.wenxin.packager import create_package
from app.wenxin.types import (
    GeoMode,
    TaskStatus,
    WenxinAnswer,
    WenxinMode,
    WenxinSource,
    WenxinTaskResult,
)
from app.wenxin.verifier import (
    verify_package_directory,
    verify_package_zip,
)


def build_fake_result() -> WenxinTaskResult:
    return WenxinTaskResult(
        task_id="Q001_quick",
        question_id="Q001",
        question="测试问题",
        geo_mode=GeoMode.QUICK,
        mode=WenxinMode.FAST,
        status=TaskStatus.SUCCESS,
        answer=WenxinAnswer(
            question="测试问题",
            text="这是一个测试回答。",
            raw_text="这是一个测试回答。",
            session_id="test_session",
            mode=WenxinMode.FAST,
            conversation_url=(
                "https://wenxin.baidu.com/"
                "search/123456"
            ),
            collected_at=(
                "2026-09-17T00:00:00+00:00"
            ),
            model_name="smartMode",
            deep_search=False,
            sources=[
                WenxinSource(
                    rank=1,
                    title="测试来源",
                    url="https://example.com/a",
                    domain="example.com",
                    tags=["测试"],
                )
            ],
        ),
    )


def test_geo_ids_are_stable() -> None:
    task_id_1 = build_task_id(
        "batch_001",
        "Q001",
        "quick",
    )

    task_id_2 = build_task_id(
        "batch_001",
        "Q001",
        "quick",
    )

    assert task_id_1 == task_id_2
    assert task_id_1.startswith("wx_t_")

    answer_id = build_answer_id(
        "batch_001",
        task_id_1,
    )

    assert answer_id.startswith("wx_a_")

    occurrence_id = build_occurrence_id(
        "batch_001",
        answer_id,
        1,
        "https://example.com/a",
    )

    assert occurrence_id.startswith("wx_s_")


def test_detect_risk() -> None:
    assert detect_risk(
        "请求频繁，请稍后再试"
    )

    assert detect_risk(
        "需要进行安全验证"
    )

    assert not detect_risk(
        "这是一个正常回答"
    )


def test_input_loader_skips_expert(
        tmp_path,
) -> None:
    csv_path = (
            tmp_path
            / "questions.csv"
    )

    with csv_path.open(
            "w",
            encoding="utf-8-sig",
            newline="",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "question_id",
                "question",
                "mode",
            ]
        )

        writer.writerow(
            [
                "Q001",
                "快速问题",
                "quick",
            ]
        )

        writer.writerow(
            [
                "Q002",
                "专家问题",
                "expert",
            ]
        )

    result = load_tasks(
        csv_path
    )

    assert len(result.tasks) == 1
    assert len(result.skipped) == 1

    task = result.tasks[0]

    assert task.question_id == "Q001"
    assert task.geo_mode == GeoMode.QUICK
    assert task.mode == WenxinMode.FAST


def test_checkpoint_round_trip(
        tmp_path,
) -> None:
    checkpoint = WenxinCheckpoint(
        root_dir=(
                tmp_path
                / "checkpoints"
        ),
        batch_id="batch_001",
        product_id="test_product",
        product_name="测试产品",
    )

    checkpoint.start(
        planned_count=1
    )

    original = build_fake_result()

    checkpoint.save_result(
        original
    )

    restored = checkpoint.load_success(
        "Q001_quick"
    )

    assert restored is not None

    assert (
            restored.status
            == TaskStatus.SUCCESS
    )

    assert restored.answer is not None

    assert (
            restored.answer.text
            == original.answer.text
    )

    assert (
            restored.answer.sources[0].url
            == "https://example.com/a"
    )


def test_export_verify_and_zip(
        tmp_path,
) -> None:
    result = build_fake_result()

    package_dir = (
            tmp_path
            / "package"
    )

    exporter = WenxinExporter()

    exporter.export(
        results=[result],
        output_dir=package_dir,
        batch_id="batch_001",
        product_id="test_product",
        product_name="测试产品",
        started_at=(
            "2026-09-17T00:00:00+00:00"
        ),
        finished_at=(
            "2026-09-17T00:01:00+00:00"
        ),
    )

    verify_package_directory(
        package_dir
    )

    manifest = json.loads(
        (
                package_dir
                / "manifest.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert manifest["task_count"] == 1
    assert manifest["answer_count"] == 1
    assert manifest["source_count"] == 1
    assert manifest["status"] == "PASS"

    zip_path = (
            tmp_path
            / "batch_001.zip"
    )

    create_package(
        package_dir,
        zip_path,
    )

    verify_package_zip(
        zip_path
    )

    with ZipFile(zip_path) as archive:
        assert set(
            archive.namelist()
        ) == {
                   "manifest.json",
                   "tasks.jsonl",
                   "answers.jsonl",
                   "sources.jsonl",
                   "checksums.json",
               }
