from __future__ import annotations

import csv
import json
from zipfile import ZipFile
import pytest

from app.wenxin.batch import WenxinBatchRunner
from app.wenxin.exceptions import (
    WenxinLoginRequiredError,
    WenxinQuotaExhaustedError,
    WenxinRiskControlError,
)
from app.wenxin.types import WenxinTask
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
from app.wenxin.error_classifier import (
    WenxinControlKind,
    classify_wenxin_text,
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


def test_classify_quota() -> None:
    match = classify_wenxin_text(
        "今日对话次数已达上限"
    )

    assert match is not None
    assert (
            match.kind
            == WenxinControlKind.QUOTA
    )


def test_classify_risk_control() -> None:
    match = classify_wenxin_text(
        "操作频繁，请稍后处理"
    )

    assert match is not None
    assert (
            match.kind
            == WenxinControlKind.RISK_CONTROL
    )


def test_classify_login_required() -> None:
    match = classify_wenxin_text(
        "登录状态已失效，请重新登录"
    )

    assert match is not None
    assert (
            match.kind
            == WenxinControlKind.LOGIN_REQUIRED
    )


def test_quota_resume_from_current_task(
        tmp_path,
) -> None:
    """
    模拟真实场景：

    第一轮：
    Q001 success
    Q002 quota
    -> Q001 已保存
    -> Q002 不写 FAILED

    第二轮：
    Q001 checkpoint 跳过
    Q002 重试成功
    Q003 成功
    """

    tasks = [
        WenxinTask(
            task_id="Q001_quick",
            question_id="Q001",
            question="问题1",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
        WenxinTask(
            task_id="Q002_quick",
            question_id="Q002",
            question="问题2",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
        WenxinTask(
            task_id="Q003_quick",
            question_id="Q003",
            question="问题3",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
    ]

    checkpoint = WenxinCheckpoint(
        root_dir=(
                tmp_path
                / "checkpoints"
        ),
        batch_id="quota_resume_test",
        product_id="test_product",
        product_name="测试产品",
    )

    class FakeQuotaClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

            # Q002 第一次调用时模拟额度耗尽
            self.quota_triggered = False

        def collect(
                self,
                question: str,
                mode: WenxinMode,
        ) -> WenxinAnswer:
            self.calls.append(
                question
            )

            if (
                    question == "问题2"
                    and not self.quota_triggered
            ):
                self.quota_triggered = True

                raise (
                    WenxinQuotaExhaustedError(
                        "今日对话次数已达上限"
                    )
                )

            return WenxinAnswer(
                question=question,
                text=(
                    f"回答：{question}"
                ),
                raw_text=(
                    f"回答：{question}"
                ),
                session_id=(
                    f"session_"
                    f"{len(self.calls)}"
                ),
                mode=mode,
                model_name="smartMode",
                deep_search=False,
                sources=[],
            )

        def _random_action_delay(
                self,
                min_seconds=None,
                max_seconds=None,
        ) -> None:
            pass

    client = FakeQuotaClient()

    runner = WenxinBatchRunner(
        client=client,
        checkpoint=checkpoint,
    )

    # ============================================================
    # 第一轮
    # ============================================================

    with pytest.raises(
            WenxinQuotaExhaustedError
    ) as exc_info:
        runner.run(
            tasks,
            planned_count=3,
            finalize_checkpoint=False,
        )

    assert (
            exc_info.value.task_id
            == "Q002_quick"
    )

    # 第一题必须已经落盘
    q001 = checkpoint.load_success(
        "Q001_quick"
    )

    assert q001 is not None

    # 第二题额度耗尽不能被写成 FAILED
    q002 = checkpoint.load_result(
        "Q002_quick"
    )

    assert q002 is None

    # 第三题根本还没执行
    q003 = checkpoint.load_result(
        "Q003_quick"
    )

    assert q003 is None

    assert client.calls == [
        "问题1",
        "问题2",
    ]

    # ============================================================
    # 第二轮：模拟人工换号后继续
    # ============================================================

    results = runner.run(
        tasks,
        planned_count=3,
        finalize_checkpoint=True,
    )

    # Q001 必须从 checkpoint 恢复，
    # 不能重新向“文心”请求
    assert client.calls == [
        "问题1",
        "问题2",
        "问题2",
        "问题3",
    ]

    assert len(results) == 3

    assert all(
        result.status
        == TaskStatus.SUCCESS
        for result in results
    )

    # 最终三题全部成功落盘
    assert (
            checkpoint.load_success(
                "Q001_quick"
            )
            is not None
    )

    assert (
            checkpoint.load_success(
                "Q002_quick"
            )
            is not None
    )

    assert (
            checkpoint.load_success(
                "Q003_quick"
            )
            is not None
    )

    meta = json.loads(
        checkpoint.meta_path.read_text(
            encoding="utf-8"
        )
    )

    assert meta["status"] == "completed"
    assert meta["planned_count"] == 3
    assert meta["completed_count"] == 3
    assert meta["success_count"] == 3
    assert meta["failed_count"] == 0


def test_risk_control_stops_batch(
        tmp_path,
) -> None:
    """
    模拟真实场景：

    Q001 success
    Q002 risk_control
    -> Q001 已保存
    -> Q002 不写 FAILED
    -> Q003 不执行
    -> 整批立即停止
    """

    tasks = [
        WenxinTask(
            task_id="Q001_quick",
            question_id="Q001",
            question="问题1",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
        WenxinTask(
            task_id="Q002_quick",
            question_id="Q002",
            question="问题2",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
        WenxinTask(
            task_id="Q003_quick",
            question_id="Q003",
            question="问题3",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
    ]

    checkpoint = WenxinCheckpoint(
        root_dir=(
                tmp_path
                / "checkpoints"
        ),
        batch_id="risk_control_test",
        product_id="test_product",
        product_name="测试产品",
    )

    class FakeRiskClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def collect(
                self,
                question: str,
                mode: WenxinMode,
        ) -> WenxinAnswer:
            self.calls.append(
                question
            )

            if question == "问题2":
                raise (
                    WenxinRiskControlError(
                        "操作频繁，请稍后再试"
                    )
                )

            return WenxinAnswer(
                question=question,
                text=(
                    f"回答：{question}"
                ),
                raw_text=(
                    f"回答：{question}"
                ),
                session_id=(
                    f"session_"
                    f"{len(self.calls)}"
                ),
                mode=mode,
                model_name="smartMode",
                deep_search=False,
                sources=[],
            )

        def _random_action_delay(
                self,
                min_seconds=None,
                max_seconds=None,
        ) -> None:
            pass

    client = FakeRiskClient()

    runner = WenxinBatchRunner(
        client=client,
        checkpoint=checkpoint,
    )

    with pytest.raises(
            WenxinRiskControlError
    ) as exc_info:
        runner.run(
            tasks,
            planned_count=3,
            finalize_checkpoint=False,
        )

    # 风控发生在 Q002
    assert (
            exc_info.value.task_id
            == "Q002_quick"
    )

    # 只执行到 Q002
    assert client.calls == [
        "问题1",
        "问题2",
    ]

    # Q001 已成功落盘
    assert (
            checkpoint.load_success(
                "Q001_quick"
            )
            is not None
    )

    # Q002 风控事件不能写成 FAILED
    assert (
            checkpoint.load_result(
                "Q002_quick"
            )
            is None
    )

    # Q003 根本不应该执行
    assert (
            checkpoint.load_result(
                "Q003_quick"
            )
            is None
    )

    meta = json.loads(
        checkpoint.meta_path.read_text(
            encoding="utf-8"
        )
    )

    # BatchRunner 被控制事件打断，
    # 此时会先保存为 interrupted。
    # 正式 Pipeline 捕获 Risk 后，
    # 再更新为 risk_control。
    assert (
            meta["status"]
            == "interrupted"
    )

    assert meta["planned_count"] == 3
    assert meta["completed_count"] == 1
    assert meta["success_count"] == 1
    assert meta["failed_count"] == 0


def test_login_resume_from_current_task(
        tmp_path,
) -> None:
    """
    第一轮：
    Q001 success
    Q002 login required
    -> Q001 已保存
    -> Q002 不写 FAILED
    -> Q003 不执行

    第二轮模拟人工重新登录：
    Q001 checkpoint 跳过
    Q002 重试成功
    Q003 成功
    """

    tasks = [
        WenxinTask(
            task_id="Q001_quick",
            question_id="Q001",
            question="问题1",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
        WenxinTask(
            task_id="Q002_quick",
            question_id="Q002",
            question="问题2",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
        WenxinTask(
            task_id="Q003_quick",
            question_id="Q003",
            question="问题3",
            geo_mode=GeoMode.QUICK,
            mode=WenxinMode.FAST,
        ),
    ]

    checkpoint = WenxinCheckpoint(
        root_dir=(
                tmp_path
                / "checkpoints"
        ),
        batch_id="login_resume_test",
        product_id="test_product",
        product_name="测试产品",
    )

    class FakeLoginClient:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.login_triggered = False

        def collect(
                self,
                question: str,
                mode: WenxinMode,
        ) -> WenxinAnswer:
            self.calls.append(
                question
            )

            if (
                    question == "问题2"
                    and not self.login_triggered
            ):
                self.login_triggered = True

                raise (
                    WenxinLoginRequiredError(
                        "登录状态已失效，请重新登录"
                    )
                )

            return WenxinAnswer(
                question=question,
                text=f"回答：{question}",
                raw_text=f"回答：{question}",
                session_id=(
                    f"session_"
                    f"{len(self.calls)}"
                ),
                mode=mode,
                model_name="smartMode",
                deep_search=False,
                sources=[],
            )

        def _random_action_delay(
                self,
                min_seconds=None,
                max_seconds=None,
        ) -> None:
            pass

    client = FakeLoginClient()

    runner = WenxinBatchRunner(
        client=client,
        checkpoint=checkpoint,
    )

    # 第一轮：Q002 登录失效
    with pytest.raises(
            WenxinLoginRequiredError
    ) as exc_info:
        runner.run(
            tasks,
            planned_count=3,
            finalize_checkpoint=False,
        )

    assert (
            exc_info.value.task_id
            == "Q002_quick"
    )

    # Q001 已完成
    assert (
            checkpoint.load_success(
                "Q001_quick"
            )
            is not None
    )

    # Q002 不能被当成普通失败
    assert (
            checkpoint.load_result(
                "Q002_quick"
            )
            is None
    )

    # Q003 尚未执行
    assert (
            checkpoint.load_result(
                "Q003_quick"
            )
            is None
    )

    assert client.calls == [
        "问题1",
        "问题2",
    ]

    # 第二轮：模拟人工重新登录完成
    results = runner.run(
        tasks,
        planned_count=3,
        finalize_checkpoint=True,
    )

    # Q001 必须跳过，不重新请求
    assert client.calls == [
        "问题1",
        "问题2",
        "问题2",
        "问题3",
    ]

    assert len(results) == 3

    assert all(
        result.status
        == TaskStatus.SUCCESS
        for result in results
    )

    meta = json.loads(
        checkpoint.meta_path.read_text(
            encoding="utf-8"
        )
    )

    assert meta["status"] == "completed"
    assert meta["planned_count"] == 3
    assert meta["completed_count"] == 3
    assert meta["success_count"] == 3
    assert meta["failed_count"] == 0
