"""Read-only Text-to-SQL path backed by SQLGlot validation and DuckDB."""

from __future__ import annotations

import re
from dataclasses import dataclass
from time import perf_counter

import pandas as pd

from agent import _call_ollama, _extract_code, dataframe_summary
from semantic_layer import build_metric_context

SQL_SYSTEM_PROMPT = """你是严谨的数据分析工程师。请把用户问题转换为一条 DuckDB SQL 查询。

硬性规则：
1. 唯一可用的表名是 source_data。
2. 只能生成单条只读 SELECT（允许 WITH）；禁止 DDL、DML、COPY、ATTACH、PRAGMA 和外部文件/网络函数。
3. 常规明细最多返回 200 行；聚合结果也应保持简洁。
4. 日期字符串使用 CAST(order_date AS DATE) 后再提取年份、月份或季度。
5. 只输出 SQL，不要 Markdown、解释或注释。
"""


@dataclass(frozen=True)
class SQLGenerationTrace:
    sql: str
    attempts: int
    repaired: bool


@dataclass(frozen=True)
class SQLExecutionResult:
    result: pd.DataFrame
    sql: str
    latency_seconds: float


def _require_sqlglot():
    try:
        import sqlglot
        from sqlglot import exp
    except ImportError as error:
        raise RuntimeError("缺少 SQLGlot，请先执行 `pip install -r requirements.txt`。") from error
    return sqlglot, exp


def _require_duckdb():
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("缺少 DuckDB，请先执行 `pip install -r requirements.txt`。") from error
    return duckdb


def _extract_sql(content: str) -> str:
    sql = _extract_code(content).strip().rstrip(";")
    return re.sub(r"^sql\s*\n", "", sql, flags=re.IGNORECASE).strip()


def validate_readonly_sql(sql: str, table_name: str = "source_data", row_limit: int = 200) -> str:
    """Validate one SELECT statement and return normalized, limited DuckDB SQL."""
    sqlglot, exp = _require_sqlglot()
    if not sql.strip() or len(sql) > 5000:
        raise ValueError("SQL 为空或过长。")
    if re.search(
        r"\b(?:read_csv|read_csv_auto|read_json|read_json_auto|read_parquet|"
        r"http_get|sqlite_scan|postgres_scan|mysql_scan)\s*\(",
        sql,
        flags=re.IGNORECASE,
    ):
        raise ValueError("不允许调用外部文件、网络或数据库扫描函数。")
    try:
        statements = sqlglot.parse(sql, read="duckdb")
    except Exception as error:
        raise ValueError(f"SQL 语法错误：{error}") from error
    if len(statements) != 1:
        raise ValueError("只允许执行一条 SQL 语句。")

    expression = statements[0]
    if expression.find(exp.Select) is None:
        raise ValueError("只允许 SELECT 查询。")

    forbidden_type_names = (
        "Alter",
        "Attach",
        "Command",
        "Copy",
        "Create",
        "Delete",
        "Drop",
        "Insert",
        "Merge",
        "Pragma",
        "Transaction",
        "TruncateTable",
        "Update",
        "Use",
    )
    forbidden_types = tuple(
        node_type for name in forbidden_type_names if (node_type := getattr(exp, name, None))
    )
    if forbidden_types and any(expression.find(node_type) for node_type in forbidden_types):
        raise ValueError("SQL 包含非只读操作。")

    tables = {table.name.lower() for table in expression.find_all(exp.Table)}
    if tables - {table_name.lower()}:
        raise ValueError(f"只允许访问表 {table_name}。")

    forbidden_functions = {
        "read_csv",
        "read_csv_auto",
        "read_json",
        "read_json_auto",
        "read_parquet",
        "http_get",
        "sqlite_scan",
        "postgres_scan",
        "mysql_scan",
    }
    for function in expression.find_all(exp.Anonymous):
        if function.name.lower() in forbidden_functions:
            raise ValueError(f"不允许调用外部读取函数：{function.name}")

    if expression.args.get("limit") is None:
        expression = expression.limit(row_limit, copy=True)
    return expression.sql(dialect="duckdb")


def generate_sql(question: str, df: pd.DataFrame, model: str) -> SQLGenerationTrace:
    """Generate one query and perform one validation-guided repair when needed."""
    context = f"""数据概况：
{dataframe_summary(df)}

相关业务指标口径：
{build_metric_context(df, question)}

用户问题：{question}
"""
    sql = _extract_sql(
        _call_ollama(
            [
                {"role": "system", "content": SQL_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            model,
        )
    )
    try:
        normalized_sql = validate_readonly_sql(sql)
        return SQLGenerationTrace(normalized_sql, attempts=1, repaired=False)
    except ValueError as first_error:
        repair_prompt = f"""请根据错误修复 SQL。仍然只能输出一条访问 source_data 的只读 SELECT。

原问题：{question}
业务口径：
{build_metric_context(df, question)}
校验错误：{first_error}
候选 SQL：
{sql}
"""
        repaired_sql = _extract_sql(
            _call_ollama(
                [
                    {"role": "system", "content": SQL_SYSTEM_PROMPT},
                    {"role": "user", "content": repair_prompt},
                ],
                model,
            )
        )
        return SQLGenerationTrace(
            validate_readonly_sql(repaired_sql),
            attempts=2,
            repaired=True,
        )


def execute_sql(sql: str, df: pd.DataFrame) -> SQLExecutionResult:
    """Run validated SQL against an in-memory, registered dataframe."""
    duckdb = _require_duckdb()
    normalized_sql = validate_readonly_sql(sql)
    started_at = perf_counter()
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("SET threads = 2")
        connection.execute("SET memory_limit = '512MB'")
        connection.register("source_data", df)
        result = connection.execute(normalized_sql).fetchdf()
    finally:
        connection.close()
    return SQLExecutionResult(
        result=result,
        sql=normalized_sql,
        latency_seconds=round(perf_counter() - started_at, 4),
    )


def should_use_python(question: str) -> bool:
    """Route only charting and advanced statistical requests to Python."""
    normalized = question.lower()
    python_terms = (
        "画图",
        "图表",
        "趋势图",
        "柱状图",
        "直方图",
        "箱线图",
        "散点图",
        "plot",
        "chart",
        "相关系数",
        "回归",
        "检验",
        "置信区间",
        "标准差",
        "分位数",
    )
    return any(term in normalized for term in python_terms)
