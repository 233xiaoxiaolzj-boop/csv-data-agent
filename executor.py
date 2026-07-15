"""Restricted execution for model-generated dataframe analysis code."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FORBIDDEN_NAMES = {
    "__import__", "eval", "exec", "open", "input", "compile", "globals", "locals",
    "getattr", "setattr", "delattr", "os", "sys", "subprocess", "requests", "socket",
}
FORBIDDEN_ATTRIBUTES = {"read_csv", "read_excel", "to_csv", "to_excel", "savefig"}


@dataclass
class ExecutionResult:
    result: Any
    figure: Any | None


def validate_code(code: str) -> None:
    """Reject syntax and obvious unsafe constructs before executing code."""
    if len(code) > 4000:
        raise ValueError("代码过长，已拒绝执行。")
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.With, ast.Try, ast.Lambda)):
            raise ValueError(f"不允许的语法：{type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValueError(f"不允许使用：{node.id}")
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRIBUTES:
            raise ValueError(f"不允许调用：{node.attr}")


def execute_code(code: str, df: pd.DataFrame) -> ExecutionResult:
    """Execute validated code with a deliberately small namespace."""
    validate_code(code)
    plt.close("all")
    local_scope: dict[str, Any] = {"df": df.copy(), "pd": pd, "np": np, "plt": plt}
    exec(compile(code, "<agent-code>", "exec"), {"__builtins__": {}}, local_scope)
    if "result" not in local_scope:
        raise ValueError("代码必须将最终分析结果赋值给 result。")
    figure = plt.gcf() if plt.get_fignums() else None
    return ExecutionResult(result=local_scope["result"], figure=figure)
