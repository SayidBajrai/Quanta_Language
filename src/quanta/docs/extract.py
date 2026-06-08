"""Convert parsed func/gate declarations with /// docs into FunctionSummary objects."""

from __future__ import annotations

from typing import Dict, List, Optional

from ..ast.nodes import ClassDecl, FuncDecl, GateDecl, ParamSpec, Program
from ..stdlib.builtins import FunctionParam, FunctionSummary
from ..types.kinds import CLASSICAL_RETURN_TYPES, CLASSICAL_TYPES, is_wildcard_type
from .comment_parser import ParsedDocComment


def _format_param_spec(ps: ParamSpec) -> str:
    if ps.shape and any(d is not None for d in ps.shape):
        dims = "".join(f"[{d}]" if d is not None else "[]" for d in ps.shape)
        return f"{ps.kind}{dims}"
    return ps.kind


def _format_classical_param(ps: ParamSpec) -> str:
    if ps.kind in CLASSICAL_TYPES:
        return f"{ps.kind} {ps.name}"
    if is_wildcard_type(ps.kind):
        return ps.name
    return ps.name


def build_func_signature(func: FuncDecl) -> str:
    """Build a display signature from a FuncDecl."""
    if func.return_type in CLASSICAL_RETURN_TYPES:
        params = ", ".join(_format_classical_param(ps) for ps in func.param_specs)
    else:
        param_parts: List[str] = []
        for ps in func.param_specs:
            formatted = _format_param_spec(ps)
            if formatted in ("qbit", "qvar") and ps.name:
                param_parts.append(ps.name)
            else:
                param_parts.append(f"{formatted} {ps.name}")
        params = ", ".join(param_parts)
    if func.return_type:
        return f"{func.return_type} {func.name}({params})"
    return f"{func.name}({params})"


def build_gate_signature(gate: GateDecl) -> str:
    """Build a display signature from a GateDecl."""
    params = ", ".join(gate.params)
    return f"gate {gate.name}({params})"


def _params_from_doc_or_decl(
    doc: Optional[ParsedDocComment],
    fallback: List[FunctionParam],
) -> tuple[FunctionParam, ...]:
    if doc and doc.params:
        return doc.params
    return tuple(fallback)


def func_to_summary(func: FuncDecl) -> FunctionSummary:
    """Build a FunctionSummary for a user-defined function."""
    doc = func.doc
    fallback_params = tuple(
        FunctionParam(ps.name, _format_param_spec(ps))
        for ps in func.param_specs
    )
    return FunctionSummary(
        name=func.name,
        summary=doc.summary if doc else "",
        signature=build_func_signature(func),
        params=_params_from_doc_or_decl(doc, list(fallback_params)),
        returns=doc.returns if doc else None,
        category="user",
    )


def gate_to_summary(gate: GateDecl) -> FunctionSummary:
    """Build a FunctionSummary for a user-defined gate macro."""
    doc = gate.doc
    fallback_params = tuple(FunctionParam(name, "qbit") for name in gate.params)
    return FunctionSummary(
        name=gate.name,
        summary=doc.summary if doc else "",
        signature=build_gate_signature(gate),
        params=_params_from_doc_or_decl(doc, list(fallback_params)),
        returns=doc.returns if doc else "void",
        category="user_gate",
    )


def _merge_overload_summaries(summaries: List[FunctionSummary]) -> FunctionSummary:
    """Combine multiple overloads of the same function name for hover/docs."""
    return FunctionSummary(
        name=summaries[0].name,
        summary="\n\n".join(s.summary for s in summaries if s.summary),
        signature="\n".join(s.signature for s in summaries),
        params=(),
        returns=None,
        category="user",
        notes=tuple(
            f"{s.signature}: {s.returns or 'void'}" for s in summaries if s.returns or s.params
        ),
    )


def extract_docs_from_ast(program: Program) -> Dict[str, FunctionSummary]:
    """Collect FunctionSummary entries for all documented func/gate declarations."""
    docs: Dict[str, FunctionSummary] = {}
    func_overloads: Dict[str, List[FunctionSummary]] = {}

    def collect(stmt) -> None:
        if isinstance(stmt, FuncDecl):
            func_overloads.setdefault(stmt.name, []).append(func_to_summary(stmt))
        elif isinstance(stmt, GateDecl):
            docs[stmt.name] = gate_to_summary(stmt)
        elif isinstance(stmt, ClassDecl):
            for member in stmt.members:
                collect(member)

    for stmt in program.statements:
        collect(stmt)

    for name, summaries in func_overloads.items():
        if len(summaries) == 1:
            docs[name] = summaries[0]
        else:
            docs[name] = _merge_overload_summaries(summaries)

    return docs
