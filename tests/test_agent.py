import pandas as pd
import pytest

import agent


def test_extract_code_uses_last_fenced_block():
    content = "思考\n```python\nresult = 1\n```\n修正\n```python\nresult = 2\n```"
    assert agent._extract_code(content) == "result = 2"


@pytest.mark.parametrize(
    ("code", "require_plot", "expected"),
    [
        ("result = df['sales'].sum()", False, False),
        ("value = df['sales'].sum()", False, True),
        ("import os\nresult = 1", False, True),
        ("result = df['sales'].sum()", True, True),
        ("plt.plot(df['sales'])\nresult = df", True, False),
        ("fig, ax = plt.subplots()\nresult = fig", True, True),
        ("result = df['sales'].plot()", False, True),
    ],
)
def test_needs_rewrite(code, require_plot, expected):
    assert agent._needs_rewrite(code, require_plot) is expected


@pytest.mark.parametrize("term", ["柱状图", "直方图", "折线图", "散点图", "可视化"])
def test_requires_plot_recognizes_common_chart_terms(term):
    assert agent._requires_plot(f"请生成{term}") is True


def test_generate_code_repairs_invalid_first_response(monkeypatch):
    responses = iter(["value = df['sales'].sum()", "result = df['sales'].sum()"])
    monkeypatch.setattr(agent, "_call_ollama", lambda messages, model: next(responses))
    df = pd.DataFrame({"sales": [1, 2, 3]})

    assert agent.generate_code("总销售额是多少？", df, "test-model") == "result = df['sales'].sum()"


def test_generation_trace_exposes_repair(monkeypatch):
    responses = iter(["value = df['units'].sum()", "result = int(df['units'].sum())"])
    monkeypatch.setattr(agent, "_call_ollama", lambda messages, model: next(responses))

    trace = agent.generate_code_with_trace(
        "总销量是多少？", pd.DataFrame({"units": [1, 2]}), "test-model"
    )

    assert trace.attempts == 2
    assert trace.repaired is True
    assert trace.used_fallback is False


def test_generate_code_uses_trusted_sales_fallback(monkeypatch):
    monkeypatch.setattr(agent, "_call_ollama", lambda messages, model: "result = 0")
    df = pd.DataFrame(
        {
            "month": ["2025-01"],
            "units": [2],
            "unit_price": [5.0],
        }
    )

    code = agent.generate_code("按月统计销售额并画趋势图", df, "test-model")

    assert "df['sales'] = df['units'] * df['unit_price']" in code
    assert "summary = df.groupby('month'" in code
    assert "result = summary" in code


def test_sales_fallback_restores_requested_chart_after_repair(monkeypatch):
    responses = iter(
        [
            "result = 0",
            "df['sales'] = df['units'] * df['unit_price']\n"
            "result = df.groupby('month', as_index=False)['sales'].sum()",
        ]
    )
    monkeypatch.setattr(agent, "_call_ollama", lambda messages, model: next(responses))
    df = pd.DataFrame(
        {
            "month": ["2025-01", "2025-02"],
            "units": [2, 3],
            "unit_price": [5.0, 7.0],
        }
    )

    trace = agent.generate_code_with_trace("按月统计销售额并画趋势图", df, "test-model")

    assert trace.used_fallback is True
    assert "plt.plot" in trace.code
    assert "result = summary" in trace.code


def test_sales_fallback_uses_requested_dimension(monkeypatch):
    monkeypatch.setattr(agent, "_call_ollama", lambda messages, model: "result = 0")
    df = pd.DataFrame(
        {
            "region": ["South", "North"],
            "units": [2, 3],
            "unit_price": [5.0, 7.0],
        }
    )

    code = agent.generate_code("各地区销售额分别是多少？", df, "test-model")

    assert "groupby('region'" in code
    assert "result = summary" in code


def test_chart_fallback_handles_explicit_dimension_and_metric(monkeypatch):
    monkeypatch.setattr(agent, "_call_ollama", lambda messages, model: "result = 0")
    df = pd.DataFrame(
        {
            "region": ["South", "North"],
            "units": [2, 3],
        }
    )

    trace = agent.generate_code_with_trace(
        "按地区汇总销量并画柱状图，将汇总结果赋给 result。",
        df,
        "test-model",
    )

    assert trace.used_fallback is True
    assert "groupby('region')['units'].sum()" in trace.code
    assert "plt.bar" in trace.code
