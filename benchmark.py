"""Reproducible multi-dimensional benchmark for the local CSV agent."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Callable, Sequence

import numpy as np
import pandas as pd

from agent import GenerationTrace, generate_code_with_trace
from benchmark_cases import (
    ANALYSIS_CASES,
    QUICK_CASES,
    SECURITY_CASES,
    BenchmarkCase,
    SecurityCase,
)
from executor import execute_code, validate_code


@dataclass(frozen=True)
class BenchmarkResult:
    name: str
    category: str
    question: str
    passed: bool
    execution_success: bool
    answer_correct: bool
    figure_correct: bool
    latency_seconds: float
    attempts: int = 0
    repaired: bool = False
    used_fallback: bool = False
    generated_code: str = ""
    error: str = ""


@dataclass(frozen=True)
class SecurityResult:
    name: str
    passed: bool
    expected_rejection: bool
    actually_rejected: bool
    error: str = ""


def _normalize_result(value):
    """Convert common pandas outputs into comparable Python structures."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return str(value.date()) if value == value.normalize() else value.isoformat()
    if isinstance(value, pd.Period):
        return str(value)
    if isinstance(value, pd.Series):
        return {str(key): _normalize_result(item) for key, item in value.to_dict().items()}
    if isinstance(value, pd.DataFrame):
        if value.shape[1] == 2:
            key_column, value_column = value.columns
            return {
                str(key): _normalize_result(item)
                for key, item in zip(value[key_column], value[value_column], strict=True)
            }
        return [
            {str(key): _normalize_result(item) for key, item in row.items()}
            for row in value.to_dict(orient="records")
        ]
    return value


def _results_equal(actual, expected) -> bool:
    """Recursively compare tables and scalars with numeric tolerance."""
    actual = _normalize_result(actual)
    expected = _normalize_result(expected)
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return bool(np.isclose(actual, expected, rtol=1e-5, atol=1e-6, equal_nan=True))
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _results_equal(actual[key], expected[key]) for key in actual
        )
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _results_equal(left, right) for left, right in zip(actual, expected, strict=True)
        )
    return actual == expected


def _unwrap_generation(value: str | GenerationTrace) -> GenerationTrace:
    if isinstance(value, GenerationTrace):
        return value
    return GenerationTrace(code=value, attempts=1, repaired=False, used_fallback=False)


def run_benchmark(
    df: pd.DataFrame,
    model: str,
    cases: Sequence[BenchmarkCase] = ANALYSIS_CASES,
    generator: Callable[[str, pd.DataFrame, str], str | GenerationTrace] = generate_code_with_trace,
) -> list[BenchmarkResult]:
    """Generate, execute and compare answers with deterministic reference code."""
    results = []
    for case in cases:
        started_at = perf_counter()
        trace = GenerationTrace("", 0, False, False)
        execution_success = False
        try:
            expected = execute_code(case.reference_code, df)
            trace = _unwrap_generation(generator(case.question, df, model))
            actual = execute_code(trace.code, df)
            execution_success = True
            answer_correct = _results_equal(actual.result, expected.result)
            figure_correct = not case.require_figure or actual.figure is not None
            results.append(
                BenchmarkResult(
                    name=case.name,
                    category=case.category,
                    question=case.question,
                    passed=answer_correct and figure_correct,
                    execution_success=True,
                    answer_correct=answer_correct,
                    figure_correct=figure_correct,
                    latency_seconds=round(perf_counter() - started_at, 3),
                    attempts=trace.attempts,
                    repaired=trace.repaired,
                    used_fallback=trace.used_fallback,
                    generated_code=trace.code,
                )
            )
        except Exception as error:  # report all cases instead of stopping on the first failure
            results.append(
                BenchmarkResult(
                    name=case.name,
                    category=case.category,
                    question=case.question,
                    passed=False,
                    execution_success=execution_success,
                    answer_correct=False,
                    figure_correct=False,
                    latency_seconds=round(perf_counter() - started_at, 3),
                    attempts=trace.attempts,
                    repaired=trace.repaired,
                    used_fallback=trace.used_fallback,
                    generated_code=trace.code,
                    error=str(error),
                )
            )
    return results


def run_security_benchmark(cases: Sequence[SecurityCase] = SECURITY_CASES) -> list[SecurityResult]:
    """Verify that the AST policy blocks adversarial snippets and permits valid code."""
    results = []
    for case in cases:
        rejected = False
        error_text = ""
        try:
            validate_code(case.code)
        except ValueError as error:
            rejected = True
            error_text = str(error)
        results.append(
            SecurityResult(
                name=case.name,
                passed=rejected == case.should_reject,
                expected_rejection=case.should_reject,
                actually_rejected=rejected,
                error=error_text,
            )
        )
    return results


def summarize(
    results: Sequence[BenchmarkResult],
    security_results: Sequence[SecurityResult] = (),
) -> dict:
    """Build portfolio-friendly metrics without hiding failed cases."""
    total = len(results)
    latencies = [item.latency_seconds for item in results]
    repaired = [item for item in results if item.repaired]
    categories = sorted({item.category for item in results})
    by_category = {
        category: {
            "passed": sum(item.passed for item in results if item.category == category),
            "total": sum(item.category == category for item in results),
        }
        for category in categories
    }
    for value in by_category.values():
        value["pass_rate"] = round(value["passed"] / value["total"], 4)

    return {
        "analysis_cases": total,
        "passed": sum(item.passed for item in results),
        "pass_rate": round(sum(item.passed for item in results) / total, 4) if total else 0.0,
        "execution_success_rate": round(sum(item.execution_success for item in results) / total, 4)
        if total
        else 0.0,
        "answer_accuracy": round(sum(item.answer_correct for item in results) / total, 4)
        if total
        else 0.0,
        "first_pass_rate": round(
            sum(item.attempts == 1 and item.passed for item in results) / total, 4
        )
        if total
        else 0.0,
        "repair_trigger_rate": round(len(repaired) / total, 4) if total else 0.0,
        "repair_success_rate": round(sum(item.passed for item in repaired) / len(repaired), 4)
        if repaired
        else 0.0,
        "fallback_rate": round(sum(item.used_fallback for item in results) / total, 4)
        if total
        else 0.0,
        "average_latency_seconds": round(float(np.mean(latencies)), 3) if latencies else 0.0,
        "p95_latency_seconds": round(float(np.percentile(latencies, 95)), 3) if latencies else 0.0,
        "security_cases": len(security_results),
        "security_pass_rate": round(
            sum(item.passed for item in security_results) / len(security_results), 4
        )
        if security_results
        else 0.0,
        "by_category": by_category,
    }


def render_markdown(model: str, csv_path: str, summary: dict, results, security_results) -> str:
    lines = [
        f"# CSV Data Agent 评测报告：{model}",
        "",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 数据集：`{csv_path}`",
        f"- 分析任务：{summary['passed']}/{summary['analysis_cases']}（{summary['pass_rate']:.1%}）",
        f"- 执行成功率：{summary['execution_success_rate']:.1%}",
        f"- 首轮通过率：{summary['first_pass_rate']:.1%}",
        f"- 安全规则测试：{sum(item.passed for item in security_results)}/{len(security_results)}（{summary['security_pass_rate']:.1%}）",
        f"- 平均 / P95 延迟：{summary['average_latency_seconds']:.3f}s / {summary['p95_latency_seconds']:.3f}s",
        "",
        "## 分类结果",
        "",
        "| 类别 | 通过 | 总数 | 通过率 |",
        "|---|---:|---:|---:|",
    ]
    for category, item in summary["by_category"].items():
        lines.append(
            f"| {category} | {item['passed']} | {item['total']} | {item['pass_rate']:.1%} |"
        )
    lines.extend(
        [
            "",
            "## 逐题结果",
            "",
            "| 任务 | 类别 | 结果 | 尝试 | 修复 | 回退 | 延迟 |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for item in results:
        lines.append(
            f"| {item.name} | {item.category} | {'通过' if item.passed else '失败'} | "
            f"{item.attempts} | {'是' if item.repaired else '否'} | "
            f"{'是' if item.used_fallback else '否'} | {item.latency_seconds:.3f}s |"
        )
    failures = [item for item in results if not item.passed]
    if failures:
        lines.extend(["", "## 失败明细", ""])
        for item in failures:
            reason = item.error or "代码可执行，但结果与参考答案不一致"
            lines.append(f"- `{item.name}`：{reason}")
    lines.extend(
        [
            "",
            "## 口径说明",
            "",
            "参考答案由确定性 pandas 代码生成；标量、Series 和 DataFrame 会归一化后递归比较，数值使用容差比较。图表题除答案正确外，还必须生成 Matplotlib Figure。安全测试验证 AST 规则是否按预期拒绝文件、网络、导入、动态执行和循环等代码。",
            "",
            "> 该结果只代表仓库内固定数据集与固定问题，不等同于通用数据分析准确率。JSON 报告保留逐题问题、生成代码、错误和审计字段，便于复核。",
        ]
    )
    return "\n".join(lines) + "\n"


def save_report(
    output_dir: Path, model: str, csv_path: str, results, security_results
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(results, security_results)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_model = model.replace(":", "-").replace("/", "-")
    stem = f"{timestamp}-{safe_model}"
    payload = {
        "model": model,
        "dataset": csv_path,
        "summary": summary,
        "results": [asdict(item) for item in results],
        "security_results": [asdict(item) for item in security_results],
    }
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(
        render_markdown(model, csv_path, summary, results, security_results),
        encoding="utf-8",
    )
    return markdown_path, json_path


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 CSV Agent 分层黄金问题评测")
    parser.add_argument("--csv", default="sample_data/ecommerce_sales.csv", help="评测 CSV 路径")
    parser.add_argument("--model", default="qwen2.5-coder:7b", help="Ollama 模型名称")
    parser.add_argument("--suite", choices=("quick", "full"), default="full", help="评测规模")
    parser.add_argument("--output-dir", default="benchmark_results", help="报告输出目录")
    args = parser.parse_args()

    df = pd.read_csv(Path(args.csv))
    cases = QUICK_CASES if args.suite == "quick" else ANALYSIS_CASES
    results = []
    for index, case in enumerate(cases, start=1):
        result = run_benchmark(df, args.model, cases=(case,))[0]
        results.append(result)
        detail = f" | {result.error}" if result.error else ""
        print(
            f"[{index:02}/{len(cases):02}] "
            f"{'PASS' if result.passed else 'FAIL':4} {result.category:8} "
            f"{result.name:24} {result.latency_seconds:7.3f}s{detail}",
            flush=True,
        )
    security_results = run_security_benchmark()
    summary = summarize(results, security_results)
    print(
        f"\n分析通过率：{summary['passed']}/{summary['analysis_cases']} ({summary['pass_rate']:.1%})"
        f" | 首轮：{summary['first_pass_rate']:.1%}"
        f" | 安全：{summary['security_pass_rate']:.1%}"
        f" | P95：{summary['p95_latency_seconds']:.3f}s"
    )
    markdown_path, json_path = save_report(
        Path(args.output_dir), args.model, args.csv, results, security_results
    )
    print(f"报告：{markdown_path} | {json_path}")
    return 0 if summary["pass_rate"] == 1.0 and summary["security_pass_rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
