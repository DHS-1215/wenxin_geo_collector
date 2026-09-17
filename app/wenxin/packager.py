from __future__ import annotations

from pathlib import Path
from zipfile import (
    ZIP_DEFLATED,
    ZipFile,
)

from app.wenxin.verifier import (
    PACKAGE_FILES,
    verify_package_directory,
    verify_package_zip,
)


def create_package(
        package_dir: str | Path,
        output_zip: str | Path,
) -> Path:
    """
    将已经导出的 GEO 标准目录
    打包为 ZIP，并在打包前后各验证一次。
    """

    package_dir = Path(
        package_dir
    )

    output_zip = Path(
        output_zip
    )

    verify_package_directory(
        package_dir
    )

    output_zip.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if output_zip.exists():
        output_zip.unlink()

    with ZipFile(
            output_zip,
            mode="w",
            compression=ZIP_DEFLATED,
    ) as archive:
        for file_name in sorted(
                PACKAGE_FILES
        ):
            file_path = (
                    package_dir
                    / file_name
            )

            archive.write(
                file_path,
                arcname=file_name,
            )

    verify_package_zip(
        output_zip
    )

    return output_zip
