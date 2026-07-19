"""Deterministic dataset profiling used before any LLM analysis."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DataProfile:
    overview: dict[str, int | float]
    columns: pd.DataFrame
    numeric: pd.DataFrame
    categorical: pd.DataFrame


def _safe_top_value(series: pd.Series) -> tuple[object, int]:
    counts = series.dropna().astype(str).value_counts()
    if counts.empty:
        return "", 0
    return counts.index[0], int(counts.iloc[0])


def build_data_profile(df: pd.DataFrame) -> DataProfile:
    """Build compact, reproducible quality and distribution summaries."""
    total_cells = int(df.shape[0] * df.shape[1])
    missing_cells = int(df.isna().sum().sum())
    overview = {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "missing_cells": missing_cells,
        "missing_rate": round(missing_cells / total_cells * 100, 2) if total_cells else 0.0,
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1024**2, 2),
    }

    column_rows = []
    for name in df.columns:
        series = df[name]
        column_rows.append(
            {
                "字段": str(name),
                "类型": str(series.dtype),
                "缺失数": int(series.isna().sum()),
                "缺失率(%)": round(float(series.isna().mean() * 100), 2),
                "唯一值数": int(series.nunique(dropna=True)),
            }
        )
    columns = pd.DataFrame(column_rows)

    numeric_rows = []
    for name in df.select_dtypes(include=np.number).columns:
        series = df[name].dropna()
        numeric_rows.append(
            {
                "字段": str(name),
                "最小值": series.min() if not series.empty else np.nan,
                "中位数": series.median() if not series.empty else np.nan,
                "平均值": round(float(series.mean()), 4) if not series.empty else np.nan,
                "最大值": series.max() if not series.empty else np.nan,
                "标准差": round(float(series.std()), 4) if len(series) > 1 else np.nan,
            }
        )
    numeric = pd.DataFrame(numeric_rows)

    categorical_rows = []
    for name in df.select_dtypes(exclude=np.number).columns:
        top_value, top_count = _safe_top_value(df[name])
        non_null_count = int(df[name].notna().sum())
        categorical_rows.append(
            {
                "字段": str(name),
                "唯一值数": int(df[name].nunique(dropna=True)),
                "最高频值": top_value,
                "最高频次数": top_count,
                "最高频占比(%)": round(top_count / non_null_count * 100, 2)
                if non_null_count
                else 0.0,
            }
        )
    categorical = pd.DataFrame(categorical_rows)

    return DataProfile(
        overview=overview,
        columns=columns,
        numeric=numeric,
        categorical=categorical,
    )
