"""
Tests for Fidelity(q1, q2) quantum state metric.
"""

import pytest

from quanta.runtime.frontend_sim import get_prints
from quanta.compiler import Compiler
from quanta.errors import QuantaSemanticError
from quanta.sema.validation import SemanticAnalyzer
from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser
from quanta.sema.transform import ASTTransformer


def _analyze(source: str):
    lexer = Lexer()
    parser = Parser()
    transformer = ASTTransformer()
    sema = SemanticAnalyzer()
    ast = parser.parse(lexer.tokenize(source))
    ast = transformer.transform(ast)
    sema.analyze(ast)
    return ast


def test_fidelity_spec_example():
    source = """
qbit q1
qbit q2

H(q1)
X(q2)

float fidelity_q1_q2 = Fidelity(q1, q2)

print(fidelity_q1_q2)
"""
    out = get_prints(source)
    assert out == "0.5"


def test_fidelity_identical_zero_states():
    source = """
qbit q1
qbit q2
print(Fidelity(q1, q2))
"""
    assert get_prints(source) == "1.0"


def test_fidelity_identical_plus_states():
    source = """
qbit q1
qbit q2
H(q1)
H(q2)
print(Fidelity(q1, q2))
"""
    assert get_prints(source) == "1.0"


def test_fidelity_orthogonal_states():
    source = """
qbit q1
qbit q2
X(q2)
print(Fidelity(q1, q2))
"""
    assert get_prints(source) == "0.0"


def test_fidelity_indexed_qubits():
    source = """
qbit[2] q
H(q[0])
X(q[1])
print(Fidelity(q[0], q[1]))
"""
    assert get_prints(source) == "0.5"


def test_fidelity_multi_qubit_registers():
    source = """
qbit[2] a
qbit[2] b
H(a[0])
H(b[0])
print(Fidelity(a, b))
"""
    out = get_prints(source)
    assert float(out) == pytest.approx(1.0, abs=1e-6)


def test_fidelity_semantic_mismatched_sizes():
    with pytest.raises(QuantaSemanticError, match="same size"):
        _analyze(
            """
qbit[2] a
qbit[3] b
float f = Fidelity(a, b)
"""
        )


def test_fidelity_semantic_non_quantum_arg():
    with pytest.raises(QuantaSemanticError, match="qbit or qint"):
        _analyze(
            """
qbit q
bit c
float f = Fidelity(q, c)
"""
        )


def test_fidelity_compiles_without_qasm():
    source = """
qbit q1
qbit q2
H(q1)
float f = Fidelity(q1, q2)
"""
    qasm = Compiler().compile(source)
    assert "qubit" in qasm
    assert "Fidelity" not in qasm


def test_fidelity_deterministic():
    source = """
qbit q1
qbit q2
H(q1)
X(q2)
print(Fidelity(q1, q2))
"""
    assert get_prints(source) == get_prints(source)
