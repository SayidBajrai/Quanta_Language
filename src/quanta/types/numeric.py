"""
Classical and quantum numeric type encoding helpers.

Signed quantum types (``qint``, ``qdec``) use two's complement internally.
Unsigned legacy quantum types (``quint``, ``qudec``) use plain binary magnitude.
``qreal`` maps basis index k to min + (k / (N-1)) * (max - min).
"""

from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple

NUMERIC_QUANTUM_KINDS = frozenset(
    {"qint", "quint", "qdec", "qudec", "qreal", "qfloat", "bint"}
)
NUMERIC_CLASSICAL_KINDS = frozenset({"uint", "dec", "udec"})
NUMERIC_KINDS = NUMERIC_QUANTUM_KINDS | NUMERIC_CLASSICAL_KINDS

DEFAULT_INT_BITS = 32
DEFAULT_FIXED_INT_BITS = 16
DEFAULT_FIXED_FRAC_BITS = 16
DEFAULT_QREAL_MIN = -1.0
DEFAULT_QREAL_MAX = 1.0
DEFAULT_QREAL_QBITS = 32

_INTEGER_KINDS = frozenset({"uint", "qint", "quint"})
_FIXED_POINT_KINDS = frozenset({"dec", "udec", "qdec", "qudec"})

_PAREN_TYPE_RE = re.compile(
    r"^(qint|quint|qdec|qudec|qfloat|uint|dec|udec|qreal|bint)\((.+)\)$"
)


def apply_numeric_defaults(kind: str, params: Optional[dict] = None) -> dict:
    """Normalize partial or missing numeric type parameters to canonical defaults."""
    partial = dict(params or {})
    if kind == "qreal":
        bits = partial.get("size", DEFAULT_QREAL_QBITS)
        return {
            "size": bits,
            "size2": None,
            "shape": [bits],
            "real_min": partial.get("real_min", DEFAULT_QREAL_MIN),
            "real_max": partial.get("real_max", DEFAULT_QREAL_MAX),
            "dynamic": False,
        }
    if kind in _FIXED_POINT_KINDS:
        int_bits = partial.get("size", DEFAULT_FIXED_INT_BITS)
        frac_bits = partial.get("size2", DEFAULT_FIXED_FRAC_BITS)
        return {
            "size": int_bits,
            "size2": frac_bits,
            "shape": [int_bits, frac_bits],
            "real_min": None,
            "real_max": None,
            "dynamic": False,
        }
    if kind in _INTEGER_KINDS:
        width = partial.get("size", DEFAULT_INT_BITS)
        return {
            "size": width,
            "size2": None,
            "shape": [width],
            "real_min": None,
            "real_max": None,
            "dynamic": False,
        }
    if kind == "qfloat":
        int_bits = partial["size"]
        frac_bits = partial["size2"]
        return {
            "size": int_bits,
            "size2": frac_bits,
            "shape": [int_bits, frac_bits],
            "real_min": None,
            "real_max": None,
            "dynamic": False,
        }
    return partial


def dynamic_numeric_params() -> dict:
    """Marker for ``quint()`` / ``qint()`` width inference from operands."""
    return {
        "size": None,
        "size2": None,
        "shape": [None],
        "real_min": None,
        "real_max": None,
        "dynamic": True,
    }


def finalize_numeric_params(kind: str, params: dict) -> dict:
    """Apply defaults unless params are explicitly marked dynamic."""
    if params.get("dynamic"):
        return params
    return apply_numeric_defaults(kind, params)


def build_tensor_type(kind: str, params: dict):
    """Build a :class:`TensorType` from finalized numeric parameters."""
    from .tensor import TensorType

    finalized = finalize_numeric_params(kind, params)
    if finalized.get("dynamic"):
        return TensorType(kind, (None,))
    if kind == "qreal":
        return TensorType(
            kind,
            (finalized["size"],),
            real_min=finalized["real_min"],
            real_max=finalized["real_max"],
        )
    if kind in _FIXED_POINT_KINDS or kind == "qfloat":
        return TensorType(kind, (finalized["size"], finalized["size2"]))
    return TensorType(kind, (finalized["size"],))


def format_numeric_type(
    kind: str,
    size: Optional[int] = None,
    size2: Optional[int] = None,
    real_min: Optional[float] = None,
    real_max: Optional[float] = None,
) -> str:
    if kind == "qreal":
        lo = real_min if real_min is not None else 0.0
        hi = real_max if real_max is not None else 1.0
        bits = size or 1
        return f"qreal({lo},{hi},{bits})"
    if kind in ("qdec", "qudec", "dec", "udec") and size2 is not None:
        return f"{kind}({size},{size2})"
    if size is not None:
        return f"{kind}({size})"
    return kind


def parse_numeric_type(type_str: str) -> Optional[dict]:
    """Parse ``kind(params)`` numeric type strings."""
    if not type_str:
        return None
    match = _PAREN_TYPE_RE.fullmatch(type_str.strip())
    if not match:
        return None
    kind = match.group(1)
    inner = match.group(2)
    if kind == "qreal":
        if not inner.strip():
            return {"kind": kind, **apply_numeric_defaults(kind)}
        parts = _split_top_level_commas(inner)
        partial: dict = {}
        try:
            if len(parts) >= 1 and parts[0].strip():
                partial["real_min"] = float(parts[0].strip())
            if len(parts) >= 2 and parts[1].strip():
                partial["real_max"] = float(parts[1].strip())
            if len(parts) >= 3 and parts[2].strip():
                partial["size"] = int(parts[2].strip())
        except ValueError:
            return None
        normalized = apply_numeric_defaults(kind, partial)
        return {"kind": kind, **normalized}
    if kind in ("qdec", "qudec", "dec", "udec"):
        parts = _split_top_level_commas(inner)
        if len(parts) != 2:
            return None
        try:
            a = int(parts[0].strip())
            b = int(parts[1].strip())
        except ValueError:
            return None
        return {"kind": kind, "size": a, "size2": b}
    if not inner.strip():
        if kind in _INTEGER_KINDS:
            return {"kind": kind, **dynamic_numeric_params()}
        if kind in _FIXED_POINT_KINDS:
            return {"kind": kind, **apply_numeric_defaults(kind)}
        return None
    try:
        width = int(inner.strip())
    except ValueError:
        return None
    return {"kind": kind, "size": width}


def _split_top_level_commas(text: str) -> List[str]:
    parts: List[str] = []
    depth = 0
    start = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    return parts


def flat_qubit_count(kind: str, size: Optional[int], size2: Optional[int] = None) -> int:
    if kind == "qreal":
        return size or 1
    if kind in ("qdec", "qudec") and size is not None and size2 is not None:
        return size + size2
    if kind == "qfloat" and size is not None and size2 is not None:
        return 1 + size + size2
    return size or 1


# --- Signed qint (two's complement) ---

def qint_signed_range(bits: int) -> Tuple[int, int]:
    if bits <= 0:
        return (0, 0)
    return (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1)


def twos_complement_encode(value: int, bits: int) -> int:
    lo, hi = qint_signed_range(bits)
    if value < lo or value > hi:
        raise ValueError(f"value {value} out of signed range [{lo}, {hi}] for {bits} bits")
    if value >= 0:
        return value
    return (1 << bits) + value


def twos_complement_decode(unsigned: int, bits: int) -> int:
    unsigned &= (1 << bits) - 1
    if unsigned & (1 << (bits - 1)):
        return unsigned - (1 << bits)
    return unsigned


def init_bit_pattern(value: int, kind: str, bits: int, frac_bits: int = 0) -> int:
    """Return unsigned bit pattern for quantum register initialization."""
    if kind == "quint":
        if value < 0:
            raise ValueError("quint cannot represent negative values")
        if value >= (1 << bits):
            raise ValueError(f"value {value} out of range for quint({bits})")
        return value
    if kind == "qint":
        total = bits + frac_bits
        scaled = int(round(value * (1 << frac_bits))) if frac_bits else value
        return twos_complement_encode(scaled, total)
    if kind in ("qdec", "qudec"):
        total = bits + frac_bits
        if kind == "qudec":
            scaled = int(round(value * (1 << frac_bits)))
            if scaled < 0:
                raise ValueError("qudec cannot represent negative values")
            if scaled >= (1 << total):
                raise ValueError(f"value {value} out of range for qudec({bits},{frac_bits})")
            return scaled
        scaled = int(round(value * (1 << frac_bits)))
        return twos_complement_encode(scaled, total)
    if kind == "qreal":
        raise ValueError("qreal registers cannot be initialized from a scalar literal")
    return value


# --- qdec ranges ---

def qdec_signed_range(int_bits: int, frac_bits: int) -> Tuple[float, float]:
    lo_int, hi_int = qint_signed_range(int_bits)
    step = 1.0 / (1 << frac_bits)
    return (float(lo_int), hi_int + (1.0 - step))


def qdec_step(frac_bits: int) -> float:
    return 1.0 / (1 << frac_bits)


def decode_qdec_value(unsigned: int, int_bits: int, frac_bits: int, signed: bool = True) -> float:
    total = int_bits + frac_bits
    raw = unsigned & ((1 << total) - 1)
    if signed:
        scaled = twos_complement_decode(raw, total)
    else:
        scaled = raw
    return scaled / (1 << frac_bits)


# --- qreal interval mapping ---

def qreal_num_states(qbits: int) -> int:
    return 1 << qbits


def qreal_value_at(k: int, qbits: int, min_val: float, max_val: float) -> float:
    n = qreal_num_states(qbits)
    if n <= 1:
        return min_val
    return min_val + (k / (n - 1)) * (max_val - min_val)


def qreal_nearest_index(value: float, qbits: int, min_val: float, max_val: float) -> int:
    n = qreal_num_states(qbits)
    if n <= 1:
        return 0
    if max_val == min_val:
        return 0
    t = (value - min_val) / (max_val - min_val)
    t = max(0.0, min(1.0, t))
    return int(round(t * (n - 1)))


def basis_index_to_signed_value(index: int, bits: int) -> int:
    return twos_complement_decode(index, bits)


def uniform_basis_amplitude(num_states: int) -> float:
    return 1.0 / math.sqrt(num_states)


def is_uniform_superposition(probs: List[float], tol: float = 1e-9) -> bool:
    if not probs:
        return True
    expected = 1.0 / len(probs)
    return all(abs(p - expected) <= tol for p in probs)
