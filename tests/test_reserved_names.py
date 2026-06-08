"""Tests for reserved OpenQASM identifier names."""

import pytest

from quanta import compile, get_prints
from quanta.errors import QuantaSemanticError
from quanta.sema.reserved_names import validate_qasm_identifier


@pytest.mark.parametrize(
    "name,kind",
    [
        ("x", "register name"),
        ("h", "register name"),
        ("cx", "register name"),
        ("measure", "register name"),
        ("reset", "register name"),
        ("swap", "gate name"),
        ("def", "function name"),
    ],
)
def test_reserved_names_rejected(name, kind):
    with pytest.raises(QuantaSemanticError, match="cannot be used"):
        validate_qasm_identifier(name, kind)


def test_qbit_register_named_x_rejected():
    source = """
qbit x
H(x)
"""
    with pytest.raises(QuantaSemanticError, match="OpenQASM gate 'x'"):
        compile(source)


def test_qbit_register_named_h_rejected():
    source = """
qbit h
H(h)
"""
    with pytest.raises(QuantaSemanticError, match="OpenQASM gate 'h'"):
        compile(source)


def test_gate_macro_named_x_rejected():
    source = """
gate x(a) {
    H(a)
}
qbit q
x(q)
"""
    with pytest.raises(QuantaSemanticError, match="OpenQASM gate 'x'"):
        compile(source)


def test_function_param_named_h_rejected():
    source = """
func apply_h(qbit h) {
    H(h)
}
"""
    with pytest.raises(QuantaSemanticError, match="OpenQASM gate 'h'"):
        compile(source, keep_structure=True)


def test_valid_register_names_compile():
    source = """
qbit q
H(q)
"""
    qasm = compile(source)
    assert "qubit" in qasm
    assert "h q" in qasm.lower()


def test_valid_names_run_in_frontend_sim():
    assert get_prints("qbit q\nH(q)\n") == ""

@pytest.mark.parametrize("name", ["X", "H"])
def test_reserved_check_is_case_insensitive(name):
    with pytest.raises(QuantaSemanticError):
        validate_qasm_identifier(name, "register name")
