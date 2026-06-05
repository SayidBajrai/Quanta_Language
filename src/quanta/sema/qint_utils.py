"""
Utilities for qint operator overloading: width inference, constants, simplification.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

from ..ast.nodes import BinaryExpr, Expr, GroupExpr, IndexExpr, LiteralExpr, VarExpr
from ..types.tensor import TensorType


def parse_qint_width(type_str: Optional[str]) -> Optional[int]:
    """Return bit width from a type string like qint[4], or None for qint[]."""
    if not type_str or not type_str.startswith("qint"):
        return None
    match = re.fullmatch(r"qint(?:\[(\d*)\])?", type_str)
    if not match:
        return None
    raw = match.group(1)
    if raw is None:
        return 1
    if raw == "":
        return None
    return int(raw)


def bitwidth_for_constant(value: int) -> int:
    """Minimum bits to represent a non-negative classical integer."""
    if value <= 0:
        return 1
    return max(1, value.bit_length())


def symbol_qint_width(name: str, symbols: Dict[str, str]) -> Optional[int]:
    type_str = symbols.get(name)
    if not type_str:
        return None
    tensor_type = TensorType.parse_legacy(type_str)
    if tensor_type.base != "qint":
        return None
    return tensor_type.total_size()


def infer_qint_width(expr: Expr, symbols: Dict[str, str]) -> int:
    """Infer result bit width for a qint arithmetic expression."""
    if isinstance(expr, GroupExpr):
        return infer_qint_width(expr.expr, symbols)

    if isinstance(expr, LiteralExpr):
        try:
            return bitwidth_for_constant(int(expr.value))
        except (ValueError, TypeError):
            return 1

    if isinstance(expr, VarExpr):
        return symbol_qint_width(expr.name, symbols) or 1

    if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
        return symbol_qint_width(expr.base.name, symbols) or 1

    if isinstance(expr, BinaryExpr):
        left = infer_qint_width(expr.left, symbols)
        right = infer_qint_width(expr.right, symbols)
        if expr.op == "*":
            return max(left, right)
        return max(left, right)

    return 1


def is_integer_literal(expr: Expr) -> bool:
    if not isinstance(expr, LiteralExpr):
        return False
    try:
        int(expr.value)
        return True
    except (ValueError, TypeError):
        return False


def literal_int_value(expr: Expr) -> Optional[int]:
    if not is_integer_literal(expr):
        return None
    return int(expr.value)  # type: ignore[arg-type]


def is_qint_zero(expr: Expr) -> bool:
    value = literal_int_value(expr)
    return value == 0


def is_qint_one(expr: Expr) -> bool:
    value = literal_int_value(expr)
    return value == 1


def expr_var_name(expr: Expr) -> Optional[str]:
    if isinstance(expr, VarExpr):
        return expr.name
    return None


def is_qint_operand(expr: Expr, symbols: Dict[str, str]) -> bool:
    if is_integer_literal(expr):
        return True
    if isinstance(expr, VarExpr):
        type_str = symbols.get(expr.name, "")
        return type_str.startswith("qint")
    if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
        type_str = symbols.get(expr.base.name, "")
        return type_str.startswith("qint")
    return False
