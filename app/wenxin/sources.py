from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Locator

from app.wenxin.selectors import SOURCE_SELECTOR
from app.wenxin.types import WenxinSource


def get_domain(url: str) -> str:
    """从 URL 中提取域名。"""

    if not url:
        return ""

    try:
        return urlparse(url).netloc.lower()
    except ValueError:
        return ""


def extract_source_tags(item: Locator) -> list[str]:
    """提取信源标签，例如“海外官网”."""

    tags = item.locator(
        "span[class*='_tag_']"
    ).all_inner_texts()

    return [
        tag.strip()
        for tag in tags
        if tag.strip()
    ]


def extract_sources(
        answer: Locator,
) -> list[WenxinSource]:
    """从单个文心回答节点中提取全部参考信源。"""

    items = answer.locator(
        SOURCE_SELECTOR
    )

    sources: list[WenxinSource] = []

    for index in range(
            items.count()
    ):
        item = items.nth(index)

        raw = item.get_attribute(
            "data-long-press-ext-info"
        )

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        title = str(
            data.get("linkTitle") or ""
        ).strip()

        url = str(
            data.get("link") or ""
        ).strip()

        if not title and not url:
            continue

        source = WenxinSource(
            rank=index + 1,
            title=title,
            url=url,
            domain=get_domain(url),
            tags=extract_source_tags(
                item
            ),
        )

        sources.append(
            source
        )

    return sources
