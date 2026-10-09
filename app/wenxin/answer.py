from __future__ import annotations

import re

from playwright.sync_api import Locator

from app.wenxin.selectors import (
    CITATION_SELECTOR,
    MARKDOWN_CONTENT_SELECTOR,
)


def clean_text(text: str) -> str:
    """清理文心回答正文中的特殊字符和多余空行。"""

    text = text.replace("\u200b", "")
    text = text.replace("\u200c", "")
    text = text.replace("\ufeff", "")

    text = re.sub(
        r"[ \t]+\n",
        "\n",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def extract_answer_text(answer: Locator) -> str:
    """
    从单个文心回答节点中提取纯正文。

    会删除正文中的引用标签，例如：
    海外官网、参考文档等。
    """

    markdown = answer.locator(
        MARKDOWN_CONTENT_SELECTOR
    )

    if markdown.count() == 0:
        return ""

    best_markdown = None
    best_length = 0

    for i in range(markdown.count()):
        candidate = markdown.nth(i)

        candidate_text = (
            candidate.inner_text().strip()
        )

        if len(candidate_text) > best_length:
            best_markdown = candidate
            best_length = len(candidate_text)

    if best_markdown is None:
        return ""

    markdown = best_markdown

    text = markdown.evaluate(
        """
        (el, citationSelector) => {
            const clone = el.cloneNode(true);

            clone.querySelectorAll(
                citationSelector
            ).forEach(node => node.remove());

            return clone.innerText || "";
        }
        """,
        CITATION_SELECTOR,
    )

    return clean_text(text)
