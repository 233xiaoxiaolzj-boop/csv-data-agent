"""Deterministic e-commerce KPI definitions and portfolio-ready business insights."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = {
    "order_date",
    "order_id",
    "region",
    "channel",
    "category",
    "units",
    "unit_price",
    "discount_rate",
    "returned",
}


@dataclass(frozen=True)
class BusinessOverview:
    """Business KPIs, dimension tables and plain-language observations."""

    kpis: dict[str, float | int]
    monthly: pd.DataFrame
    regions: pd.DataFrame
    channels: pd.DataFrame
    categories: pd.DataFrame
    insights: tuple[str, ...]


def supports_business_overview(df: pd.DataFrame) -> bool:
    """Return whether the uploaded data supports the demo business dashboard."""
    return REQUIRED_COLUMNS.issubset(df.columns)


def _dimension_summary(data: pd.DataFrame, dimension: str) -> pd.DataFrame:
    summary = (
        data.groupby(dimension, as_index=False)
        .agg(
            orders=("order_id", "nunique"),
            units=("units", "sum"),
            net_sales=("net_sales", "sum"),
            realized_sales=("realized_sales", "sum"),
            return_rate=("returned", "mean"),
        )
        .sort_values("realized_sales", ascending=False)
        .reset_index(drop=True)
    )
    return summary


def build_business_overview(df: pd.DataFrame) -> BusinessOverview:
    """Build auditable gross, discounted and return-adjusted sales metrics."""
    if not supports_business_overview(df):
        missing = sorted(REQUIRED_COLUMNS - set(df.columns))
        raise ValueError(f"经营看板缺少字段：{', '.join(missing)}")

    data = df.copy()
    data["order_date"] = pd.to_datetime(data["order_date"], errors="raise")
    for column in ("units", "unit_price", "discount_rate", "returned"):
        data[column] = pd.to_numeric(data[column], errors="raise")

    data["gross_sales"] = data["units"] * data["unit_price"]
    data["net_sales"] = data["gross_sales"] * (1 - data["discount_rate"])
    data["realized_sales"] = data["net_sales"] * (1 - data["returned"])
    data["month"] = data["order_date"].dt.to_period("M").astype(str)

    monthly = (
        data.groupby("month", as_index=False)
        .agg(
            orders=("order_id", "nunique"),
            gross_sales=("gross_sales", "sum"),
            net_sales=("net_sales", "sum"),
            realized_sales=("realized_sales", "sum"),
            return_rate=("returned", "mean"),
        )
        .sort_values("month")
        .reset_index(drop=True)
    )
    regions = _dimension_summary(data, "region")
    channels = _dimension_summary(data, "channel")
    categories = _dimension_summary(data, "category")

    gross_sales = float(data["gross_sales"].sum())
    net_sales = float(data["net_sales"].sum())
    realized_sales = float(data["realized_sales"].sum())
    return_rate = float(data["returned"].mean())
    kpis: dict[str, float | int] = {
        "orders": int(data["order_id"].nunique()),
        "units": int(data["units"].sum()),
        "gross_sales": gross_sales,
        "net_sales": net_sales,
        "realized_sales": realized_sales,
        "return_rate": return_rate,
        "average_order_value": realized_sales / data["order_id"].nunique(),
    }

    top_region = regions.iloc[0]
    top_category = categories.iloc[0]
    highest_return_channel = channels.sort_values("return_rate", ascending=False).iloc[0]
    peak_month = monthly.sort_values("realized_sales", ascending=False).iloc[0]
    loss_rate = 1 - realized_sales / gross_sales if gross_sales else 0.0
    insights = (
        f"{top_region['region']} 地区回款销售额最高，占整体的 "
        f"{top_region['realized_sales'] / realized_sales:.1%}。",
        f"{top_category['category']} 是回款销售额最高的品类。",
        f"{highest_return_channel['channel']} 渠道退货率最高，为 "
        f"{highest_return_channel['return_rate']:.1%}，应优先检查商品与履约原因。",
        f"{peak_month['month']} 是回款销售额峰值月份；折扣和退货合计造成 "
        f"{loss_rate:.1%} 的原价金额折损。",
    )
    return BusinessOverview(kpis, monthly, regions, channels, categories, insights)
