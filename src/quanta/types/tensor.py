"""
N-dimensional tensor type utilities for Quanta.

All primitive types (qbit, bit, int, float, bool, str) can be scalars or tensors
with static or dynamic shapes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Union

from ..errors import QuantaSemanticError, QuantaTypeError

SCALAR_BASE_TYPES = frozenset({"qbit", "bit", "qint", "bint", "int", "float", "bool", "str", "list", "dict", "var"})


@dataclass(frozen=True)
class TensorType:
    """Tensor type: base scalar kind + optional per-dimension sizes (None = dynamic)."""

    base: str
    dimensions: tuple  # tuple[Optional[int], ...]

    @property
    def rank(self) -> int:
        return len(self.dimensions)

    @property
    def is_scalar(self) -> bool:
        return self.rank == 0

    @property
    def is_dynamic(self) -> bool:
        return any(d is None for d in self.dimensions)

    def shape(self) -> Optional[tuple]:
        if self.is_dynamic or self.is_scalar:
            return None
        return tuple(self.dimensions)

    def total_size(self) -> Optional[int]:
        if self.is_scalar:
            return 1
        if self.is_dynamic:
            return None
        return math.prod(self.dimensions)

    def with_shape(self, shape: Sequence[int]) -> "TensorType":
        if len(shape) != self.rank:
            raise QuantaTypeError(
                f"Shape length {len(shape)} does not match tensor rank {self.rank}"
            )
        return TensorType(self.base, tuple(shape))

    def format(self) -> str:
        if self.is_scalar:
            return self.base
        parts = []
        for dim in self.dimensions:
            parts.append("[]" if dim is None else f"[{dim}]")
        return self.base + "".join(parts)

    @staticmethod
    def parse_legacy(type_hint: Optional[str]) -> "TensorType":
        if not type_hint:
            return TensorType("var", ())
        if "[" not in type_hint:
            return TensorType(type_hint, ())
        base = type_hint.split("[", 1)[0]
        rest = type_hint[len(base) :]
        dims: List[Optional[int]] = []
        while rest.startswith("["):
            rest = rest[1:]
            if rest.startswith("]"):
                dims.append(None)
                rest = rest[1:]
                continue
            end = rest.find("]")
            if end == -1:
                break
            raw = rest[:end]
            rest = rest[end + 1 :]
            try:
                dims.append(int(raw))
            except ValueError:
                dims.append(None)
        return TensorType(base, tuple(dims))

    @staticmethod
    def from_quantum(kind: str, shape: Sequence[Optional[int]]) -> "TensorType":
        dims = tuple(shape) if shape else (1,)
        return TensorType(kind, dims)


def infer_shape(value: Any) -> List[int]:
    """Infer rectangular tensor shape from a nested list value."""
    if not isinstance(value, list):
        return []
    if not value:
        return [0]
    child_shapes = [infer_shape(item) for item in value]
    if any(shape != child_shapes[0] for shape in child_shapes[1:]):
        raise QuantaSemanticError("Inconsistent tensor shape: ragged nested lists")
    return [len(value)] + child_shapes[0]


def validate_shape(value: Any, expected: Sequence[Optional[int]], path: str = "") -> List[int]:
    """Validate value against expected tensor shape; return concrete shape."""
    actual = infer_shape(value)
    if len(actual) != len(expected):
        raise QuantaSemanticError(
            f"Shape mismatch for {path or 'tensor'}: expected rank {len(expected)}, got {len(actual)}"
        )
    concrete: List[int] = []
    for i, exp in enumerate(expected):
        got = actual[i]
        if exp is not None and exp != got:
            raise QuantaSemanticError(
                f"Shape mismatch for {path or 'tensor'} at dimension {i}: expected {exp}, got {got}"
            )
        concrete.append(got)
    return concrete


def tensor_default_value(base: str) -> Any:
    if base in ("int", "float", "qint", "bint"):
        return 0
    if base == "bool":
        return False
    if base == "str":
        return ""
    if base in ("bit",):
        return 0
    if base in ("qbit",):
        return None
    return None


def allocate_tensor(base: str, shape: Sequence[int]) -> Any:
    if not shape:
        return tensor_default_value(base)
    return [allocate_tensor(base, shape[1:]) for _ in range(shape[0])]


def reshape_tensor(value: Any, new_shape: Sequence[int]) -> Any:
    flat = flatten_tensor(value)
    expected = math.prod(new_shape)
    if len(flat) != expected:
        raise QuantaSemanticError(
            f"Cannot reshape tensor of size {len(flat)} to shape {tuple(new_shape)}"
        )
    return unflatten_tensor(flat, list(new_shape))


def flatten_tensor(value: Any) -> List[Any]:
    if not isinstance(value, list):
        return [value]
    out: List[Any] = []
    for item in value:
        out.extend(flatten_tensor(item))
    return out


def unflatten_tensor(flat: List[Any], shape: List[int]) -> Any:
    if len(shape) == 0:
        return flat[0] if flat else tensor_default_value("float")
    if len(shape) == 1:
        return flat[: shape[0]]
    chunk = math.prod(shape[1:])
    return [unflatten_tensor(flat[i * chunk : (i + 1) * chunk], shape[1:]) for i in range(shape[0])]


def linear_index(multi_index: Sequence[int], shape: Sequence[int]) -> int:
    idx = 0
    stride = 1
    for dim, size in zip(reversed(multi_index), reversed(shape)):
        if dim < 0 or dim >= size:
            raise QuantaSemanticError(f"Index {dim} out of range for dimension size {size}")
        idx += dim * stride
        stride *= size
    return idx


def unravel_index(linear: int, shape: Sequence[int]) -> List[int]:
    result: List[int] = []
    for size in reversed(shape):
        result.append(linear % size)
        linear //= size
    result.reverse()
    return result
