import pandas as pd

from agent import GenerationTrace
from benchmark import (
    BenchmarkCase,
    _normalize_result,
    run_benchmark,
    run_security_benchmark,
    summarize,
)


def test_normalize_two_column_dataframe_as_mapping():
    result = pd.DataFrame({"month": ["2025-01", "2025-02"], "sales": [10.0, 20.0]})
    assert _normalize_result(result) == {"2025-01": 10.0, "2025-02": 20.0}


def test_normalize_timestamp_and_period():
    assert _normalize_result(pd.Timestamp("2025-01-02")) == "2025-01-02"
    assert _normalize_result(pd.Period("2025Q1")) == "2025Q1"


def test_run_benchmark_with_generation_trace():
    cases = (
        BenchmarkCase("sum", "基础统计", "求和", "result = int(df['value'].sum())"),
        BenchmarkCase(
            "chart",
            "可视化",
            "画图",
            "result = int(df['value'].sum())\nplt.figure()\nplt.plot(df['value'])",
            require_figure=True,
        ),
    )
    code_by_question = {case.question: case.reference_code for case in cases}

    def generator(question, df, model):
        return GenerationTrace(code_by_question[question], 1, False, False)

    results = run_benchmark(
        pd.DataFrame({"value": [1, 2, 3]}),
        "test-model",
        cases=cases,
        generator=generator,
    )

    assert all(result.passed for result in results)
    assert all(result.execution_success for result in results)


def test_summary_reports_repair_and_category_metrics():
    cases = (BenchmarkCase("sum", "基础统计", "求和", "result = int(df['value'].sum())"),)

    def generator(question, df, model):
        return GenerationTrace("result = int(df['value'].sum())", 2, True, False)

    results = run_benchmark(pd.DataFrame({"value": [1, 2]}), "test", cases, generator)
    security_results = run_security_benchmark()
    report = summarize(results, security_results)

    assert report["pass_rate"] == 1.0
    assert report["first_pass_rate"] == 0.0
    assert report["repair_success_rate"] == 1.0
    assert report["by_category"]["基础统计"]["passed"] == 1
    assert report["security_pass_rate"] == 1.0
