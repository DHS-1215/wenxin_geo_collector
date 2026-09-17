from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

INPUT_DIR = (
        PROJECT_ROOT
        / "input"
)


@dataclass(
    frozen=True,
    slots=True,
)
class ProductConfig:
    """GEO 采集产品配置。"""

    product_id: str
    product_name: str
    csv_path: Path


PRODUCTS = {
    "hongmao": ProductConfig(
        product_id="hongmao_yaojiu",
        product_name="鸿茅药酒",
        csv_path=(
                INPUT_DIR
                / "hongmao_questions.csv"
        ),
    ),
    "tianyishou": ProductConfig(
        product_id="tianyishou_qixueguben",
        product_name="天益寿气血固本",
        csv_path=(
                INPUT_DIR
                / "tianyishou_questions.csv"
        ),
    ),
}


def get_product(
        key: str,
) -> ProductConfig:
    """根据产品简称获取配置。"""

    try:
        return PRODUCTS[key]
    except KeyError as exc:
        raise ValueError(
            f"未知产品: {key}"
        ) from exc
