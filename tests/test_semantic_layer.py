import pandas as pd

from semantic_layer import build_metric_context, load_metric_catalog


def test_metric_catalog_contains_portfolio_metrics():
    names = {metric["name"] for metric in load_metric_catalog()["metrics"]}
    assert {
        "units_sold",
        "gross_sales_amount",
        "net_sales_amount",
        "realized_sales_amount",
        "return_rate",
    }.issubset(names)


def test_context_only_includes_metrics_supported_by_columns():
    context = build_metric_context(
        pd.DataFrame({"units": [1], "returned": [0]}),
        "总销量和退货率是多少？",
    )

    assert "销量" in context
    assert "退货率" in context
    assert "原价销售额" not in context


def test_time_context_requires_order_date():
    without_date = build_metric_context(pd.DataFrame({"units": [1]}), "按月统计销量")
    with_date = build_metric_context(
        pd.DataFrame({"units": [1], "order_date": ["2025-01-01"]}),
        "按月统计销量",
    )

    assert "YYYY-MM" not in without_date
    assert "YYYY-MM" in with_date


def test_irrelevant_metrics_are_not_sent_to_model():
    context = build_metric_context(
        pd.DataFrame({"units": [1], "unit_price": [2.0], "returned": [0]}),
        "按地区汇总销量",
    )

    assert "销量" in context
    assert "原价销售额" not in context
    assert "退货率" not in context


def test_generic_sales_question_uses_explicit_gross_definition():
    context = build_metric_context(
        pd.DataFrame(
            {
                "units": [1],
                "unit_price": [2.0],
                "discount_rate": [0.1],
                "returned": [0],
            }
        ),
        "总销售额是多少？",
    )

    assert "原价销售额" in context
    assert "未扣除折扣与退货" in context
    assert "折后销售额" not in context
