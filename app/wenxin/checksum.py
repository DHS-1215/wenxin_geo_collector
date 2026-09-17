from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(
        path: str | Path,
) -> str:
    """计算文件 SHA-256。"""

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
) -> dict:
    """
    生成 GEO 标准 checksums.json 数据。

    checksums.json 本身不参与校验。
    """

    result: dict[str, str] = {}

    for file_path in files:
        path = Path(
            file_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"校验文件不存在: {path}"
            )

        result[path.name] = (
            sha256_file(path)
        )

    return {
        "files": result
    }
