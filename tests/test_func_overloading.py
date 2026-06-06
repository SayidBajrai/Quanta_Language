"""Tests for user-defined function overloading."""

import pytest

from quanta import compile, get_prints, get_user_function_docs
from quanta.errors import QuantaSemanticError
from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser
from quanta.sema.overload import FuncOverloadTable, func_param_signature, resolve_func_overload
from quanta.sema.validation import SemanticAnalyzer


INT_ADD = """
func int add(int a, int b) {
    return a + b;
}
"""

FLOAT_ADD = """
func float add(float a, float b) {
    return a + b;
}
"""

OVERLOADED_ADD = INT_ADD + FLOAT_ADD + """
int a = 1
int b = 4
float x = 1.5
float y = 2.5
Print(add(a, b))
Print(add(x, y))
"""


def test_func_param_signature_key():
    ast = Parser().parse(Lexer().tokenize(INT_ADD + FLOAT_ADD))
    funcs = [s for s in ast.statements if hasattr(s, "param_specs")]
    assert func_param_signature(funcs[0]) == ("int", "int")
    assert func_param_signature(funcs[1]) == ("float", "float")


def test_register_duplicate_overload_rejected():
    source = INT_ADD + """
func int add(int x, int y) {
    return x + y;
}
"""
    with pytest.raises(QuantaSemanticError, match="Duplicate function overload"):
        SemanticAnalyzer().analyze(Parser().parse(Lexer().tokenize(source)))


def test_resolve_overload_by_arg_types():
    ast = Parser().parse(Lexer().tokenize(INT_ADD + FLOAT_ADD))
    table = FuncOverloadTable()
    for stmt in ast.statements:
        table.register(stmt)
    funcs = table.overloads("add")
    int_fn = resolve_func_overload("add", funcs, ("int", "int"))
    float_fn = resolve_func_overload("add", funcs, ("float", "float"))
    assert int_fn.return_type == "int"
    assert float_fn.return_type == "float"


def test_no_matching_overload_rejected():
    ast = Parser().parse(Lexer().tokenize(INT_ADD))
    table = FuncOverloadTable()
    for stmt in ast.statements:
        table.register(stmt)
    with pytest.raises(QuantaSemanticError, match="No matching overload"):
        resolve_func_overload("add", table.overloads("add"), ("float", "float"))


def test_overloaded_add_end_to_end():
    assert get_prints(OVERLOADED_ADD) == "5\n4.0"


def test_overloaded_add_structured_qasm():
    qasm = compile(OVERLOADED_ADD, keep_structure=True)
    assert "def add__int_int" in qasm
    assert "def add__float_float" in qasm
    assert "add__int_int" in qasm
    assert "add__float_float" in qasm


def test_overloaded_docs_merge_signatures():
    source = """
/// - int add
/// int a - first
/// int b - second
/// return: int - sum
func int add(int a, int b) {
    return a + b;
}

/// - float add
/// float a - first
/// float b - second
/// return: float - sum
func float add(float a, float b) {
    return a + b;
}
"""
    doc = get_user_function_docs(source, "add")
    assert doc is not None
    assert "int add(int a, int b)" in doc.signature
    assert "float add(float a, float b)" in doc.signature
