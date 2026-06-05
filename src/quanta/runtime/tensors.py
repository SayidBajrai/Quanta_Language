"""
Runtime tensor operations for Quanta frontend simulation.
"""

from __future__ import annotations

import copy
from typing import Any, List, Optional, Sequence, Tuple

from ..ast.nodes import (
    Expr,
    IndexExpr,
    IndexItem,
    ListExpr,
    LiteralExpr,
    SingleIndex,
    SliceFull,
    SliceIndex,
    VarExpr,
)
from ..errors import QuantaSemanticError
from ..sema.indexing import eval_const_int
from ..types.tensor import (
    allocate_tensor,
    infer_shape,
    linear_index,
    reshape_tensor,
    tensor_default_value,
    validate_shape,
)


def eval_literal_value(expr: Expr, eval_expr) -> Any:
    if isinstance(expr, LiteralExpr):
        v = expr.value
        if isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit():
            return float(v) if "." in v else int(v)
        return v
    if isinstance(expr, ListExpr):
        return [eval_literal_value(e, eval_expr) for e in expr.elements]
    return eval_expr(expr)


def tensor_elementwise_binop(left: Any, right: Any, op: str) -> Any:
    from .tensor_algebra import tensor_elementwise_binop as _algebra_binop

    return _algebra_binop(left, right, op)


def _expand_dim_item(item: IndexItem, dim_size: int, constants: Optional[dict] = None) -> List[int]:
    if isinstance(item, SliceFull):
        return list(range(dim_size))
    if isinstance(item, SingleIndex):
        idx = eval_const_int(item.expr, constants)
        if idx < 0 or idx >= dim_size:
            raise QuantaSemanticError(f"Index {idx} out of range for dimension size {dim_size}")
        return [idx]
    if isinstance(item, SliceIndex):
        start = eval_const_int(item.start, constants) if item.start else 0
        stop = eval_const_int(item.stop, constants) if item.stop else dim_size
        step = eval_const_int(item.step, constants) if item.step else 1
        if step == 0:
            raise QuantaSemanticError("Slice step cannot be zero")
        return list(range(start, stop, step))
    raise QuantaSemanticError(f"Unknown slice item: {type(item).__name__}")


def expand_tensor_indices(
    items: Sequence[IndexItem], shape: Sequence[int], constants: Optional[dict] = None
) -> List[Tuple[int, ...]]:
    if len(items) != len(shape):
        raise QuantaSemanticError(
            f"Tensor index dimension mismatch: expected {len(shape)} indices, got {len(items)}"
        )
    per_dim = [_expand_dim_item(item, shape[i], constants) for i, item in enumerate(items)]
    if all(len(d) == 1 for d in per_dim):
        return [tuple(d[0] for d in per_dim)]
    from itertools import product

    return [tuple(coords) for coords in product(*per_dim)]


def slice_tensor_value(value: Any, items: Sequence[IndexItem], shape: Sequence[int]) -> Any:
    indices = expand_tensor_indices(items, shape)
    if len(indices) == 1 and all(isinstance(item, SingleIndex) for item in items):
        cur = value
        for idx in indices[0]:
            cur = cur[idx]
        return cur

    result_shape: List[int] = []
    for item, dim in zip(items, shape):
        if isinstance(item, SingleIndex):
            continue
        result_shape.append(len(_expand_dim_item(item, dim)))

    if not result_shape:
        return copy.deepcopy(value)

    def gather(tensor, dims, coords=()):
        if len(dims) == 0:
            return copy.deepcopy(tensor)
        item, dim = dims[0]
        if isinstance(item, SingleIndex):
            idx = eval_const_int(item.expr)
            return gather(tensor[idx], dims[1:], coords + (idx,))
        idxs = _expand_dim_item(item, dim)
        return [gather(tensor[i], dims[1:], coords + (i,)) for i in idxs]

    return gather(value, list(zip(items, shape)))


def get_tensor_index(
    value: Any, expr: IndexExpr, shape: Sequence[int], constants: Optional[dict] = None
) -> Any:
    if isinstance(expr.base, IndexExpr):
        inner = get_tensor_index(value, expr.base, shape, constants)
        if len(expr.items) != 1 or not isinstance(expr.items[0], SingleIndex):
            raise QuantaSemanticError("Chained tensor indexing supports only scalar index per level")
        idx = eval_const_int(expr.items[0].expr, constants)
        if isinstance(inner, list):
            return inner[idx]
        return inner
    if len(expr.items) == 1 and isinstance(expr.items[0], SingleIndex):
        idx = eval_const_int(expr.items[0].expr, constants)
        return value[idx]
    return slice_tensor_value(value, expr.items, shape)


def reshape_runtime(value: Any, new_shape: Sequence[int]) -> Any:
    return reshape_tensor(value, new_shape)
