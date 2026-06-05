"""
Tensor shape inference and validation for Quanta.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..ast.nodes import Expr, ListExpr, LiteralExpr, VarDecl, QuantumDecl
from ..errors import QuantaSemanticError
from ..types.tensor import TensorType, infer_shape, validate_shape


class TensorSymbol:
    def __init__(self, name: str, tensor_type: TensorType, locked_shape: Optional[Tuple[int, ...]] = None):
        self.name = name
        self.tensor_type = tensor_type
        self.locked_shape = locked_shape

    def format_type(self) -> str:
        if self.locked_shape is not None:
            return TensorType(self.tensor_type.base, self.locked_shape).format()
        return self.tensor_type.format()


def tensor_type_from_decl(stmt: VarDecl) -> TensorType:
    if stmt.tensor_type is not None:
        return stmt.tensor_type
    return TensorType.parse_legacy(stmt.type_hint)


def tensor_type_from_quantum(stmt: QuantumDecl) -> TensorType:
    if stmt.tensor_type is not None:
        return stmt.tensor_type
    if stmt.kind in ("qdec", "qfloat") and stmt.size2 is not None:
        return TensorType(stmt.kind, (stmt.size or 0, stmt.size2))
    if stmt.kind == "qfloat" and stmt.size is not None and stmt.size2 is None:
        return TensorType(stmt.kind, (stmt.size,))
    return TensorType.from_quantum(stmt.kind, stmt.shape or [stmt.size or 1])


def validate_literal_tensor(value: Any, tensor_type: TensorType, name: str = "") -> Tuple[int, ...]:
    if tensor_type.is_scalar:
        return ()
    if tensor_type.is_dynamic:
        concrete = tuple(validate_shape(value, tensor_type.dimensions, name))
        return concrete
    expected = tensor_type.shape()
    if expected is None:
        raise QuantaSemanticError(f"Cannot validate dynamic tensor {name}")
    validate_shape(value, expected, name)
    return expected


def eval_literal_list(expr: Expr) -> Any:
    if isinstance(expr, LiteralExpr):
        v = expr.value
        if isinstance(v, str):
            try:
                return float(v) if "." in v else int(v)
            except ValueError:
                return v
        return v
    if isinstance(expr, ListExpr):
        return [eval_literal_list(e) for e in expr.elements]
    raise QuantaSemanticError("Tensor initializer must be a literal nested list")


def lock_tensor_shape(symbol: TensorSymbol, shape: Tuple[int, ...]) -> None:
    if symbol.locked_shape is None:
        symbol.locked_shape = shape
        return
    if symbol.locked_shape != shape:
        raise QuantaSemanticError(
            f"Shape mismatch for '{symbol.name}': locked {symbol.locked_shape}, got {shape}"
        )
