"""LLM integration, dataframe context and generation audit helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import pandas as pd
import requests

from executor import validate_code
from prompts import SYSTEM_PROMPT, build_user_prompt
from semantic_layer import build_metric_context


@dataclass(frozen=True)
class GenerationTrace:
    """Generated code plus audit information used by benchmarks and the UI."""

    code: str
    attempts: int
    repaired: bool
    used_fallback: bool


def dataframe_summary(df: pd.DataFrame) -> str:
    """Create a compact, privacy-conscious context for the model."""
    schema = "\n".join(f"- {name}: {dtype}" for name, dtype in df.dtypes.items())
    missing = df.isna().sum()
    missing_text = ", ".join(f"{name}={count}" for name, count in missing.items() if count)
    preview = df.head(5).to_csv(index=False)
    return (
        f"行数：{len(df)}，列数：{len(df.columns)}\n"
        f"字段和类型：\n{schema}\n"
        f"缺失值：{missing_text or '无'}\n"
        f"前 5 行（CSV）：\n{preview}"
    )


def _call_ollama(messages: list[dict[str, str]], model: str) -> str:
    """Send one non-streaming chat request to a locally-running Ollama model."""
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "seed": 42,
                    "num_ctx": 4096,
                    "num_predict": 512,
                },
                "messages": messages,
            },
            timeout=(5, 90),
        )
        response.raise_for_status()
    except requests.ConnectionError as error:
        raise RuntimeError(
            "未检测到 Ollama。本项目使用免费的本地模型；请先启动 Ollama，"
            "并运行 `ollama run qwen2.5-coder:7b`。"
        ) from error
    except requests.RequestException as error:
        raise RuntimeError(f"Ollama 请求失败：{error}") from error
    return response.json().get("message", {}).get("content", "")


def _extract_code(content: str) -> str:
    """Use the last fenced Python block when a reasoning model adds prose."""
    blocks = re.findall(r"```(?:python)?\s*\n?(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
    return (blocks[-1] if blocks else content).strip()


def _needs_rewrite(code: str, require_plot: bool) -> bool:
    """Return whether generated code violates the execution contract."""
    if not code.strip():
        return True
    unsafe_sales_formula = re.search(
        r"groupby\(.*?\)\s*\[.*?\]\s*\.sum\(\).*?\*.*?groupby\(.*?\).*?\.mean\(\)",
        code,
        flags=re.DOTALL,
    )
    invalid_result_type = re.search(
        r"\bresult\s*=\s*(?:fig|ax)\b|\bresult\s*=.*?\.plot\(",
        code,
        flags=re.DOTALL,
    )
    try:
        validate_code(code)
    except ValueError:
        return True
    return (
        not re.search(r"\bresult\s*=", code)
        or bool(unsafe_sales_formula)
        or bool(invalid_result_type)
        or (require_plot and "plt." not in code)
    )


def _requires_plot(question: str) -> bool:
    normalized = question.lower().replace(" ", "")
    return any(
        term in normalized
        for term in (
            "画图",
            "图表",
            "趋势图",
            "柱状图",
            "条形图",
            "直方图",
            "折线图",
            "散点图",
            "可视化",
            "plot",
            "chart",
            "histogram",
        )
    )


def _requires_sales_guard(question: str, df: pd.DataFrame) -> bool:
    """Identify the explicit row-level sales calculation used by the demo dataset."""
    normalized = question.lower().replace(" ", "")
    sales_terms = ("销售额", "营收", "成交额", "revenue", "sales")
    return {"units", "unit_price"}.issubset(df.columns) and (
        "units×unit_price" in normalized
        or "units*unit_price" in normalized
        or any(term in normalized for term in sales_terms)
    )


def _valid_sales_plan(code: str) -> bool:
    normalized = re.sub(r"\s+", "", code)
    row_formula = bool(
        re.search(
            r"df\[['\"]sales['\"]\]=df\[['\"]units['\"]\]\*df\[['\"]unit_price['\"]\]",
            normalized,
        )
    )
    sales_sum = bool(re.search(r"\[['\"]sales['\"]\]\.sum\(\)", normalized))
    return row_formula and sales_sum and "import " not in code


def _trusted_sales_template(df: pd.DataFrame, question: str) -> str:
    """Return deterministic code for the explicitly defined demo revenue metric."""
    normalized = question.lower().replace(" ", "")
    group_candidates = (
        ("region", ("region", "地区", "区域")),
        ("channel", ("channel", "渠道")),
        ("category", ("category", "品类", "类别")),
        ("product", ("product", "产品", "商品")),
    )
    group_column = next(
        (
            column
            for column, terms in group_candidates
            if column in df.columns and any(term in normalized for term in terms)
        ),
        None,
    )
    asks_for_month = any(term in normalized for term in ("month", "月份", "月度", "趋势"))
    asks_for_chart = _requires_plot(question)

    if asks_for_month and "month" in df.columns:
        grouping_code = "summary = df.groupby('month', as_index=False)['sales'].sum()"
        x_column = "month"
    elif asks_for_month and "order_date" in df.columns:
        grouping_code = (
            "df['month'] = pd.to_datetime(df['order_date']).dt.to_period('M').astype(str)\n"
            "summary = df.groupby('month', as_index=False)['sales'].sum()"
        )
        x_column = "month"
    elif group_column:
        grouping_code = f"summary = df.groupby('{group_column}', as_index=False)['sales'].sum()"
        x_column = group_column
    else:
        return "df['sales'] = df['units'] * df['unit_price']\nresult = float(df['sales'].sum())"

    chart_code = ""
    if asks_for_chart:
        chart_code = f"""
plt.figure(figsize=(10, 6))
plt.plot(summary['{x_column}'], summary['sales'], marker='o')
plt.title('Sales Analysis')
plt.xlabel('{x_column}')
plt.ylabel('Total Sales')
plt.xticks(rotation=30)
"""
    return f"""df['sales'] = df['units'] * df['unit_price']
{grouping_code}
{chart_code}
result = summary"""


def _trusted_chart_template(df: pd.DataFrame, question: str) -> str | None:
    """Return deterministic code for explicit dimension-metric chart requests."""
    normalized = question.lower().replace(" ", "")
    dimension_candidates = (
        ("region", ("region", "地区", "区域")),
        ("channel", ("channel", "渠道")),
        ("category", ("category", "品类", "类别")),
        ("product", ("product", "产品", "商品")),
    )
    metric_candidates = (
        ("units", ("units", "销量", "销售量", "件数"), "sum"),
        ("returned", ("returned", "退货订单数", "退货数"), "sum"),
        ("shipping_days", ("shipping_days", "物流时效", "物流天数"), "mean"),
        ("unit_price", ("unit_price", "平均单价", "单价"), "mean"),
    )
    dimension = next(
        (
            column
            for column, terms in dimension_candidates
            if column in df.columns and any(term in normalized for term in terms)
        ),
        None,
    )
    metric = next(
        (
            (column, aggregation)
            for column, terms, aggregation in metric_candidates
            if column in df.columns and any(term in normalized for term in terms)
        ),
        None,
    )
    if not dimension or not metric:
        return None

    metric_column, aggregation = metric
    chart_method = (
        "bar" if any(term in normalized for term in ("柱状图", "条形图", "bar")) else "plot"
    )
    chart_call = (
        "plt.bar(result.index.astype(str), result.values)"
        if chart_method == "bar"
        else "plt.plot(result.index.astype(str), result.values, marker='o')"
    )
    return f"""result = df.groupby('{dimension}')['{metric_column}'].{aggregation}()
plt.figure(figsize=(10, 6))
{chart_call}
plt.title('{metric_column} by {dimension}')
plt.xlabel('{dimension}')
plt.ylabel('{metric_column}')
plt.xticks(rotation=30)"""


def generate_code_with_trace(question: str, df: pd.DataFrame, model: str) -> GenerationTrace:
    """Generate safe analysis code and retain repair/fallback audit information."""
    code = _extract_code(
        _call_ollama(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        question,
                        dataframe_summary(df),
                        build_metric_context(df, question),
                    ),
                },
            ],
            model,
        )
    )
    attempts = 1
    repaired = False
    used_fallback = False
    require_plot = _requires_plot(question)
    requires_sales_guard = _requires_sales_guard(question, df)

    if _needs_rewrite(code, require_plot) or (requires_sales_guard and not _valid_sales_plan(code)):
        repaired = True
        attempts = 2
        sales_rule = ""
        if requires_sales_guard:
            sales_rule = """
计算销售额等逐行公式时，必须先创建如 `df['sales'] = df['units'] * df['unit_price']` 的派生列，再按用户要求的维度对 `sales` 聚合。绝不能把数量总和乘以平均单价。
"""
        repair_prompt = f"""下面的候选代码不符合执行环境要求，请根据原问题重写。

原问题：{question}
相关业务口径：
{build_metric_context(df, question)}

硬性要求：不能有 import；pd、np、plt、df 已经可用；最后必须将表格或标量答案赋给 result，不能把 Figure、Axes 或 Plot 对象赋给 result；只输出 Python 代码，不要 Markdown。
{sales_rule}
用户问题要求图表时，必须使用 plt 创建图表。
只创建 Figure，不要调用 plt.show()、plt.pause() 或保存文件。

候选代码：
{code}"""
        code = _extract_code(
            _call_ollama(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": repair_prompt},
                ],
                model,
            )
        )

    if requires_sales_guard and (not _valid_sales_plan(code) or _needs_rewrite(code, require_plot)):
        code = _trusted_sales_template(df, question)
        used_fallback = True
    if _needs_rewrite(code, require_plot) and require_plot:
        trusted_chart = _trusted_chart_template(df, question)
        if trusted_chart is not None:
            code = trusted_chart
            used_fallback = True
    if _needs_rewrite(code, require_plot):
        raise RuntimeError("模型生成的分析代码在自动修复后仍未通过安全与格式校验，请换一种问法。")

    return GenerationTrace(
        code=code,
        attempts=attempts,
        repaired=repaired,
        used_fallback=used_fallback,
    )


def generate_code(question: str, df: pd.DataFrame, model: str) -> str:
    """Backward-compatible code-only API used by the Streamlit app."""
    return generate_code_with_trace(question, df, model).code
