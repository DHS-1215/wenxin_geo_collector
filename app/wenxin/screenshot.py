from __future__ import annotations

import hashlib
import struct

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Locator, Page

@dataclass(slots=True)
class ScreenshotInfo:
    path: str
    sha256: str
    size_bytes: int
    width: int
    height: int


def _read_png_size(
    data: bytes,
) -> tuple[int, int]:
    """
    直接读取 PNG IHDR。
    不额外引入 Pillow。
    """

    signature = (
        b"\x89PNG\r\n\x1a\n"
    )

    if not data.startswith(signature):
        raise ValueError(
            "截图不是有效 PNG"
        )

    if len(data) < 24:
        raise ValueError(
            "PNG 数据长度异常"
        )

    width, height = struct.unpack(
        ">II",
        data[16:24],
    )

    return width, height


def capture_answer_screenshot(
    *,
    page: Page,
    answer_node: Locator,
    output_path: Path,
) -> ScreenshotInfo:
    """
    文心回答完成后的证据截图。

    与现有在线数据包保持一致：
    使用当前浏览器 viewport 截图，
    不使用 full_page。
    """

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 尽量让当前回答进入可视区域。
    try:
        answer_node.scroll_into_view_if_needed(
            timeout=5000,
        )
    except Exception:
        # 页面通常本身就在最新回答附近，
        # scroll 失败不直接阻断截图。
        pass

    page.wait_for_timeout(
        300
    )

    image_bytes = page.screenshot(
        path=str(output_path),
        type="png",
        full_page=False,
        animations="disabled",
        caret="hide",
    )

    width, height = (
        _read_png_size(
            image_bytes
        )
    )

    sha256 = hashlib.sha256(
        image_bytes
    ).hexdigest()

    return ScreenshotInfo(
        path=(
            output_path
            .as_posix()
        ),
        sha256=sha256,
        size_bytes=len(
            image_bytes
        ),
        width=width,
        height=height,
    )

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)


def build_runtime_screenshot_path(
    *,
    batch_id: str,
    task_id: str,
) -> Path:
    """
    采集阶段截图临时存放位置。

    注意：
    这里是运行时路径。
    最终 GEO Package 会由 Exporter
    转成 screenshots/{task_id}.png。
    """

    return (
        PROJECT_ROOT
        / "output"
        / "screenshots"
        / batch_id
        / f"{task_id}.png"
    )