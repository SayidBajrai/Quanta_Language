"""
Function overload registration and resolution.

Uniqueness is determined by parameter count, parameter types, and their order.
Return types are not part of the overload key.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from ..ast.nodes import (
    BinaryExpr,
    CallExpr,
    Expr,
    FuncDecl,
    GroupExpr,
    IndexExpr,
    LiteralExpr,
    ParamSpec,
    UnaryExpr,
    VarExpr,
)
from ..errors import QuantaSemanticError
from ..types.kinds import (
    CLASSICAL_TYPES,
    is_classical_type,
    is_quantum_type,
    type_base,
    wildcard_match_score,
)

ParamSig = Tuple[str, ...]


def format_param_type(ps: ParamSpec) -> str:
    """Canonical type string for one parameter in an overload signature."""
    if ps.kind in CLASSICAL_TYPES or type_base(ps.kind) in ("var", "qvar", "cvar"):
        if ps.kind in CLASSICAL_TYPES:
            return ps.kind
        return ps.kind
    if ps.shape and len(ps.shape) == 1 and ps.shape[0] == 1:
        return ps.kind
    if ps.shape and any(d is not None for d in ps.shape):
        dims = "".join(f"[{d}]" if d is not None else "[]" for d in ps.shape)
        return f"{ps.kind}{dims}"
    return ps.kind


def _normalize_match_type(type_str: str) -> str:
    base = type_base(type_str)
    if base in CLASSICAL_TYPES:
        return type_str if "[" in type_str else base
    for kind in ("qbit", "bit", "qint", "quint", "bint", "qdec", "qudec", "qfloat", "qreal"):
        if type_str == kind or type_str == f"{kind}[1]":
            return kind
    return type_str


def func_param_signature(func: FuncDecl) -> ParamSig:
    """Overload key: ordered parameter types only."""
    return tuple(format_param_type(ps) for ps in func.param_specs)


def mangled_def_name(name: str, sig: ParamSig) -> str:
    """OpenQASM-safe unique name for an overloaded ``def``."""
    if not sig:
        return name
    safe = "_".join(t.replace("[", "").replace("]", "") for t in sig)
    return f"{name}__{safe}"


def format_param_sig(sig: ParamSig) -> str:
    if not sig:
        return "()"
    return f"({', '.join(sig)})"


class FuncOverloadTable:
    """Registry of user-defined functions keyed by name and parameter signature."""

    def __init__(self) -> None:
        self._by_name: Dict[str, List[FuncDecl]] = {}
        self._by_sig: Dict[str, Dict[ParamSig, FuncDecl]] = {}

    def register(self, func: FuncDecl) -> None:
        name = func.name
        sig = func_param_signature(func)
        if name not in self._by_sig:
            self._by_sig[name] = {}
            self._by_name[name] = []
        if sig in self._by_sig[name]:
            raise QuantaSemanticError(
                f"Duplicate function overload for '{name}{format_param_sig(sig)}'"
            )
        self._by_sig[name][sig] = func
        self._by_name[name].append(func)

    def has(self, name: str) -> bool:
        return name in self._by_name

    def overloads(self, name: str) -> List[FuncDecl]:
        return list(self._by_name.get(name, []))

    def get(self, name: str, sig: ParamSig) -> Optional[FuncDecl]:
        return self._by_sig.get(name, {}).get(sig)


def _normalize_type(type_str: str) -> str:
    if not type_str:
        return "var"
    base = type_base(type_str)
    if base in CLASSICAL_TYPES:
        return type_str if "[" in type_str else base
    return type_str


def infer_expr_type(expr: Expr, symbols: Dict[str, object]) -> str:
    """Best-effort static type for overload resolution at a call site."""
    if isinstance(expr, LiteralExpr):
        value = expr.value
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            if value in ("true", "false"):
                return "bool"
            stripped = value.replace(".", "", 1).replace("-", "", 1).replace("+", "", 1)
            if stripped.isdigit():
                return "float" if "." in value else "int"
        return "var"
    if isinstance(expr, VarExpr):
        sym = symbols.get(expr.name)
        if sym is not None:
            sym_type = getattr(sym, "type", None) or getattr(sym, "symbol_type", None)
            if sym_type:
                return _normalize_type(str(sym_type))
        return "var"
    if isinstance(expr, IndexExpr):
        base = expr.base
        if isinstance(base, VarExpr):
            sym = symbols.get(base.name)
            if sym is not None:
                sym_type = getattr(sym, "type", None) or getattr(sym, "symbol_type", None)
                if sym_type and "[" in str(sym_type):
                    return "qbit"
            return "qbit"
        return "qbit"
    if isinstance(expr, GroupExpr):
        return infer_expr_type(expr.expr, symbols)
    if isinstance(expr, UnaryExpr):
        return infer_expr_type(expr.right, symbols)
    if isinstance(expr, BinaryExpr):
        left = infer_expr_type(expr.left, symbols)
        right = infer_expr_type(expr.right, symbols)
        if left == right and type_base(left) not in ("var", "qvar", "cvar"):
            return left
        if is_classical_type(left) and type_base(left) != "cvar":
            return left
        if is_classical_type(right) and type_base(right) != "cvar":
            return right
        return "var"
    if isinstance(expr, CallExpr) and expr.resolved_func is not None:
        ret = expr.resolved_func.return_type
        return ret if ret else "var"
    return "var"


def _match_score(param_sig: ParamSig, arg_types: Sequence[str]) -> Optional[int]:
    if len(param_sig) != len(arg_types):
        return None
    score = 0
    for param_type, arg_type in zip(param_sig, arg_types):
        param_type = _normalize_match_type(param_type)
        arg_type = _normalize_match_type(arg_type)
        part = wildcard_match_score(param_type, arg_type)
        if part is None:
            return None
        score += part
    return score


def resolve_func_overload(
    name: str,
    funcs: Sequence[FuncDecl],
    arg_types: Sequence[str],
) -> FuncDecl:
    if not funcs:
        raise QuantaSemanticError(f"Undefined function: {name}")

    candidates: List[Tuple[int, FuncDecl]] = []
    for func in funcs:
        sig = func_param_signature(func)
        score = _match_score(sig, arg_types)
        if score is not None:
            candidates.append((score, func))

    if not candidates:
        raise QuantaSemanticError(
            f"No matching overload for '{name}{format_param_sig(tuple(arg_types))}'"
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score = candidates[0][0]
    best = [func for score, func in candidates if score == best_score]
    if len(best) > 1:
        raise QuantaSemanticError(
            f"Ambiguous call to '{name}{format_param_sig(tuple(arg_types))}': "
            "multiple overloads match"
        )
    return best[0]
