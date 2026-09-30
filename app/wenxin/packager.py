from __future__ import annotations

from pathlib import Path
from zipfile import (
    ZIP_DEFLATED,
    ZipFile,
)

from app.wenxin.verifier import (
    verify_package_directory,
    verify_package_zip,
)


def create_package(
    package_dir: str | Path,
    output_zip: str | Path,
) -> Path:
    """
    Package a verified GEO directory into ZIP.
    All package files, including screenshots/,
    are stored with package-relative paths.
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

    package_files = sorted(
        (
            path
            for path in package_dir.rglob(
                "*"
            )
            if path.is_file()
        ),
        key=lambda path: (
            path.relative_to(
                package_dir
            ).as_posix()
        ),
    )

    with ZipFile(
        output_zip,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as archive:
        for file_path in package_files:
            arcname = (
                file_path
                .relative_to(
                    package_dir
                )
                .as_posix()
            )

            archive.write(
                file_path,
                arcname=arcname,
            )

    verify_package_zip(
        output_zip
    )

    return output_zip
