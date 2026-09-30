from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from importlib import metadata
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[1]

REQUIREMENTS_PATH = (
    ROOT_DIR
    / "requirements.txt"
)

OUTPUT_DIR = (
    ROOT_DIR
    / "output"
)

CHECKPOINT_DIR = (
    OUTPUT_DIR
    / "checkpoints"
)

CDP_URL = (
    "http://127.0.0.1:9222"
)

WENXIN_DOMAIN = (
    "wenxin.baidu.com"
)

TEXTAREA_SELECTOR = (
    "#chat-textarea"
)


PASS_COUNT = 0
FAIL_COUNT = 0
WARN_COUNT = 0


def print_header() -> None:
    print("=" * 80)
    print(
        "WENXIN SERVER HEALTH CHECK"
    )
    print("=" * 80)
    print()


def pass_check(
    name: str,
    detail: str = "",
) -> None:
    global PASS_COUNT

    PASS_COUNT += 1

    if detail:
        print(
            f"[PASS] {name}: {detail}"
        )
    else:
        print(
            f"[PASS] {name}"
        )


def fail_check(
    name: str,
    detail: str = "",
) -> None:
    global FAIL_COUNT

    FAIL_COUNT += 1

    if detail:
        print(
            f"[FAIL] {name}: {detail}"
        )
    else:
        print(
            f"[FAIL] {name}"
        )


def warn_check(
    name: str,
    detail: str = "",
) -> None:
    global WARN_COUNT

    WARN_COUNT += 1

    if detail:
        print(
            f"[WARN] {name}: {detail}"
        )
    else:
        print(
            f"[WARN] {name}"
        )


def check_python_environment() -> None:
    """
    确认当前 Python 来自项目虚拟环境。
    """

    executable = Path(
        sys.executable
    ).resolve()

    expected_venv = (
        ROOT_DIR
        / ".venv"
    ).resolve()

    try:
        executable.relative_to(
            expected_venv
        )
    except ValueError:
        fail_check(
            "Python virtualenv",
            (
                "当前 Python 不属于项目 .venv："
                f"{executable}"
            ),
        )
        return

    pass_check(
        "Python virtualenv",
        str(executable),
    )


def parse_requirements() -> list[
    tuple[str, str | None]
]:
    """
    当前项目 requirements.txt 使用简单的：
        package==version

    同时兼容以后出现未固定版本的包。
    """

    text = (
        REQUIREMENTS_PATH
        .read_text(
            encoding="utf-8-sig"
        )
    )

    requirements: list[
        tuple[str, str | None]
    ] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
        ):
            continue

        if "==" in line:
            name, version = (
                line.split(
                    "==",
                    1,
                )
            )

            requirements.append(
                (
                    name.strip(),
                    version.strip(),
                )
            )

        else:
            requirements.append(
                (
                    line,
                    None,
                )
            )

    return requirements


def check_requirements_file() -> None:
    if not REQUIREMENTS_PATH.exists():
        fail_check(
            "requirements.txt",
            "文件不存在",
        )
        return

    try:
        requirements = (
            parse_requirements()
        )
    except Exception as exc:
        fail_check(
            "requirements.txt",
            str(exc),
        )
        return

    if not requirements:
        fail_check(
            "requirements.txt",
            "文件为空",
        )
        return

    pass_check(
        "requirements.txt",
        (
            f"{len(requirements)} "
            "个直接依赖"
        ),
    )


def check_requirement_versions() -> None:
    if not REQUIREMENTS_PATH.exists():
        return

    try:
        requirements = (
            parse_requirements()
        )
    except Exception:
        return

    errors: list[str] = []

    for package_name, expected in (
        requirements
    ):
        try:
            installed = (
                metadata.version(
                    package_name
                )
            )
        except (
            metadata
            .PackageNotFoundError
        ):
            errors.append(
                f"{package_name} 未安装"
            )
            continue

        if (
            expected
            and installed != expected
        ):
            errors.append(
                (
                    f"{package_name}: "
                    f"需要 {expected}, "
                    f"实际 {installed}"
                )
            )

    if errors:
        fail_check(
            "Requirements versions",
            "; ".join(errors),
        )
        return

    pass_check(
        "Requirements versions",
        "与 requirements.txt 一致",
    )


def check_playwright_import() -> None:
    try:
        importlib.import_module(
            "playwright.sync_api"
        )
    except Exception as exc:
        fail_check(
            "Playwright import",
            str(exc),
        )
        return

    pass_check(
        "Playwright import"
    )


def check_wenxin_core_imports() -> None:
    modules = (
        "app.wenxin.client",
        "app.wenxin.batch",
        "app.wenxin.checkpoint",
        "app.wenxin.exporter",
        "app.wenxin.verifier",
        "app.wenxin.error_classifier",
        "app.wenxin.exceptions",
    )

    errors: list[str] = []

    for module_name in modules:
        try:
            importlib.import_module(
                module_name
            )
        except Exception as exc:
            errors.append(
                (
                    f"{module_name}: "
                    f"{exc}"
                )
            )

    if errors:
        fail_check(
            "Wenxin core imports",
            "; ".join(errors),
        )
        return

    pass_check(
        "Wenxin core imports"
    )


def check_pip_dependencies() -> None:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "check",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:
        fail_check(
            "pip check",
            str(exc),
        )
        return

    output = (
        result.stdout.strip()
        or result.stderr.strip()
    )

    if result.returncode != 0:
        fail_check(
            "pip check",
            output,
        )
        return

    pass_check(
        "pip check",
        (
            output
            or "依赖完整"
        ),
    )


def find_chrome() -> Path | None:
    candidates: list[
        Path
    ] = []

    program_files = os.environ.get(
        "ProgramFiles"
    )

    program_files_x86 = os.environ.get(
        "ProgramFiles(x86)"
    )

    local_app_data = os.environ.get(
        "LOCALAPPDATA"
    )

    if program_files:
        candidates.append(
            Path(program_files)
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe"
        )

    if program_files_x86:
        candidates.append(
            Path(program_files_x86)
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe"
        )

    if local_app_data:
        candidates.append(
            Path(local_app_data)
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe"
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    command = shutil.which(
        "chrome"
    )

    if command:
        return Path(command)

    command = shutil.which(
        "chrome.exe"
    )

    if command:
        return Path(command)

    return None


def check_chrome_executable() -> None:
    chrome = find_chrome()

    if chrome is None:
        fail_check(
            "Google Chrome",
            "未找到 chrome.exe",
        )
        return

    pass_check(
        "Google Chrome",
        str(chrome),
    )


def get_cdp_version() -> dict:
    url = (
        f"{CDP_URL}"
        "/json/version"
    )

    with urllib.request.urlopen(
        url,
        timeout=3,
    ) as response:
        raw = response.read()

    return json.loads(
        raw.decode("utf-8")
    )


def check_cdp() -> bool:
    try:
        data = get_cdp_version()
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        fail_check(
            "Chrome CDP 9222",
            str(exc),
        )
        return False

    browser_name = data.get(
        "Browser",
        "unknown",
    )

    websocket_url = data.get(
        "webSocketDebuggerUrl"
    )

    if not websocket_url:
        fail_check(
            "Chrome CDP 9222",
            (
                "服务存在，但缺少 "
                "webSocketDebuggerUrl"
            ),
        )
        return False

    pass_check(
        "Chrome CDP 9222",
        browser_name,
    )

    return True


def check_output_writable() -> None:
    test_file = (
        OUTPUT_DIR
        / ".wenxin_health_check.tmp"
    )

    try:
        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        CHECKPOINT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        test_file.write_text(
            "health-check",
            encoding="utf-8",
        )

        content = (
            test_file.read_text(
                encoding="utf-8"
            )
        )

        if content != "health-check":
            raise RuntimeError(
                "写入后读取内容不一致"
            )

    except Exception as exc:
        fail_check(
            "Output writable",
            str(exc),
        )
        return

    finally:
        try:
            test_file.unlink(
                missing_ok=True
            )
        except Exception:
            pass

    pass_check(
        "Output writable",
        str(OUTPUT_DIR),
    )


def check_wenxin_browser() -> None:
    try:
        with sync_playwright() as p:
            browser = (
                p.chromium
                .connect_over_cdp(
                    CDP_URL,
                    timeout=5000,
                )
            )

            pages = []

            for context in (
                browser.contexts
            ):
                pages.extend(
                    context.pages
                )

            wenxin_pages = [
                page
                for page in pages
                if (
                    WENXIN_DOMAIN
                    in page.url
                )
            ]

            if not wenxin_pages:
                fail_check(
                    "Wenxin page",
                    (
                        "CDP 已连接，"
                        "但没有打开文心页面"
                    ),
                )
                return

            page = wenxin_pages[-1]

            pass_check(
                "Wenxin page",
                page.url,
            )

            textarea = (
                page
                .locator(
                    TEXTAREA_SELECTOR
                )
                .first
            )

            textarea.wait_for(
                state="visible",
                timeout=5000,
            )

            pass_check(
                "Wenxin textarea",
                TEXTAREA_SELECTOR,
            )

            check_login_cookie(
                browser
            )

    except Exception as exc:
        fail_check(
            "Wenxin browser readiness",
            str(exc),
        )


def check_login_cookie(
    browser,
) -> None:
    """
    百度登录态属于网页实现细节，
    不使用它作为强制失败条件。

    这里只检查常见百度登录 Cookie，
    没检测到时给 WARN，
    最终仍以页面是否可操作为准。
    """

    cookie_names: set[str] = set()

    try:
        for context in (
            browser.contexts
        ):
            for cookie in (
                context.cookies()
            ):
                cookie_names.add(
                    cookie.get(
                        "name",
                        "",
                    )
                )

    except Exception as exc:
        warn_check(
            "Baidu login state",
            (
                "无法读取 Cookie："
                f"{exc}"
            ),
        )
        return

    known_login_cookies = {
        "BDUSS",
        "BDUSS_BFESS",
        "STOKEN",
    }

    matched = (
        cookie_names
        & known_login_cookies
    )

    if matched:
        pass_check(
            "Baidu login state",
            (
                "发现登录 Cookie: "
                + ", ".join(
                    sorted(matched)
                )
            ),
        )

        return

    warn_check(
        "Baidu login state",
        (
            "未检测到常见登录 Cookie，"
            "请人工确认当前百度账号"
            "已经登录"
        ),
    )


def main() -> int:
    print_header()

    check_python_environment()
    check_requirements_file()
    check_requirement_versions()
    check_playwright_import()
    check_wenxin_core_imports()
    check_pip_dependencies()

    check_chrome_executable()
    check_output_writable()

    cdp_ready = check_cdp()

    if cdp_ready:
        check_wenxin_browser()

    print()
    print("=" * 80)

    print(
        f"PASS: {PASS_COUNT}"
    )

    print(
        f"WARN: {WARN_COUNT}"
    )

    print(
        f"FAIL: {FAIL_COUNT}"
    )

    print("-" * 80)

    if FAIL_COUNT:
        print(
            "WENXIN SERVER CHECK: FAILED"
        )
        print("=" * 80)

        return 1

    print(
        "WENXIN SERVER CHECK: PASS"
    )
    print("=" * 80)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )