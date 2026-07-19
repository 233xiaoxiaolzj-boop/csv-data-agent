import pandas as pd
import pytest

from data_profile import build_data_profile


def test_build_data_profile_reports_quality_and_distributions():
    df = pd.DataFrame(
        {
            "city": ["深圳", "深圳", None, "深圳"],
            "sales": [10.0, 20.0, None, 10.0],
        }
    )

    profile = build_data_profile(df)

    assert profile.overview["rows"] == 4
    assert profile.overview["columns"] == 2
    assert profile.overview["missing_cells"] == 2
    assert profile.overview["missing_rate"] == 25.0
    assert profile.overview["duplicate_rows"] == 1
    assert profile.columns.set_index("字段").loc["sales", "缺失数"] == 1
    assert profile.numeric.set_index("字段").loc["sales", "平均值"] == pytest.approx(13.3333)
    assert profile.categorical.set_index("字段").loc["city", "最高频值"] == "深圳"
