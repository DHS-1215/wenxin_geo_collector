from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT_DIR = Path(__file__).resolve().parents[1]

DIST_DIR = ROOT_DIR / "dist"

PACKAGE_NAME = "wenxin_geo_collector"

STAGING_DIR = (
        DIST_DIR
        / "_server_staging"
        / PACKAGE_NAME
)

ZIP_PATH = (
        DIST_DIR
        / "wenxin_geo_collector_server.zip"
)

SHA256_PATH = (
        DIST_DIR
        / "wenxin_geo_collector_server.zip.sha256"
)

REQUIRED_ROOT_FILES = (
    "requirements.txt",
    "README.md",
    "setup_wenxin_server.bat",
    "run_wenxin_server.bat",
)

OPTIONAL_ROOT_FILES = (
    "run_wenxin.bat",
)

INCLUDE_DIRS = (
    "app",
    "input",
    "tests",
)

INCLUDE_SCRIPTS = (
    "run_wenxin_pipeline.py",
    "check_wenxin_server.py",
    "probe_wenxin_capacity.py",
    "probe_wenxin_controls.py",
)

EXCLUDED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".git",
    ".venv",
    "output",
    "runtime",
    "logs",
    "dist",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def should_exclude(
        path: Path,
) -> bool:
    if any(
            part in EXCLUDED_NAMES
            for part in path.parts
    ):
        return True

    if path.suffix.lower() in (
            EXCLUDED_SUFFIXES
    ):
        return True

    return False


def copy_directory(
        source: Path,
        destination: Path,
) -> None:
    for path in source.rglob("*"):
        relative = path.relative_to(
            source
        )

        if should_exclude(relative):
            continue

        target = (
                destination
                / relative
        )

        if path.is_dir():
            target.mkdir(
                parents=True,
                exist_ok=True,
            )
            continue

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            path,
            target,
        )


def validate_source() -> None:
    errors: list[str] = []

    for filename in (
            REQUIRED_ROOT_FILES
    ):
        path = ROOT_DIR / filename

        if not path.is_file():
            errors.append(
                f"缺少必要文件: {filename}"
            )

    for dirname in INCLUDE_DIRS:
        path = ROOT_DIR / dirname

        if not path.is_dir():
            errors.append(
                f"缺少必要目录: {dirname}"
            )

    scripts_dir = (
            ROOT_DIR
            / "scripts"
    )

    for filename in INCLUDE_SCRIPTS:
        path = (
                scripts_dir
                / filename
        )

        if not path.is_file():
            errors.append(
                (
                    "缺少必要脚本: "
                    f"scripts/{filename}"
                )
            )

    if errors:
        raise RuntimeError(
            "\n".join(errors)
        )


def prepare_staging() -> None:
    staging_parent = (
        STAGING_DIR.parent
    )

    if staging_parent.exists():
        shutil.rmtree(
            staging_parent
        )

    STAGING_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def copy_root_files() -> None:
    for filename in (
            REQUIRED_ROOT_FILES
    ):
        shutil.copy2(
            ROOT_DIR / filename,
            STAGING_DIR / filename,
        )

    for filename in (
            OPTIONAL_ROOT_FILES
    ):
        source = (
                ROOT_DIR
                / filename
        )

        if source.is_file():
            shutil.copy2(
                source,
                STAGING_DIR / filename,
            )


def copy_project_directories() -> None:
    for dirname in INCLUDE_DIRS:
        source = (
                ROOT_DIR
                / dirname
        )

        destination = (
                STAGING_DIR
                / dirname
        )

        destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        copy_directory(
            source,
            destination,
        )


def copy_scripts() -> None:
    destination = (
            STAGING_DIR
            / "scripts"
    )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    source_dir = (
            ROOT_DIR
            / "scripts"
    )

    for filename in INCLUDE_SCRIPTS:
        shutil.copy2(
            source_dir / filename,
            destination / filename,
        )


def create_runtime_placeholders() -> None:
    """
    只创建目录说明，不携带任何真实登录态、
    output 或服务器运行数据。
    """

    runtime_readme = (
            STAGING_DIR
            / "SERVER_FIRST_RUN.txt"
    )

    runtime_readme.write_text(
        (
            "文心 GEO 服务器部署说明\n"
            "========================\n\n"
            "首次部署：\n"
            "1. python -m venv .venv\n"
            "2. .venv\\Scripts\\python.exe "
            "-m pip install -r requirements.txt\n"
            "3. .venv\\Scripts\\python.exe "
            "-m pytest -q\n"
            "4. 双击 run_wenxin_server.bat\n"
            "5. 首次启动后，在服务器 Chrome 中"
            "人工登录百度账号\n\n"
            "以下目录由服务器自行生成：\n"
            "- .venv\\\n"
            "- output\\\n"
            "- runtime\\chrome_profile\\\n"
            "- logs\\\n\n"
            "不要从开发电脑复制 Chrome 登录 Profile。\n"
        ),
        encoding="utf-8",
    )


def create_zip() -> int:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    file_count = 0

    with ZipFile(
            ZIP_PATH,
            "w",
            compression=ZIP_DEFLATED,
    ) as archive:

        for file_path in sorted(
                STAGING_DIR.rglob("*")
        ):
            if not file_path.is_file():
                continue

            arcname = (
                file_path.relative_to(
                    STAGING_DIR.parent
                )
            )

            archive.write(
                file_path,
                arcname,
            )

            file_count += 1

    return file_count


def sha256_file(
        path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(
                1024 * 1024
        ):
            digest.update(chunk)

    return digest.hexdigest()


def write_checksum() -> str:
    checksum = sha256_file(
        ZIP_PATH
    )

    SHA256_PATH.write_text(
        (
            f"{checksum}  "
            f"{ZIP_PATH.name}\n"
        ),
        encoding="utf-8",
    )

    return checksum


def cleanup_staging() -> None:
    staging_parent = (
        STAGING_DIR.parent
    )

    if staging_parent.exists():
        shutil.rmtree(
            staging_parent
        )


def main() -> int:
    print(
        "=" * 80
    )
    print(
        "WENXIN SERVER PACKAGE BUILDER"
    )
    print(
        "=" * 80
    )
    print()

    try:
        validate_source()

        print(
            "[PASS] Source validation"
        )

        DIST_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        prepare_staging()
        copy_root_files()
        copy_project_directories()
        copy_scripts()
        create_runtime_placeholders()

        print(
            "[PASS] Deployment files prepared"
        )

        file_count = create_zip()

        print(
            "[PASS] ZIP created"
        )

        checksum = write_checksum()

        print(
            "[PASS] SHA-256 generated"
        )

        cleanup_staging()

    except Exception as exc:
        print()
        print(
            f"[FAIL] {exc}"
        )

        cleanup_staging()

        print()
        print(
            "SERVER PACKAGE: FAILED"
        )

        return 1

    size_mb = (
            ZIP_PATH.stat().st_size
            / 1024
            / 1024
    )

    print()
    print(
        "=" * 80
    )

    print(
        "SERVER PACKAGE: PASS"
    )

    print(
        "=" * 80
    )

    print(
        f"FILES: {file_count}"
    )

    print(
        f"SIZE: {size_mb:.2f} MB"
    )

    print(
        f"ZIP: {ZIP_PATH}"
    )

    print(
        f"SHA256 FILE: {SHA256_PATH}"
    )

    print(
        f"SHA256: {checksum}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
