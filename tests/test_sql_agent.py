import pandas as pd
import pytest

from sql_agent import execute_sql, should_use_python, validate_readonly_sql


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("各地区的销售额是多少？", False),
        ("按月份画销售额趋势图", True),
        ("计算物流时效与退货的相关系数", True),
    ],
)
def test_analysis_router(question, expected):
    assert should_use_python(question) is expected


def test_readonly_sql_validation_and_execution():
    pytest.importorskip("duckdb")
    pytest.importorskip("sqlglot")
    df = pd.DataFrame({"region": ["A", "A", "B"], "units": [1, 2, 4]})

    output = execute_sql(
        "SELECT region, SUM(units) AS total_units FROM source_data GROUP BY region",
        df,
    )

    assert output.result.set_index("region")["total_units"].to_dict() == {"A": 3.0, "B": 4.0}
    assert "LIMIT 200" in output.sql


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE source_data",
        "SELECT * FROM other_table",
        "SELECT * FROM read_csv_auto('secret.csv')",
        "SELECT 1; SELECT 2",
    ],
)
def test_sql_security_policy(sql):
    pytest.importorskip("sqlglot")
    with pytest.raises(ValueError):
        validate_readonly_sql(sql)
