"""Restricted execution for model-generated dataframe analysis code."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FORBIDDEN_NAMES = {
    "__import__",
    "eval",
    "exec",
    "open",
    "input",
    "compile",
    "globals",
    "locals",
    "getattr",
    "setattr",
    "delattr",
    "os",
    "sys",
    "subprocess",
    "requests",
    "socket",
}
FORBIDDEN_ATTRIBUTES = {
    "load",
    "loadtxt",
    "read_csv",
    "read_excel",
    "read_html",
    "read_json",
    "read_pickle",
    "read_sql",
    "save",
    "savefig",
    "savetxt",
    "to_csv",
    "to_excel",
    "to_json",
    "to_pickle",
    "to_sql",
    "show",
    "pause",
}
FORBIDDEN_NODES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.For,
    ast.FunctionDef,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Lambda,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


@dataclass
class ExecutionResult:
    result: Any
    figure: Any | None


def validate_code(code: str) -> None:
    """Reject unsafe or resource-heavy constructs before executing code."""
    if len(code) > 4000:
        raise ValueError("代码过长，已拒绝执行。")
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        raise ValueError(f"代码语法错误：{error.msg}") from error

    nodes = list(ast.walk(tree))
    if len(nodes) > 500:
        raise ValueError("代码结构过于复杂，已拒绝执行。")
    for node in nodes:
        if isinstance(node, FORBIDDEN_NODES):
            raise ValueError(f"不允许的语法：{type(node).__name__}")
        if isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or node.id.startswith("__"):
                raise ValueError(f"不允许使用：{node.id}")
        if isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_ATTRIBUTES or node.attr.startswith("__"):
                raise ValueError(f"不允许调用：{node.attr}")
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and abs(node.value) > 1_000_000_000:
                raise ValueError("数值常量过大，已拒绝执行。")
            if isinstance(node.value, str) and len(node.value) > 10_000:
                raise ValueError("字符串常量过长，已拒绝执行。")


def execute_code(code: str, df: pd.DataFrame) -> ExecutionResult:
    """Execute validated code with a deliberately small namespace."""
    validate_code(code)
    plt.close("all")
    local_scope: dict[str, Any] = {"df": df.copy(), "pd": pd, "np": np, "plt": plt}
    exec(
        compile(code, "<agent-code>", "exec"),
        {"__builtins__": SAFE_BUILTINS},
        local_scope,
    )
    if "result" not in local_scope:
        raise ValueError("代码必须将最终分析结果赋值给 result。")
    figure = plt.gcf() if plt.get_fignums() else None
    return ExecutionResult(result=local_scope["result"], figure=figure)
