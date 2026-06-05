"""
Tensor algebra core for int, float, and bool tensors (frontend simulator).

Strict shape validation — no implicit broadcasting.
"""

from __future__ import annotations

from typing import Any, List, Sequence, Tuple, Union

from ..errors import QuantaSemanticError
from ..types.tensor import infer_shape

NumericTensor = Union[int, float, bool, list]


def tensor_shape(value: Any) -> Tuple[int, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(infer_shape(value))


def _format_shape(shape: Sequence[int]) -> str:
    if not shape:
        return "()"
    inner = ", ".join(str(d) for d in shape)
    return f"({inner})"


def to_numeric_scalar(value: Any) -> Union[int, float]:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    raise QuantaSemanticError(f"Expected numeric scalar, got {type(value).__name__}")


def _leaf_kind(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    return "unknown"


def _result_kind(a: Any, b: Any, op: str) -> str:
    if op == "*":
        la, lb = _leaf_kind(a), _leaf_kind(b)
        if la == "bool" and lb == "bool":
            return "bool"
    if _leaf_kind(a) == "float" or _leaf_kind(b) == "float":
        return "float"
    return "int"


def _coerce_scalar(value: Any, kind: str) -> Any:
    if kind == "bool":
        return bool(value)
    if kind == "float":
        return float(to_numeric_scalar(value))
    return int(to_numeric_scalar(value))


def require_same_shape(a: Any, b: Any, op_name: str) -> None:
    sa, sb = tensor_shape(a), tensor_shape(b)
    if sa != sb:
        raise QuantaSemanticError(
            f"Shape mismatch: {_format_shape(sa)} vs {_format_shape(sb)} ({op_name})"
        )


def require_rank(value: Any, rank: int, op_name: str) -> None:
    shape = tensor_shape(value)
    if len(shape) != rank:
        raise QuantaSemanticError(
            f"{op_name} requires rank-{rank} tensor, got shape {_format_shape(shape)}"
        )


def dot_product(a: Any, b: Any) -> Union[int, float]:
    require_rank(a, 1, "DotProduct")
    require_rank(b, 1, "DotProduct")
    if len(a) != len(b):
        raise QuantaSemanticError(
            f"DotProduct requires equal-length vectors, got {len(a)} and {len(b)}"
        )
    total = 0.0
    for x, y in zip(a, b):
        total += to_numeric_scalar(x) * to_numeric_scalar(y)
    if all(isinstance(v, int) and not isinstance(v, bool) for v in a + b):
        return int(total)
    return float(total)


def cross_product(a: Any, b: Any) -> List[Union[int, float]]:
    require_rank(a, 1, "CrossProduct")
    require_rank(b, 1, "CrossProduct")
    if len(a) != 3 or len(b) != 3:
        raise QuantaSemanticError("CrossProduct requires 3D vectors")
    a1, a2, a3 = (to_numeric_scalar(v) for v in a)
    b1, b2, b3 = (to_numeric_scalar(v) for v in b)
    return [
        a2 * b3 - a3 * b2,
        a3 * b1 - a1 * b3,
        a1 * b2 - a2 * b1,
    ]


def elementwise_product(a: Any, b: Any) -> Any:
    require_same_shape(a, b, "ElementwiseProduct")
    return _elementwise(a, b, "*")


def _elementwise(a: Any, b: Any, op: str) -> Any:
    if isinstance(a, list):
        if not isinstance(b, list):
            raise QuantaSemanticError("Shape mismatch: tensor vs scalar")
        if len(a) != len(b):
            raise QuantaSemanticError(
                f"Shape mismatch: ({len(a)},) vs ({len(b)},) ({op})"
            )
        return [_elementwise(x, y, op) for x, y in zip(a, b)]
    kind = _result_kind(a, b, op)
    if op == "*":
        if kind == "bool":
            return bool(a) and bool(b)
        return _coerce_scalar(to_numeric_scalar(a) * to_numeric_scalar(b), kind)
    if op == "+":
        return _coerce_scalar(to_numeric_scalar(a) + to_numeric_scalar(b), kind)
    if op == "-":
        return _coerce_scalar(to_numeric_scalar(a) - to_numeric_scalar(b), kind)
    if op == "/":
        return _coerce_scalar(to_numeric_scalar(a) / to_numeric_scalar(b), kind)
    raise QuantaSemanticError(f"Unsupported elementwise operation: {op}")


def _scale_tensor(tensor: Any, scalar: Any) -> Any:
    if not isinstance(tensor, list):
        kind = _result_kind(scalar, tensor, "*")
        if kind == "bool":
            return bool(scalar) and bool(tensor)
        return _coerce_scalar(to_numeric_scalar(scalar) * to_numeric_scalar(tensor), kind)
    return [_scale_tensor(item, scalar) for item in tensor]


def _hcat_blocks(blocks: List[Any]) -> Any:
    if not blocks:
        return []
    if not isinstance(blocks[0], list):
        return sum(blocks, [])
    height = len(blocks[0])
    rows: List[Any] = []
    for i in range(height):
        row: List[Any] = []
        for block in blocks:
            row.extend(block[i])
        rows.append(row)
    return rows


def _vcat_blocks(blocks: List[Any]) -> Any:
    result: List[Any] = []
    for block in blocks:
        if isinstance(block, list):
            result.extend(block)
        else:
            result.append(block)
    return result


def tensor_product(a: Any, b: Any) -> Any:
    if not isinstance(a, list):
        return _scale_tensor(b, a)
    if not isinstance(b, list):
        return _scale_tensor(a, b)
    if not isinstance(a[0], list):
        out: List[Any] = []
        for item in a:
            out.extend(_flatten(tensor_product(item, b)))
        return out
    block_rows = [_hcat_blocks([tensor_product(cell, b) for cell in row]) for row in a]
    return _vcat_blocks(block_rows)


def _flatten(value: Any) -> List[Any]:
    if not isinstance(value, list):
        return [value]
    out: List[Any] = []
    for item in value:
        out.extend(_flatten(item))
    return out


def tensor_elementwise_binop(left: Any, right: Any, op: str) -> Any:
    """Strict elementwise binary op used by expression evaluator."""
    if isinstance(left, list) or isinstance(right, list):
        if not (isinstance(left, list) and isinstance(right, list)):
            raise QuantaSemanticError(
                f"Shape mismatch: tensor vs scalar in elementwise '{op}'"
            )
        require_same_shape(left, right, op)
        return _elementwise(left, right, op)
    kind = _result_kind(left, right, op)
    if op == "*":
        if kind == "bool":
            return bool(left) and bool(right)
        return _coerce_scalar(to_numeric_scalar(left) * to_numeric_scalar(right), kind)
    if op == "+":
        return _coerce_scalar(to_numeric_scalar(left) + to_numeric_scalar(right), kind)
    if op == "-":
        return _coerce_scalar(to_numeric_scalar(left) - to_numeric_scalar(right), kind)
    if op == "/":
        return _coerce_scalar(to_numeric_scalar(left) / to_numeric_scalar(right), kind)
    raise QuantaSemanticError(f"Unsupported tensor operation: {op}")
