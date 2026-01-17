"""
Tests for QASM3 code generation
"""

import pytest
from quanta import compile


def test_bell_state():
    """Test Bell state compilation"""
    source = """
qubit[2] q;
bit[2] c;

func bell(a, b) {
    H(a);
    CNot(a, b);
}

bell(q[0], q[1]);
Measure(q[0], c[0]);
"""
    qasm = compile(source)
    
    assert "OPENQASM 3" in qasm
    assert "qubit[2] q" in qasm
    assert "h q[0]" in qasm.lower()
    assert "cx" in qasm.lower() or "cnot" in qasm.lower()


def test_simple_gates():
    """Test simple gate compilation"""
    source = """
qubit[1] q;
H(q[0]);
X(q[0]);
"""
    qasm = compile(source)
    
    assert "h q[0]" in qasm.lower()
    assert "x q[0]" in qasm.lower()


def test_measure_all():
    """Test MeasureAll() function (case-sensitive)"""
    source = """
qubit[2] q;
bit[2] c;
MeasureAll(q, c);
"""
    qasm = compile(source)
    
    assert "measure q[0] -> c[0]" in qasm.lower()
    assert "measure q[1] -> c[1]" in qasm.lower()
