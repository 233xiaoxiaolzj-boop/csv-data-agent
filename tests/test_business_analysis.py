import pandas as pd
import pytest

from business_analysis import build_business_overview, supports_business_overview


@pytest.fixture
def sales_data():
    return pd.DataFrame(
        {
            "order_date": ["2025-01-01", "2025-02-01"],
            "order_id": ["A", "B"],
            "region": ["South", "North"],
            "channel": ["Direct", "Marketplace"],
            "category": ["Home", "Sports"],
            "units": [2, 3],
            "unit_price": [100.0, 50.0],
            "discount_rate": [0.1, 0.0],
            "returned": [0, 1],
        }
    )


def test_business_overview_distinguishes_sales_definitions(sales_data):
    overview = build_business_overview(sales_data)

    assert overview.kpis["gross_sales"] == pytest.approx(350.0)
    assert overview.kpis["net_sales"] == pytest.approx(330.0)
    assert overview.kpis["realized_sales"] == pytest.approx(180.0)
    assert overview.kpis["return_rate"] == pytest.approx(0.5)
    assert list(overview.monthly["month"]) == ["2025-01", "2025-02"]


def test_business_overview_returns_dimension_insights(sales_data):
    overview = build_business_overview(sales_data)

    assert overview.regions.iloc[0]["region"] == "South"
    assert (
        overview.channels.sort_values("return_rate", ascending=False).iloc[0]["channel"]
        == "Marketplace"
    )
    assert len(overview.insights) == 4


def test_business_overview_requires_expected_schema():
    frame = pd.DataFrame({"units": [1]})

    assert supports_business_overview(frame) is False
    with pytest.raises(ValueError, match="经营看板缺少字段"):
        build_business_overview(frame)
