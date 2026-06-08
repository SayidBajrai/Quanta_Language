"""
Shared Quanta type kind constants and helpers.

Wildcards:
  - ``var``  — any type (classical or quantum)
  - ``qvar`` — any quantum type (qbit, qint, qdec, …)
  - ``cvar`` — any classical type (int, float, str, …)
"""

from __future__ import annotations

from typing import Optional

CLASSICAL_TYPES = frozenset({"int", "float", "bool", "str", "list", "dict", "uint", "dec", "udec"})
QUANTUM_TYPES = frozenset(
    {"qbit", "bit", "qint", "quint", "bint", "qdec", "qudec", "qfloat", "qreal"}
)
WILDCARD_TYPES = frozenset({"var", "qvar", "cvar"})

# ``func var`` — inferred classical return (not a parameter wildcard).
CLASSICAL_RETURN_TYPES = CLASSICAL_TYPES | {"var"}

_WILDCARD_SCORE = {"var": 0, "qvar": 1, "cvar": 1}
_EXACT_MATCH_SCORE = 2


def type_base(kind: str) -> str:
    return kind.split("[", 1)[0]


def is_classical_type(kind: str) -> bool:
    return type_base(kind) in CLASSICAL_TYPES


def is_quantum_type(kind: str) -> bool:
    return type_base(kind) in QUANTUM_TYPES


def is_wildcard_type(kind: str) -> bool:
    return type_base(kind) in WILDCARD_TYPES


def is_classical_return_type(return_type: Optional[str]) -> bool:
    return return_type in CLASSICAL_RETURN_TYPES


def param_symbol_type(kind: str) -> str:
    """Concrete symbol type used for semantic checks inside function bodies."""
    if kind == "qvar":
        return "qbit"
    if kind == "cvar":
        return "cvar"
    return kind


def qasm_param_type(kind: str, size: Optional[int] = 1) -> str:
    """Map a parameter kind to an OpenQASM type for structured ``def`` emission."""
    if kind == "qvar":
        qasm_kind = "qubit"
        sz = size or 1
        return f"{qasm_kind}[{sz}]" if sz > 1 else qasm_kind
    if kind == "cvar":
        return "int"
    if kind == "var":
        return "int"
    if kind in ("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal"):
        qasm_kind = "qubit"
    elif kind in ("bit", "bint"):
        qasm_kind = "bit"
    else:
        qasm_kind = kind
    sz = size or 1
    if sz > 1:
        return f"{qasm_kind}[{sz}]"
    return qasm_kind


def wildcard_match_score(param_type: str, arg_type: str) -> Optional[int]:
    """Return specificity score when ``param_type`` accepts ``arg_type``, else ``None``."""
    param_type = type_base(param_type)
    arg_type = type_base(arg_type)
    if param_type == "var":
        return _WILDCARD_SCORE["var"]
    if param_type == "qvar":
        if is_quantum_type(arg_type):
            return _WILDCARD_SCORE["qvar"]
        return None
    if param_type == "cvar":
        if is_classical_type(arg_type):
            return _WILDCARD_SCORE["cvar"]
        return None
    if param_type == arg_type:
        return _EXACT_MATCH_SCORE
    return None
