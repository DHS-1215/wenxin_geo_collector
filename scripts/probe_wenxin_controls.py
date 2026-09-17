from playwright.sync_api import sync_playwright


def print_html(title: str, locator, limit: int = 10) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

    count = locator.count()
    print(f"COUNT: {count}")

    shown = 0

    for i in range(count):
        if shown >= limit:
            break

        item = locator.nth(i)

        try:
            if not item.is_visible():
                continue

            text = item.inner_text(timeout=1000).strip()
            html = item.evaluate("el => el.outerHTML")

            print(f"\n[{i}] TEXT={text!r}")
            print(html[:2000])

            shown += 1

        except Exception as exc:
            print(f"\n[{i}] FAILED: {exc}")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(
            "http://127.0.0.1:9222"
        )

        context = browser.contexts[0]
        page = context.pages[-1]

        textarea = page.locator("#chat-textarea")
        mode_button = page.locator(
            '[data-testid="chat-mode-selector"]'
        )

        print("=" * 80)
        print("WENXIN CONTROL PROBE")
        print("=" * 80)

        print("URL:", page.url)

        # ------------------------------------------------------------
        # 1. textarea 本体
        # ------------------------------------------------------------

        print_html(
            "TEXTAREA",
            textarea,
            limit=2,
        )

        # ------------------------------------------------------------
        # 2. textarea 向上找父节点
        # ------------------------------------------------------------

        print("\n" + "=" * 80)
        print("TEXTAREA PARENT CHAIN")
        print("=" * 80)

        parent = textarea

        for level in range(1, 7):
            parent = parent.locator("..")

            try:
                html = parent.evaluate(
                    "el => el.outerHTML"
                )

                print(f"\nLEVEL {level}")
                print(html[:4000])

            except Exception as exc:
                print(
                    f"\nLEVEL {level} FAILED:",
                    exc,
                )
                break

        # ------------------------------------------------------------
        # 3. 填入文字，观察发送控件是否出现
        # ------------------------------------------------------------

        print("\n" + "=" * 80)
        print("FILL TEXT AND PROBE")
        print("=" * 80)

        textarea.fill("测试")

        page.wait_for_timeout(500)

        print_html(
            "VISIBLE BUTTON AFTER FILL",
            page.locator("button"),
            limit=20,
        )

        print_html(
            "VISIBLE ROLE=BUTTON AFTER FILL",
            page.get_by_role("button"),
            limit=20,
        )

        # 搜索可能的发送控件
        candidates = page.locator(
            """
            [aria-label*="发送"],
            [title*="发送"],
            [data-testid*="send"],
            [class*="send"],
            [class*="Send"],
            [class*="submit"],
            [class*="Submit"]
            """
        )

        print_html(
            "SEND CANDIDATES",
            candidates,
            limit=20,
        )

        # 清空，不真正发送
        textarea.fill("")

        # ------------------------------------------------------------
        # 4. 打开模式菜单
        # ------------------------------------------------------------

        print("\n" + "=" * 80)
        print("MODE MENU")
        print("=" * 80)

        print("MODE BEFORE:", mode_button.inner_text().strip())

        mode_button.click()
        page.wait_for_timeout(500)

        print_html(
            "VISIBLE ROLE=MENU",
            page.locator('[role="menu"]'),
            limit=10,
        )

        print_html(
            "VISIBLE ROLE=MENUITEM",
            page.locator('[role="menuitem"]'),
            limit=20,
        )

        print_html(
            "VISIBLE ROLE=OPTION",
            page.locator('[role="option"]'),
            limit=20,
        )

        print_html(
            "VISIBLE BUTTON IN OPEN MENU STATE",
            page.locator("button"),
            limit=30,
        )

        # 常见模式关键词
        for keyword in [
            "快速",
            "深度",
            "思考",
            "搜索",
            "研究",
            "智能",
            "专业",
        ]:
            locator = page.get_by_text(
                keyword,
                exact=False,
            )

            print_html(
                f"MODE KEYWORD: {keyword}",
                locator,
                limit=10,
            )

        # ESC 关闭菜单
        page.keyboard.press("Escape")

        # ------------------------------------------------------------
        # 5. 新对话父节点
        # ------------------------------------------------------------

        print("\n" + "=" * 80)
        print("NEW CHAT")
        print("=" * 80)

        new_chat_text = page.get_by_text(
            "新对话",
            exact=True,
        ).first

        print_html(
            "NEW CHAT TEXT",
            new_chat_text,
            limit=1,
        )

        current = new_chat_text

        for level in range(1, 6):
            current = current.locator("..")

            try:
                html = current.evaluate(
                    "el => el.outerHTML"
                )

                print(f"\nNEW CHAT PARENT LEVEL {level}")
                print(html[:3000])

            except Exception as exc:
                print(
                    f"LEVEL {level} FAILED:",
                    exc,
                )
                break


if __name__ == "__main__":
    main()
