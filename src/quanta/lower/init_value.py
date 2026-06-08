"""Extract compile-time initializer values from AST expressions."""

from __future__ import annotations

from typing import Optional, Union

from ..ast.nodes import Expr, GroupExpr, LiteralExpr, UnaryExpr


def compile_time_number(expr: Expr) -> Optional[Union[int, float]]:
    if isinstance(expr, LiteralExpr):
        try:
            if isinstance(expr.value, bool):
                return int(expr.value)
            if isinstance(expr.value, (int, float)):
                return expr.value
            if isinstance(expr.value, str):
                if "." in expr.value:
                    return float(expr.value)
                return int(expr.value)
        except (ValueError, TypeError):
            return None
    if isinstance(expr, UnaryExpr) and expr.op == "-":
        inner = compile_time_number(expr.right)
        if inner is not None:
            return -inner
    if isinstance(expr, GroupExpr):
        return compile_time_number(expr.expr)
    return None
