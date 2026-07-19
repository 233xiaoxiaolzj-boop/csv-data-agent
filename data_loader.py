"""Defensive CSV loading with explicit size, encoding and delimiter handling."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from io import BytesIO

import pandas as pd

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_ROWS = 1_000_000
ENCODINGS = ("utf-8-sig", "utf-8", "gb18030")


@dataclass(frozen=True)
class CSVLoadResult:
    dataframe: pd.DataFrame
    encoding: str
    delimiter: str
    warnings: tuple[str, ...]


def _decode_sample(content: bytes) -> tuple[str, str]:
    sample = content[:64_000]
    for encoding in ENCODINGS:
        try:
            return sample.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码，请转换为 UTF-8 或 GB18030 后重试。")


def load_csv(content: bytes) -> CSVLoadResult:
    """Load untrusted CSV bytes with bounded size and deterministic diagnostics."""
    if not content:
        raise ValueError("CSV 文件为空。")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("CSV 超过 50 MB 限制，请先抽样或转换为数据库表。")

    decoded_sample, encoding = _decode_sample(content)
    try:
        delimiter = csv.Sniffer().sniff(decoded_sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    header = next(csv.reader(decoded_sample.splitlines(), delimiter=delimiter), [])
    normalized_header = [column.strip() for column in header]
    duplicate_names = sorted(
        {name for name in normalized_header if normalized_header.count(name) > 1}
    )
    if duplicate_names:
        raise ValueError(f"CSV 包含重复字段名：{', '.join(duplicate_names)}")

    dataframe = pd.read_csv(
        BytesIO(content),
        encoding=encoding,
        sep=delimiter,
        low_memory=False,
        nrows=MAX_ROWS + 1,
    )
    if len(dataframe) > MAX_ROWS:
        raise ValueError("CSV 超过 100 万行限制，请使用 DuckDB/Parquet 数据源或先进行抽样。")
    warnings = []
    unnamed = [column for column in dataframe.columns if str(column).startswith("Unnamed:")]
    if unnamed:
        warnings.append(f"检测到疑似空索引列：{', '.join(map(str, unnamed))}")
    if dataframe.empty:
        warnings.append("文件包含字段名但没有数据行。")
    return CSVLoadResult(dataframe, encoding, delimiter, tuple(warnings))
