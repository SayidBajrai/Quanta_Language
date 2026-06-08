"""
Utilities for quint/qint operator overloading: width inference, constants, simplification.
"""

from __future__ import annotations

from typing import Dict, Optional

from ..ast.nodes import BinaryExpr, Expr, GroupExpr, IndexExpr, LiteralExpr, VarExpr
from ..types.numeric import parse_numeric_type
from ..types.tensor import TensorType

_QUINTEGER_BASES = ("qint", "quint")


def parse_quinteger_width(type_str: Optional[str]) -> Optional[int]:
    """Return bit width from ``qint(n)`` / ``quint(n)``, or None for dynamic ``quint()``."""
    if not type_str:
        return None
    parsed = parse_numeric_type(type_str)
    if parsed and parsed["kind"] in _QUINTEGER_BASES:
        return parsed.get("size")
    return None


def bitwidth_for_constant(value: int) -> int:
    """Minimum bits to represent a non-negative classical integer."""
    if value <= 0:
        return 1
    return max(1, value.bit_length())


def symbol_quinteger_width(name: str, symbols: Dict[str, str]) -> Optional[int]:
    type_str = symbols.get(name)
    if not type_str:
        return None
    tensor_type = TensorType.parse_legacy(type_str)
    if tensor_type.base not in _QUINTEGER_BASES:
        return None
    return tensor_type.total_size()


def infer_quinteger_width(expr: Expr, symbols: Dict[str, str]) -> int:
    """Infer result bit width for a quint/qint arithmetic expression."""
    if isinstance(expr, GroupExpr):
        return infer_quinteger_width(expr.expr, symbols)

    if isinstance(expr, LiteralExpr):
        try:
            return bitwidth_for_constant(int(expr.value))
        except (ValueError, TypeError):
            return 1

    if isinstance(expr, VarExpr):
        return symbol_quinteger_width(expr.name, symbols) or 1

    if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
        return symbol_quinteger_width(expr.base.name, symbols) or 1

    if isinstance(expr, BinaryExpr):
        left = infer_quinteger_width(expr.left, symbols)
        right = infer_quinteger_width(expr.right, symbols)
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


def is_quinteger_zero(expr: Expr) -> bool:
    value = literal_int_value(expr)
    return value == 0


def is_quinteger_one(expr: Expr) -> bool:
    value = literal_int_value(expr)
    return value == 1


def expr_var_name(expr: Expr) -> Optional[str]:
    if isinstance(expr, VarExpr):
        return expr.name
    return None


def is_quinteger_operand(expr: Expr, symbols: Dict[str, str]) -> bool:
    if is_integer_literal(expr):
        return True
    if isinstance(expr, VarExpr):
        type_str = symbols.get(expr.name, "")
        return any(type_str.startswith(base) for base in _QUINTEGER_BASES)
    if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
        type_str = symbols.get(expr.base.name, "")
        return any(type_str.startswith(base) for base in _QUINTEGER_BASES)
    return False


# Backwards-compatible aliases used during migration
parse_qint_width = parse_quinteger_width
infer_qint_width = infer_quinteger_width
is_qint_zero = is_quinteger_zero
is_qint_one = is_quinteger_one
is_qint_operand = is_quinteger_operand
