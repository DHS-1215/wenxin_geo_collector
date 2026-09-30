from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

from datetime import datetime, timezone
from playwright.sync_api import Locator, Page

from app.wenxin.answer import extract_answer_text
from app.wenxin.selectors import (
    ANSWER_SELECTOR,
    MARKDOWN_SELECTOR,
    MODE_SELECTOR,
    NEW_CHAT_SELECTOR,
    SEND_BUTTON_SELECTOR,
    TEXTAREA_SELECTOR,
    MARKDOWN_CONTENT_SELECTOR,
)
from app.wenxin.sources import extract_sources
from app.wenxin.types import (
    WenxinAnswer,
    WenxinMode,
)

from app.wenxin.error_classifier import (
    raise_for_wenxin_control,
)

from app.wenxin.screenshot import (
    capture_answer_screenshot,
)


class WenxinClient:
    """文心助手网页采集客户端。"""

    def __init__(
            self,
            page: Page,
            answer_timeout: float = 180.0,
            min_action_delay: float = 0.3,
            max_action_delay: float = 0.8,
    ) -> None:
        self.page = page
        self.answer_timeout = answer_timeout
        self.min_action_delay = min_action_delay
        self.max_action_delay = max_action_delay

    # ============================================================
    # 新对话
    # ============================================================

    def new_chat(self) -> None:
        """进入一个新的空白对话。"""

        button = self.page.locator(
            NEW_CHAT_SELECTOR
        )

        button.wait_for(
            state="visible",
            timeout=10000,
        )

        button.click()

        self._random_action_delay(
            0.5,
            1.0,
        )

        textarea = self.page.locator(
            TEXTAREA_SELECTOR
        )

        textarea.wait_for(
            state="visible",
            timeout=10000,
        )

        # 等旧回答从页面中清掉
        deadline = time.monotonic() + 10.0

        while time.monotonic() < deadline:
            if (
                    self.page.locator(
                        ANSWER_SELECTOR
                    ).count()
                    == 0
            ):
                return

            self.page.wait_for_timeout(
                200
            )

        raise TimeoutError(
            "新对话页面未成功清空"
        )

    # ============================================================
    # 模式
    # ============================================================

    def get_mode(self) -> WenxinMode:
        """读取当前回答模式。"""

        button = self.page.locator(
            MODE_SELECTOR
        )

        text = button.inner_text().strip()

        if "工作任务" in text:
            return WenxinMode.TASK

        return WenxinMode.FAST

    def set_mode(
            self,
            mode: WenxinMode,
    ) -> None:
        """切换文心回答模式。"""

        if self.get_mode() == mode:
            return

        button = self.page.locator(
            MODE_SELECTOR
        )

        button.click()

        self._random_action_delay(
            0.3,
            0.6,
        )

        option = self.page.locator(
            (
                '[role="menuitemradio"]'
                f'[data-chat-mode="{mode.value}"]'
            )
        )

        option.wait_for(
            state="visible",
            timeout=5000,
        )

        option.click()

        self._random_action_delay(
            0.4,
            0.8,
        )

        deadline = time.monotonic() + 5.0

        while time.monotonic() < deadline:
            if self.get_mode() == mode:
                return

            self.page.wait_for_timeout(
                100
            )

        raise TimeoutError(
            f"回答模式切换失败: {mode.value}"
        )

    # ============================================================
    # 发送问题
    # ============================================================

    def send(
            self,
            question: str,
    ) -> int:
        """
        输入并发送问题。

        返回发送前已有回答数量，
        用于后续判断新回答是否出现。
        """

        question = question.strip()

        if not question:
            raise ValueError(
                "question 不能为空"
            )

        textarea = self.page.locator(
            TEXTAREA_SELECTOR
        )

        textarea.wait_for(
            state="visible",
            timeout=10000,
        )

        previous_answer_count = (
            self.page.locator(
                ANSWER_SELECTOR
            ).count()
        )

        textarea.fill(
            question
        )

        self._random_action_delay(
            0.4,
            0.9,
        )

        send_button = self.page.locator(
            SEND_BUTTON_SELECTOR
        ).first

        send_button.wait_for(
            state="visible",
            timeout=5000,
        )

        send_button.click()

        self._random_action_delay(
            0.3,
            0.6,
        )

        return previous_answer_count

    # ============================================================
    # 等待回答
    # ============================================================

    def wait_answer(
            self,
            previous_answer_count: int,
    ) -> Locator:
        """等待本次回答生成完成。"""

        started = time.monotonic()
        last_status: str | None = None

        while True:
            elapsed = (
                    time.monotonic()
                    - started
            )

            answers = self.page.locator(
                ANSWER_SELECTOR
            )

            if (
                    answers.count()
                    > previous_answer_count
            ):
                answer = answers.last

                status = answer.get_attribute(
                    "data-status"
                )

                if status != last_status:
                    print(
                        f"[WENXIN] "
                        f"T+{elapsed:.1f}s "
                        f"status={status}"
                    )

                    last_status = status

                if status == "COMPLETE":
                    markdown = answer.locator(
                        MARKDOWN_SELECTOR
                    )

                    if (
                            markdown.count()
                            and markdown.last.inner_text().strip()
                    ):
                        return answer

            if elapsed >= self.answer_timeout:
                raise TimeoutError(
                    "等待文心回答完成超时"
                )

            self.page.wait_for_timeout(
                500
            )

    # ============================================================
    # 会话 ID
    # ============================================================

    def get_session_id(self) -> str:
        """从当前 URL 获取文心会话 ID。"""

        match = re.search(
            r"/search/(\d+)",
            self.page.url,
        )

        if not match:
            return ""

        return match.group(1)

    # ============================================================
    # 回答元数据
    # ============================================================

    @staticmethod
    def extract_answer_meta(
            answer: Locator,
    ) -> tuple[str | None, bool | None]:
        """提取实际使用模型和 deepSearch 状态。"""

        markdown = answer.locator(
            MARKDOWN_SELECTOR
        )

        if markdown.count() == 0:
            return None, None

        raw = markdown.last.get_attribute(
            "data-show-log"
        )

        if not raw:
            return None, None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None, None

        used_model = (
                data.get("usedModel")
                or {}
        )

        model_name = used_model.get(
            "modelName"
        )

        model_function = (
                used_model.get(
                    "modelFunction"
                )
                or {}
        )

        raw_deep_search = (
            model_function.get(
                "deepSearch"
            )
        )

        if raw_deep_search is None:
            deep_search = None
        else:
            deep_search = str(
                raw_deep_search
            ).lower() in {
                              "1",
                              "true",
                              "yes",
                          }

        return (
            model_name,
            deep_search,
        )

    # ============================================================
    # 完整单题采集
    # ============================================================

    def collect(
            self,
            question: str,
            mode: WenxinMode,
            screenshot_output_path: Path | None = None,
    ) -> WenxinAnswer:
        """完成一次完整的文心单题采集。"""

        self.new_chat()

        self.set_mode(
            mode
        )

        previous_count = self.send(
            question
        )

        try:
            answer_node = self.wait_answer(
                previous_count
            )

        except Exception as exc:
            page_text = (
                self._safe_page_text()
            )

            raise_for_wenxin_control(
                str(exc),
                page_text,
            )

            raise

        text = extract_answer_text(
            answer_node
        )

        raw_markdown = answer_node.locator(
            MARKDOWN_CONTENT_SELECTOR
        )

        raw_text = ""

        if raw_markdown.count():
            raw_text = (
                raw_markdown
                .last
                .inner_text()
                .strip()
            )

        raise_for_wenxin_control(
            text
        )

        sources = extract_sources(
            answer_node
        )

        screenshot_info = None

        if screenshot_output_path is not None:
            screenshot_info = (
                capture_answer_screenshot(
                    page=self.page,
                    answer_node=answer_node,
                    output_path=(
                        screenshot_output_path
                    ),
                )
            )

        (
            model_name,
            deep_search,
        ) = self.extract_answer_meta(
            answer_node
        )

        return WenxinAnswer(
            screenshot_path=(
                screenshot_info.path
                if screenshot_info
                else None
            ),
            screenshot_sha256=(
                screenshot_info.sha256
                if screenshot_info
                else None
            ),
            screenshot_size_bytes=(
                screenshot_info.size_bytes
                if screenshot_info
                else None
            ),
            screenshot_width=(
                screenshot_info.width
                if screenshot_info
                else None
            ),
            screenshot_height=(
                screenshot_info.height
                if screenshot_info
                else None
            ),
            question=question,
            text=text,
            raw_text=raw_text,
            session_id=self.get_session_id(),
            conversation_url=self.page.url,
            collected_at=(
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            mode=mode,
            model_name=model_name,
            deep_search=deep_search,
            sources=sources,

        )

    # ============================================================
    # 操作缓冲
    # ============================================================

    def _random_action_delay(
            self,
            min_seconds: float | None = None,
            max_seconds: float | None = None,
    ) -> None:
        """页面操作之间增加轻量随机缓冲。"""

        minimum = (
            self.min_action_delay
            if min_seconds is None
            else min_seconds
        )

        maximum = (
            self.max_action_delay
            if max_seconds is None
            else max_seconds
        )

        delay = random.uniform(
            minimum,
            maximum,
        )

        self.page.wait_for_timeout(
            int(delay * 1000)
        )

    def _safe_page_text(
            self,
    ) -> str:
        try:
            return (
                self.page
                .locator("body")
                .inner_text(
                    timeout=3000
                )
            )
        except Exception:
            return ""
