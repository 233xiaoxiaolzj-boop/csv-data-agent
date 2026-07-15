"""LLM integration and dataframe context helpers."""
from __future__ import annotations

import re

import pandas as pd
import requests

from prompts import SYSTEM_PROMPT, build_user_prompt


def dataframe_summary(df: pd.DataFrame) -> str:
    """Create a compact, privacy-conscious context for the model."""
    schema = "\n".join(f"- {name}: {dtype}" for name, dtype in df.dtypes.items())
    missing = df.isna().sum()
    missing_text = ", ".join(f"{name}={count}" for name, count in missing.items() if count)
    preview = df.head(5).to_csv(index=False)
    return (
        f"行数: {len(df)}，列数: {len(df.columns)}\n"
        f"字段和类型:\n{schema}\n"
        f"缺失值: {missing_text or '无'}\n"
        f"前 5 行（CSV）:\n{preview}"
    )


def _call_ollama(messages: list[dict[str, str]], model: str) -> str:
    """Send one non-streaming chat request to a locally-running Ollama model."""
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": model,
                "stream": False,
                "options": {"temperature": 0},
                "messages": messages,
            },
            timeout=120,
        )
        response.raise_for_status()
    except requests.ConnectionError as error:
        raise RuntimeError(
            "未检测到 Ollama。本项目使用免费的本地模型；请先安装 Ollama 并运行 `ollama run qwen2.5-coder:7b`。"
        ) from error
    except requests.RequestException as error:
        raise RuntimeError(f"Ollama 请求失败：{error}") from error
    return response.json().get("message", {}).get("content", "")


def _extract_code(content: str) -> str:
    """Use the last fenced Python block when a reasoning model adds prose."""
    blocks = re.findall(r"```(?:python)?\s*\n?(.*?)```", content, flags=re.DOTALL | re.IGNORECASE)
    return (blocks[-1] if blocks else content).strip()


def _needs_rewrite(code: str, require_plot: bool) -> bool:
    unsafe_sales_formula = re.search(
        r"groupby\(.*?\)\s*\[.*?\]\s*\.sum\(\).*?\*.*?groupby\(.*?\).*?\.mean\(\)",
        code,
        flags=re.DOTALL,
    )


def _requires_sales_guard(question: str, df: pd.DataFrame) -> bool:
    """Identify the explicit row-level sales calculation used by the demo dataset."""
    normalized = question.lower().replace(" ", "")
    return (
        {"month", "units", "unit_price"}.issubset(df.columns)
        and ("units×unit_price" in normalized or "units*unit_price" in normalized)
    )


def _valid_sales_plan(code: str) -> bool:
    normalized = re.sub(r"\s+", "", code)
    row_formula = bool(re.search(r"df\[['\"]sales['\"]\]=df\[['\"]units['\"]\]\*df\[['\"]unit_price['\"]\]", normalized))
    monthly_sum = bool(re.search(r"groupby\(['\"]month['\"]\).*?\[['\"]sales['\"]\]\.sum\(\)", normalized))
    return row_formula and monthly_sum and "import " not in code


def _trusted_sales_template() -> str:
    """A deterministic guardrail for an explicitly requested revenue formula."""
    return '''df['sales'] = df['units'] * df['unit_price']
monthly_sales = df.groupby('month', as_index=False)['sales'].sum()

plt.figure(figsize=(10, 6))
plt.plot(monthly_sales['month'], monthly_sales['sales'], marker='o')
plt.title('Monthly Sales Trend')
plt.xlabel('Month')
plt.ylabel('Total Sales')
plt.grid(True)

result = monthly_sales'''
    return (
        "import " in code
        or not re.search(r"\bresult\s*=", code)
        or bool(unsafe_sales_formula)
        or (require_plot and "plt." not in code)
    )


def generate_code(question: str, df: pd.DataFrame, model: str) -> str:
    """Generate safe analysis code, with one repair pass for local reasoning models."""
    code = _extract_code(_call_ollama([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(question, dataframe_summary(df))},
    ], model))

    require_plot = any(word in question.lower() for word in ("画图", "图表", "趋势图", "plot", "chart"))
    requires_sales_guard = _requires_sales_guard(question, df)
    if _needs_rewrite(code, require_plot) or (requires_sales_guard and not _valid_sales_plan(code)):
        repair_prompt = f'''下面的候选代码不符合执行环境要求。请重写它。

硬性要求：不能有 import；pd、np、plt、df 已经可用；最后必须有一行将答案赋给 result；只输出 Python 代码，不要 Markdown。

计算销售额等逐行公式时，必须先创建如 `df['sales'] = df['units'] * df['unit_price']` 的派生列，然后按月对 `sales` 求和。绝不能把数量总和乘以平均单价。

用户问题要求图表时，必须使用 plt 创建图表。

候选代码：
{code}'''
        code = _extract_code(_call_ollama([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": repair_prompt},
        ], model))
    if requires_sales_guard and not _valid_sales_plan(code):
        code = _trusted_sales_template()
    return code
