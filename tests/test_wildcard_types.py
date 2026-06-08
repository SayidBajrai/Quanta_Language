"""Tests for var / qvar / cvar wildcard parameter types."""

import pytest

from quanta.errors import QuantaSemanticError
from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser
from quanta.sema.overload import FuncOverloadTable, resolve_func_overload
from quanta.sema.validation import SemanticAnalyzer


def _funcs(source: str):
    ast = Parser().parse(Lexer().tokenize(source))
    return [s for s in ast.statements if hasattr(s, "param_specs")]


def test_qvar_matches_quantum_not_classical():
    source = """
func apply(qvar q) { H(q); }
func pick(cvar x) { return x; }
"""
    funcs = _funcs(source)
    table = FuncOverloadTable()
    for fn in funcs:
        table.register(fn)
    apply_fn = resolve_func_overload("apply", table.overloads("apply"), ("qbit",))
    pick_fn = resolve_func_overload("pick", table.overloads("pick"), ("int",))
    assert apply_fn.name == "apply"
    assert pick_fn.name == "pick"
    with pytest.raises(QuantaSemanticError, match="No matching overload"):
        resolve_func_overload("apply", table.overloads("apply"), ("int",))
    with pytest.raises(QuantaSemanticError, match="No matching overload"):
        resolve_func_overload("pick", table.overloads("pick"), ("qbit",))


def test_var_matches_any_category():
    source = """
func echo(var x) { return x; }
func touch(var q) { H(q); }
"""
    funcs = _funcs(source)
    table = FuncOverloadTable()
    for fn in funcs:
        table.register(fn)
    resolve_func_overload("echo", table.overloads("echo"), ("int",))
    resolve_func_overload("touch", table.overloads("touch"), ("qbit",))


def test_specific_overload_beats_wildcard():
    source = """
func int pick(cvar x) { return x; }
func int pick(int x) { return x; }
"""
    funcs = _funcs(source)
    table = FuncOverloadTable()
    for fn in funcs:
        table.register(fn)
    chosen = resolve_func_overload("pick", table.overloads("pick"), ("int",))
    assert chosen.param_specs[0].kind == "int"


def test_qvar_beats_var_for_quantum_args():
    source = """
func apply(var q) { H(q); }
func apply(qvar q) { H(q); }
"""
    funcs = _funcs(source)
    table = FuncOverloadTable()
    for fn in funcs:
        table.register(fn)
    chosen = resolve_func_overload("apply", table.overloads("apply"), ("qbit",))
    assert chosen.param_specs[0].kind == "qvar"


def test_quantum_func_validates_with_qvar_param():
    source = """
func bell(a, b) {
    H(a);
    CNot(a, b);
}
qbit q0
qbit q1
bell(q0, q1)
"""
    SemanticAnalyzer().analyze(Parser().parse(Lexer().tokenize(source)))
