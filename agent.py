"""LLM integration and dataframe context helpers."""
from __future__ import annotations

import os

import pandas as pd
from openai import OpenAI

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


def generate_code(question: str, df: pd.DataFrame, model: str) -> str:
    """Ask an OpenAI-compatible API to write a small dataframe analysis."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("未检测到 OPENAI_API_KEY。请在环境变量或 .env 中配置后重试。")

    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(question, dataframe_summary(df))},
        ],
    )
    code = response.choices[0].message.content or ""
    return code.removeprefix("```python").removeprefix("```").removesuffix("```").strip()
