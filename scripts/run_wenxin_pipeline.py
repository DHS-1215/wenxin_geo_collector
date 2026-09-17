from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import (
    Browser,
    Page,
    sync_playwright,
)

from app.wenxin.batch import WenxinBatchRunner
from app.wenxin.checkpoint import WenxinCheckpoint
from app.wenxin.client import WenxinClient
from app.wenxin.exporter import WenxinExporter
from app.wenxin.input_loader import load_tasks
from app.wenxin.packager import create_package
from app.wenxin.products import (
    PRODUCTS,
    ProductConfig,
    get_product,
)
from app.wenxin.types import (
    TaskStatus,
    WenxinTask,
    WenxinTaskResult,
)
from app.wenxin.verifier import (
    verify_package_directory,
    verify_package_zip,
)

CHECKPOINT_ROOT = Path(
    "output/checkpoints"
)

PACKAGE_ROOT = Path(
    "output/package"
)

WENXIN_HOME = (
    "https://wenxin.baidu.com/"
    "?enter_type=chat_site"
)


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "百度文心助手 GEO 采集 Pipeline"
        )
    )

    parser.add_argument(
        "--product",
        choices=PRODUCTS.keys(),
        default=None,
        help="直接指定采集产品",
    )

    parser.add_argument(
        "--batch-id",
        default=None,
        help=(
            "恢复已有批次；"
            "不指定则创建新批次"
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "仅执行前 N 个任务，"
            "主要用于调试或分段测试"
        ),
    )

    return parser.parse_args()


# ============================================================
# Product
# ============================================================

def choose_product() -> str | None:
    print()
    print("请选择采集产品：")
    print()
    print("1. 鸿茅药酒")
    print("2. 天益寿气血固本")
    print()
    print("Q. 退出")
    print()

    mapping = {
        "1": "hongmao",
        "2": "tianyishou",
        "q": None,
    }

    while True:
        value = input(
            "请输入选项 [1/2/Q]: "
        ).strip().lower()

        if value in mapping:
            return mapping[value]

        print(
            "无效选项，请输入 1、2 或 Q。"
        )


def resolve_product_key(
        cli_product: str | None,
) -> str | None:
    if cli_product:
        return cli_product

    return choose_product()


# ============================================================
# Batch
# ============================================================

def build_batch_id(
        product_id: str,
) -> str:
    timestamp = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    return (
        f"wenxin_"
        f"{product_id}_"
        f"{timestamp}"
    )


def validate_existing_checkpoint(
        checkpoint: WenxinCheckpoint,
        product: ProductConfig,
) -> None:
    """
    防止把鸿茅 batch_id
    错误地拿给天益寿继续跑。
    """

    if not checkpoint.meta_path.exists():
        return

    meta = json.loads(
        checkpoint.meta_path.read_text(
            encoding="utf-8"
        )
    )

    old_product_id = str(
        meta.get(
            "product_id"
        )
        or ""
    )

    if (
            old_product_id
            and old_product_id
            != product.product_id
    ):
        raise ValueError(
            "Batch 产品不匹配："
            f"{checkpoint.batch_id} "
            f"属于 {old_product_id}，"
            f"当前选择的是 "
            f"{product.product_id}"
        )


# ============================================================
# Browser
# ============================================================

def find_wenxin_page(
        browser: Browser,
) -> Page:
    """
    优先寻找已经打开的文心页面。
    找不到则在已有登录 Context 中新建。
    """

    for context in browser.contexts:
        for page in reversed(
                context.pages
        ):
            if (
                    "wenxin.baidu.com"
                    in page.url
            ):
                page.bring_to_front()
                return page

    if not browser.contexts:
        raise RuntimeError(
            "CDP 中没有 BrowserContext"
        )

    context = browser.contexts[0]

    page = context.new_page()

    page.goto(
        WENXIN_HOME,
        wait_until="domcontentloaded",
        timeout=30000,
    )

    page.bring_to_front()

    return page


# ============================================================
# Checkpoint helpers
# ============================================================

def result_map(
        results: list[WenxinTaskResult],
) -> dict[str, WenxinTaskResult]:
    return {
        result.task_id: result
        for result in results
    }


def successful_task_ids(
        results: list[WenxinTaskResult],
) -> set[str]:
    return {
        result.task_id
        for result in results
        if (
                result.status
                == TaskStatus.SUCCESS
        )
    }


def order_results(
        tasks: list[WenxinTask],
        results: list[WenxinTaskResult],
) -> list[WenxinTaskResult]:
    mapping = result_map(
        results
    )

    ordered: list[
        WenxinTaskResult
    ] = []

    for task in tasks:
        result = mapping.get(
            task.task_id
        )

        if result is None:
            raise RuntimeError(
                "Checkpoint 缺少任务结果: "
                f"{task.task_id}"
            )

        ordered.append(
            result
        )

    return ordered


# ============================================================
# Export
# ============================================================

def export_package(
        *,
        checkpoint: WenxinCheckpoint,
        product: ProductConfig,
        batch_id: str,
        tasks: list[WenxinTask],
) -> tuple[Path, Path]:
    results = (
        checkpoint.load_all_results()
    )

    ordered_results = (
        order_results(
            tasks,
            results,
        )
    )

    failed = [
        result
        for result
        in ordered_results
        if (
                result.status
                != TaskStatus.SUCCESS
        )
    ]

    if failed:
        failed_ids = [
            result.task_id
            for result
            in failed
        ]

        raise RuntimeError(
            "仍存在失败任务，"
            "暂不生成正式包: "
            f"{failed_ids}"
        )

    meta = json.loads(
        checkpoint.meta_path.read_text(
            encoding="utf-8"
        )
    )

    package_dir = (
            PACKAGE_ROOT
            / batch_id
    )

    exporter = WenxinExporter()

    exporter.export(
        results=ordered_results,
        output_dir=package_dir,
        batch_id=batch_id,
        product_id=(
            product.product_id
        ),
        product_name=(
            product.product_name
        ),
        started_at=str(
            meta.get(
                "started_at"
            )
            or ""
        ),
        finished_at=str(
            meta.get(
                "finished_at"
            )
            or ""
        ),
    )

    verify_package_directory(
        package_dir
    )

    print(
        "DIRECTORY VERIFY: PASS"
    )

    zip_path = (
            PACKAGE_ROOT
            / f"{batch_id}.zip"
    )

    create_package(
        package_dir,
        zip_path,
    )

    verify_package_zip(
        zip_path
    )

    print(
        "ZIP VERIFY: PASS"
    )

    return (
        package_dir,
        zip_path,
    )


# ============================================================
# Summary
# ============================================================

def print_final_summary(
        *,
        batch_id: str,
        package_dir: Path,
        zip_path: Path,
        results: list[WenxinTaskResult],
) -> None:
    source_count = sum(
        len(
            result.answer.sources
        )
        for result in results
        if result.answer
    )

    print()
    print("=" * 80)
    print(
        "WENXIN GEO PIPELINE: PASS"
    )
    print("=" * 80)

    print(
        "BATCH ID:",
        batch_id,
    )

    print(
        "TASKS:",
        len(results),
    )

    print(
        "SUCCESS:",
        sum(
            result.status
            == TaskStatus.SUCCESS
            for result
            in results
        ),
    )

    print(
        "SOURCES:",
        source_count,
    )

    print(
        "PACKAGE DIR:",
        package_dir.resolve(),
    )

    print(
        "ZIP:",
        zip_path.resolve(),
    )


# ============================================================
# Main
# ============================================================

def main() -> int:
    args = parse_args()

    product_key = (
        resolve_product_key(
            args.product
        )
    )

    if product_key is None:
        print("已退出。")
        return 0

    product = get_product(
        product_key
    )

    load_result = load_tasks(
        product.csv_path
    )

    all_tasks = (
        load_result.tasks
    )

    if not all_tasks:
        print(
            "ERROR: 没有可执行任务"
        )
        return 1

    batch_id = (
            args.batch_id
            or build_batch_id(
        product.product_id
    )
    )

    checkpoint = WenxinCheckpoint(
        root_dir=CHECKPOINT_ROOT,
        batch_id=batch_id,
        product_id=(
            product.product_id
        ),
        product_name=(
            product.product_name
        ),
    )

    validate_existing_checkpoint(
        checkpoint,
        product,
    )

    # --------------------------------------------------------
    # 本次执行范围
    # --------------------------------------------------------

    tasks = all_tasks

    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError(
                "--limit 必须大于 0"
            )

        tasks = all_tasks[
                :args.limit
                ]

    is_partial = (
            len(tasks)
            < len(all_tasks)
    )

    print()
    print("=" * 80)
    print(
        "WENXIN GEO COLLECTION PIPELINE"
    )
    print("=" * 80)

    print(
        "PRODUCT:",
        product.product_name,
    )

    print(
        "PRODUCT ID:",
        product.product_id,
    )

    print(
        "BATCH ID:",
        batch_id,
    )

    print(
        "CSV:",
        product.csv_path,
    )

    print(
        "TOTAL INPUT:",
        (
                len(all_tasks)
                + len(
            load_result.skipped
        )
        ),
    )

    print(
        "RUNNABLE:",
        len(all_tasks),
    )

    print(
        "THIS RUN:",
        len(tasks),
    )

    print(
        "SKIPPED:",
        len(
            load_result.skipped
        ),
    )

    # --------------------------------------------------------
    # 看看已经完成多少
    # --------------------------------------------------------

    existing_results = (
        checkpoint.load_all_results()
    )

    success_ids = (
        successful_task_ids(
            existing_results
        )
    )

    pending_tasks = [
        task
        for task in tasks
        if (
                task.task_id
                not in success_ids
        )
    ]

    print(
        "CHECKPOINT SUCCESS:",
        len(
            [
                task
                for task in tasks
                if (
                    task.task_id
                    in success_ids
            )
            ]
        ),
    )

    print(
        "PENDING:",
        len(pending_tasks),
    )

    # --------------------------------------------------------
    # 已经全部成功：直接恢复
    # --------------------------------------------------------

    if not pending_tasks:
        print()
        print(
            "[CHECKPOINT] "
            "本次范围内任务已经全部成功。"
        )

        print(
            "[CHECKPOINT] "
            "无需重新连接文心采集。"
        )

    else:
        # ----------------------------------------------------
        # CDP real collection
        # ----------------------------------------------------

        print()
        print(
            "Connecting CDP..."
        )

        try:
            with sync_playwright() as p:
                browser = (
                    p.chromium
                    .connect_over_cdp(
                        "http://127.0.0.1:9222"
                    )
                )

                page = find_wenxin_page(
                    browser
                )

                print(
                    "WENXIN PAGE:",
                    page.url,
                )

                client = WenxinClient(
                    page=page,
                    answer_timeout=180,
                )

                runner = (
                    WenxinBatchRunner(
                        client=client,
                        checkpoint=(
                            checkpoint
                        ),
                    )
                )

                runner.run(
                    tasks,
                    planned_count=(
                        len(all_tasks)
                    ),
                    finalize_checkpoint=(
                        not is_partial
                    ),
                )

        except Exception as exc:
            print()
            print(
                "PIPELINE ERROR:",
                repr(exc),
            )

            print(
                "\n如果是 CDP 未启动，"
                "请先启动 Chrome "
                "remote debugging 9222。"
            )

            return 1

    # --------------------------------------------------------
    # Partial
    # --------------------------------------------------------

    if is_partial:
        print()
        print("=" * 80)
        print(
            "PARTIAL COLLECTION COMPLETE"
        )
        print("=" * 80)

        print(
            "CHECKPOINT:",
            checkpoint.batch_dir.resolve(),
        )

        print()
        print(
            "继续执行："
        )

        print(
            "python -m "
            "scripts.run_wenxin_pipeline "
            f"--product {product_key} "
            f'--batch-id "{batch_id}"'
        )

        return 0

    # --------------------------------------------------------
    # Full package
    # --------------------------------------------------------

    current_results = (
        checkpoint.load_all_results()
    )

    current_success = (
        successful_task_ids(
            current_results
        )
    )

    missing = [
        task.task_id
        for task
        in all_tasks
        if (
                task.task_id
                not in current_success
        )
    ]

    if missing:
        print()
        print(
            "PIPELINE INCOMPLETE"
        )

        print(
            "未成功任务:",
            missing,
        )

        print(
            "\n再次使用同一 batch_id "
            "即可重试失败任务。"
        )

        return 1

    print()
    print("=" * 80)
    print(
        "EXPORTING GEO PACKAGE"
    )
    print("=" * 80)

    package_dir, zip_path = (
        export_package(
            checkpoint=checkpoint,
            product=product,
            batch_id=batch_id,
            tasks=all_tasks,
        )
    )

    final_results = (
        order_results(
            all_tasks,
            checkpoint
            .load_all_results(),
        )
    )

    print_final_summary(
        batch_id=batch_id,
        package_dir=package_dir,
        zip_path=zip_path,
        results=final_results,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
