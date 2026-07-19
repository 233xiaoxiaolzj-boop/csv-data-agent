"""External business-metric definitions supplied to the code-generation model."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

DEFAULT_METRICS_PATH = Path(__file__).parent / "config" / "metrics.json"


@lru_cache(maxsize=4)
def load_metric_catalog(path: str = str(DEFAULT_METRICS_PATH)) -> dict:
    """Load and minimally validate the version-controlled metric catalog."""
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    metrics = catalog.get("metrics")
    if not isinstance(metrics, list):
        raise ValueError("指标配置必须包含 metrics 列表。")
    required_keys = {"name", "label", "definition", "formula", "required_columns"}
    for metric in metrics:
        if not required_keys.issubset(metric):
            missing = sorted(required_keys - set(metric))
            raise ValueError(f"指标配置缺少字段：{', '.join(missing)}")
    return catalog


def build_metric_context(
    df: pd.DataFrame,
    question: str = "",
    path: str = str(DEFAULT_METRICS_PATH),
) -> str:
    """Return only relevant definitions supported by the current dataset."""
    catalog = load_metric_catalog(path)
    lines = []
    available_columns = set(df.columns)
    normalized_question = question.lower().replace(" ", "")
    for metric in catalog["metrics"]:
        terms = [metric["name"], metric["label"], *metric.get("aliases", [])]
        is_relevant = not question or any(
            term.lower().replace(" ", "") in normalized_question for term in terms
        )
        if is_relevant and set(metric["required_columns"]).issubset(available_columns):
            aliases = "、".join(metric.get("aliases", []))
            alias_text = f"（同义词：{aliases}）" if aliases else ""
            lines.append(
                f"- {metric['label']}{alias_text}：{metric['definition']}；参考公式：{metric['formula']}"
            )

    time_terms = (
        "日期",
        "时间",
        "年份",
        "年度",
        "月份",
        "月度",
        "季度",
        "按年",
        "按月",
        "按季",
        "year",
        "month",
        "quarter",
    )
    if "order_date" in available_columns and (
        not question or any(term in normalized_question for term in time_terms)
    ):
        lines.append(
            "- 时间维度：order_date 当前是字符串，使用 .dt 前必须先执行 "
            "pd.to_datetime(df['order_date'])；按月/季度默认保留年份，使用 YYYY-MM / YYYYQn；"
            "Period 用于画图前必须转成字符串。只在用户要求时间维度时使用日期字段。"
        )
    return "\n".join(lines) if lines else "- 本问题没有匹配到预定义指标，按字段原义计算。"
