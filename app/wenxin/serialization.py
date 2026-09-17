from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def write_json(
        path: str | Path,
        data: Any,
) -> None:
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def write_jsonl(
        path: str | Path,
        rows: Iterable[dict],
) -> None:
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
            "w",
            encoding="utf-8",
            newline="\n",
    ) as file:
        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
            )

            file.write("\n")
