from __future__ import annotations

import argparse
import random
import time

from playwright.sync_api import (
    sync_playwright,
)

from app.wenxin.capacity import (
    CapacityResult,
    detect_risk,
)
from app.wenxin.client import (
    WenxinClient,
)
from app.wenxin.types import (
    WenxinMode,
)

QUESTIONS = (
    "请用两三句话介绍一下鸿茅药酒的基本属性。",
    "鸿茅药酒属于药品还是普通酒类？",
    "请简单说明鸿茅药酒的生产企业信息。",
    "鸿茅药酒的说明书通常包含哪些基本信息？",
    "气血固本口服液属于什么类型的产品？",
    "请简单介绍气血固本口服液的基本属性。",
    "气血固本口服液常见的产品信息有哪些？",
    "购买中成药时通常应该关注哪些批准信息？",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "文心连续采集能力与"
            "风控边界探测"
        )
    )

    parser.add_argument(
        "--count",
        type=int,
        default=4,
        help="连续请求数量，默认 4",
    )

    parser.add_argument(
        "--min-delay",
        type=float,
        default=2.0,
    )

    parser.add_argument(
        "--max-delay",
        type=float,
        default=4.0,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.count <= 0:
        raise ValueError(
            "--count 必须大于 0"
        )

    count = min(
        args.count,
        len(QUESTIONS),
    )

    results: list[
        CapacityResult
    ] = []

    print("=" * 80)
    print("WENXIN CAPACITY PROBE")
    print("=" * 80)

    print(
        "REQUEST COUNT:",
        count,
    )

    print(
        "INTERVAL:",
        f"{args.min_delay}"
        f" - "
        f"{args.max_delay}s",
    )

    with sync_playwright() as p:
        browser = (
            p.chromium
            .connect_over_cdp(
                "http://127.0.0.1:9222"
            )
        )

        if not browser.contexts:
            raise RuntimeError(
                "没有可用 BrowserContext"
            )

        page = None

        for context in browser.contexts:
            for candidate in reversed(
                    context.pages
            ):
                if (
                        "wenxin.baidu.com"
                        in candidate.url
                ):
                    page = candidate
                    break

            if page:
                break

        if page is None:
            raise RuntimeError(
                "没有找到文心页面"
            )

        client = WenxinClient(
            page=page,
            answer_timeout=180,
        )

        for index in range(count):
            question = QUESTIONS[
                index
            ]

            print()
            print("-" * 80)
            print(
                f"[{index + 1}/{count}]"
            )
            print(
                "QUESTION:",
                question,
            )

            started = (
                time.monotonic()
            )

            try:
                answer = client.collect(
                    question=question,
                    mode=WenxinMode.FAST,
                )

                elapsed = (
                        time.monotonic()
                        - started
                )

                risk = detect_risk(
                    answer.text,
                )

                result = CapacityResult(
                    index=index + 1,
                    question=question,
                    success=True,
                    elapsed_seconds=(
                        elapsed
                    ),
                    answer_length=len(
                        answer.text
                    ),
                    source_count=len(
                        answer.sources
                    ),
                    session_id=(
                        answer.session_id
                    ),
                    risk_detected=risk,
                )

                results.append(
                    result
                )

                print(
                    "[SUCCESS]",
                    f"time={elapsed:.1f}s",
                    f"answer={len(answer.text)}",
                    f"sources={len(answer.sources)}",
                    f"session={answer.session_id}",
                )

                if risk:
                    print(
                        "[RISK] "
                        "页面回答中检测到"
                        "疑似风控提示，停止。"
                    )
                    break

            except Exception as exc:
                elapsed = (
                        time.monotonic()
                        - started
                )

                error = str(
                    exc
                )

                page_text = ""

                try:
                    page_text = (
                        page.locator(
                            "body"
                        ).inner_text(
                            timeout=3000
                        )
                    )
                except Exception:
                    pass

                risk = detect_risk(
                    error,
                    page_text,
                )

                results.append(
                    CapacityResult(
                        index=index + 1,
                        question=question,
                        success=False,
                        elapsed_seconds=(
                            elapsed
                        ),
                        error=error,
                        risk_detected=risk,
                    )
                )

                print(
                    "[FAILED]",
                    repr(exc),
                )

                if risk:
                    print(
                        "[RISK] "
                        "检测到疑似风控，"
                        "立即停止探测。"
                    )

                break

            if index + 1 < count:
                delay = random.uniform(
                    args.min_delay,
                    args.max_delay,
                )

                print(
                    f"[DELAY] {delay:.1f}s"
                )

                page.wait_for_timeout(
                    int(
                        delay * 1000
                    )
                )

    print()
    print("=" * 80)
    print("CAPACITY SUMMARY")
    print("=" * 80)

    success_count = sum(
        result.success
        for result in results
    )

    failure_count = (
            len(results)
            - success_count
    )

    risk_count = sum(
        result.risk_detected
        for result in results
    )

    print(
        "ATTEMPTED:",
        len(results),
    )

    print(
        "SUCCESS:",
        success_count,
    )

    print(
        "FAILED:",
        failure_count,
    )

    print(
        "RISK DETECTED:",
        risk_count,
    )

    for result in results:
        print(
            f"#{result.index}",
            "PASS"
            if result.success
            else "FAIL",
            f"{result.elapsed_seconds:.1f}s",
            f"answer={result.answer_length}",
            f"sources={result.source_count}",
            (
                "RISK"
                if result.risk_detected
                else ""
            ),
        )

    print()

    if (
            success_count
            == count
            and risk_count == 0
    ):
        print(
            "CAPACITY PROBE: PASS"
        )
    elif risk_count:
        print(
            "CAPACITY PROBE: "
            "RISK_DETECTED"
        )
    else:
        print(
            "CAPACITY PROBE: "
            "PASS_WITH_WARNINGS"
        )

    print("=" * 80)


if __name__ == "__main__":
    main()
