from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(
    path: str | Path,
) -> str:
    """Calculate SHA-256 for one file."""

    path = Path(path)

    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def generate_checksums(
    files: list[str | Path],
    *,
    base_dir: str | Path | None = None,
) -> dict:
    """
    Build checksums.json data.

    If base_dir is supplied, checksum keys are
    package-relative POSIX paths such as:
    screenshots/wx_t_xxx.png
    """

    result: dict[str, str] = {}

    base = (
        Path(base_dir).resolve()
        if base_dir is not None
        else None
    )

    for file_path in files:
        path = Path(
            file_path
        )

        if not path.is_file():
            raise FileNotFoundError(
                f"Checksum file not found: {path}"
            )

        if base is None:
            key = path.name
        else:
            try:
                key = (
                    path.resolve()
                    .relative_to(base)
                    .as_posix()
                )
            except ValueError as exc:
                raise ValueError(
                    "Checksum file is outside package: "
                    f"{path}"
                ) from exc

        if key in result:
            raise ValueError(
                f"Duplicate checksum path: {key}"
            )

        result[key] = sha256_file(
            path
        )

    return {
        "files": result
    }
